import os
from typing import Optional

from core.kernel.path import IbPath, PathValidator, ModuleNameSpace
from core.base.diagnostics.codes import DEP_SECURITY_ERROR

class ModuleResolveError(Exception):
    def __init__(self, module_name: str, importer_path: Optional[str] = None, message: Optional[str] = None, code: Optional[str] = None):
        self.module_name = module_name
        self.importer_path = importer_path
        self.message = message
        self.code = code
        
        if message:
            msg = message
        else:
            msg = f"Cannot resolve module '{module_name}'"
            if importer_path:
                msg += f" from '{importer_path}'"
        super().__init__(msg)

class ModuleResolver:
    """
    Resolves module names (e.g., 'utils.math' or '..calc') to absolute file paths.
    Acts as the Single Source of Truth for path resolution.
    """
    def __init__(self, root_dir: str):
        # root_dir 已由 engine 规范化，消费者信任，仅 IbPath 包装。
        self._project_root = IbPath.from_native(root_dir)
        self.root_dir = root_dir
        # Extensions to probe, in order of preference
        self.extensions = ['.ibci', '.py', '']
        # Explicitly allowed files outside root (e.g. for run_string)
        self.allowed_files: set[str] = set()

    def allow_file(self, file_path: str):
        """Explicitly allow a file outside root_dir."""
        self.allowed_files.add(PathValidator.canonicalize_for_security(file_path).to_native())

    def _check_path_security(self, path: str):
        """
        Ensure the path is within the project root directory.
        Prevents Path Traversal attacks.
        """
        # 经 PathValidator 规范化（解符号链接）+ 沙箱判定，全仓统一。
        abs_path_ib = PathValidator.canonicalize_for_security(path)
        abs_path = abs_path_ib.to_native()

        # 1. Check if explicitly allowed
        if abs_path in self.allowed_files:
            return

        # 2. is_within 沙箱检查（跨盘由内部返回 False 覆盖）。
        if not PathValidator.is_within(self._project_root, abs_path_ib):
            raise ModuleResolveError(
                "", None,
                message=f"Path '{path}' resolves to '{abs_path}' which is outside project root '{self.root_dir}'",
                code=DEP_SECURITY_ERROR,
            )

    def _get_candidate_path(self, module_name: str, context_file: Optional[str] = None) -> str:
        """Helper to calculate candidate path without probing."""
        is_relative = module_name.startswith('.')
        
        candidate_path: str
        
        if is_relative:
            if not context_file:
                raise ModuleResolveError(module_name, None)
                
            # Count leading dots
            level = 0
            for char in module_name:
                if char == '.':
                    level += 1
                else:
                    break
            
            # module_name: ..math -> level=2, suffix=math
            suffix = module_name[level:]
            
            # Start from the directory containing the importer file
            # 经 IbPath 规范化（替代散点 os.path.abspath/dirname）。
            current_dir = IbPath.from_native(context_file).resolve_dot_segments().parent
            current_dir = current_dir.to_native() if current_dir is not None else ""

            # Go up (level - 1) times
            base_dir = current_dir
            for _ in range(level - 1):
                _parent = IbPath.from_native(base_dir).parent
                base_dir = _parent.to_native() if _parent is not None else ""
                
            # Construct relative path
            if suffix:
                rel_path = ModuleNameSpace.module_to_relpath(suffix)
                candidate_path = (IbPath.from_native(base_dir) / rel_path).to_native() if base_dir else rel_path
            else:
                # Import is just '..', e.g. from .. import X -> importing form __init__ of parent
                candidate_path = base_dir

        else:
            # Absolute import (from root)
            rel_path = ModuleNameSpace.module_to_relpath(module_name)
            candidate_path = (IbPath.from_native(self.root_dir) / rel_path).to_native()
            
        # Security Check
        self._check_path_security(candidate_path)
            
        return candidate_path

    def resolve(self, module_name: str, context_file: Optional[str] = None) -> str:
        """
        Resolve a module name to an absolute file path.

        解析语义：
        - 相对导入（``.``/``..`` 前缀）：锚定导入方文件目录（level 逐级上溯），
          单候选；
        - 绝对导入：两级搜索——① 导入方文件所在目录（入口目录/子模块同目录
          模块——sys.path[0] 惯例，多文件用例的同目录模块可解析）→ ② 项目根
          （root_dir，项目级模块，既有语义兜底）。逐级探测，首个命中返回。

        Args:
            module_name: The module name (e.g., 'pkg.mod' or '..mod').
            context_file: The absolute path of the file importing the module
                (required for relative imports; 绝对导入两级搜索的 ① 级锚点)。

        Returns:
            The absolute path to the resolved file.

        Raises:
            ModuleResolveError: If the module cannot be found.
        """
        if module_name.startswith("."):
            candidates = [self._get_candidate_path(module_name, context_file)]
            absolute = False
        else:
            candidates = self._get_absolute_candidates(module_name, context_file)
            absolute = True

        for cand in candidates:
            # Security Check——相对导入单候选：越界即安全错误（既有语义）；
            # 绝对导入 ① 级（导入方目录）可能位于沙箱外（如合成入口载体
            # tempfile 位于系统临时目录）——越界候选跳过，回落 ② 级（项目根，
            # 恒在沙箱内）。
            try:
                self._check_path_security(cand)
            except Exception:
                if not absolute or len(candidates) == 1:
                    raise
                continue
            resolved = self._probe_file(cand)
            if resolved:
                return resolved

        raise ModuleResolveError(module_name, context_file)

    def _get_absolute_candidates(self, module_name: str,
                                 context_file: Optional[str]) -> list:
        """绝对导入候选序列：导入方文件目录（同目录模块）→ 项目根。"""
        rel_path = ModuleNameSpace.module_to_relpath(module_name)
        cands = []
        if context_file:
            ctx_dir = IbPath.from_native(context_file).resolve_dot_segments().parent
            if ctx_dir is not None:
                cands.append(
                    (IbPath.from_native(ctx_dir.to_native()) / rel_path).to_native()
                )
        cands.append((IbPath.from_native(self.root_dir) / rel_path).to_native())
        # 去重（导入方位于项目根时两级同候选）——保序
        return list(dict.fromkeys(cands))

    def _probe_file(self, base_path: str) -> Optional[str]:
        """Check for file existence with various extensions and package inits."""
        # 1. Check direct file: path.ibci
        for ext in self.extensions:
            path = base_path + ext
            if os.path.isfile(path):
                return path
                
        # 2. Check package init: path/__init__.ibci
        for ext in self.extensions:
            init_path = (IbPath.from_native(base_path) / ('__init__' + ext)).to_native()
            if os.path.isfile(init_path):
                return init_path
                
        return None
