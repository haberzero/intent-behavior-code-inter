import os
from typing import Dict, List, Optional, Any, Set
from collections import OrderedDict
from core.compiler.dependencies import ModuleInfo, ImportInfo, CircularDependencyError, ModuleStatus, ImportType, DependencyGraph
from core.kernel.ast import IbModule
from core.compiler.lexer.lexer import Lexer
from core.compiler.common.tokens import Token
from core.compiler.parser.parser import Parser
from core.compiler.semantic.analyzer import SemanticAnalyzer
from core.compiler.common.diagnostics import DiagnosticReporter
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.base.source.source_manager import SourceManager
from core.kernel.path import IbPath, PathValidator, ModuleNameSpace, safe_relpath
from core.compiler.parser.resolver.resolver import ModuleResolver, ModuleResolveError
from core.kernel.issue import Severity, CompilerError
from core.base.source_atomic import Location
from core.kernel.host_interface import HostInterface
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger
from core.base.diagnostics.codes import (
    DEP_GRAPH_ERROR, DEP_FAILED_DEPENDENCY, DEP_SECURITY_ERROR, DEP_FILE_NOT_FOUND, INT_INTERNAL_ERROR,
    DEP_MODULE_NOT_FOUND, SEM_IMPORT_CONFLICT, SEM_UNDEFINED_SYMBOL, DEP_CIRCULAR_IMPORT
)
from core.kernel.blueprint import CompilationArtifact, CompilationResult

from core.base.interfaces import (
    ISourceProvider, ICompilerService
)
from core.base.enums import Provenance
from core.kernel.symbols import (
    Symbol, VariableSymbol, SymbolKind, SymbolTable, FunctionSymbol, TypeSymbol
)
from core.kernel.spec import TypeDef as ModuleMetadata, IbSpec, TypeKind
from core.kernel.spec.member import MemberSpec, MethodMemberSpec
class Scheduler(ICompilerService):
    """
    Top-level scheduler for multi-file compilation.
    Orchestrates Lexer, Parser, and Semantic Analyzer.
    """
    MAX_CACHE_SIZE = 100 # Maximum modules to keep in memory

    def __init__(self, root_dir: str, host_interface: Optional[HostInterface] = None, debugger: Optional[Any] = None, issue_tracker: Optional[DiagnosticReporter] = None, registry: Optional[Any] = None):
        # root_dir 已由 engine 经 canonicalize_for_security 规范化（单一 realpath 源），
        # 消费者信任传入值，仅做 IbPath 类型包装（不再重复 realpath——幂等冗余）。
        self._project_root = IbPath.from_native(root_dir)
        self.root_dir = root_dir
        self.source_manager = SourceManager()
        self.issue_tracker = issue_tracker or IssueTracker(source_provider=self.source_manager)
        self.resolver = ModuleResolver(self.root_dir)
        self.host_interface = host_interface or HostInterface()
        self.debugger = debugger or core_debugger
        self.registry = registry
        
        # Initial symbols to pre-populate in every module's global scope
        self.predefined_symbols: Dict[str, Any] = {}
        
        # Caches (Using OrderedDict for LRU behavior)
        self.modules: Dict[str, ModuleInfo] = {} # Path -> Info
        self.ast_cache: OrderedDict[str, IbModule] = OrderedDict()   # Path -> AST
        self.symbol_table_cache: OrderedDict[str, Any] = OrderedDict() # Path -> SymbolTable
        self.token_cache: OrderedDict[str, List[Token]] = OrderedDict() # Path -> Tokens
        self.import_star_cache: OrderedDict[str, Dict[str, List[str]]] = OrderedDict()  # Path -> {导入模块名: 注入成员名}
        self.module_name_to_path: Dict[str, str] = {} # Name -> Path (Fast lookup)
        
        # 插件类型缓存：用于存储已转换的外部插件模块类型，支持跨插件继承
        self.plugin_type_cache: Dict[str, Any] = {}
        
        # Build Cache
        # Map: file_path -> mtime
        self.build_cache: Dict[str, float] = {}
        
        # Explicitly allowed files outside root (e.g. for run_string)
        self.allowed_files: Set[str] = set()

    def allow_file(self, file_path: str):
        """Explicitly allow a file outside root_dir."""
        abs_path = PathValidator.canonicalize_for_security(file_path).to_native()
        self.allowed_files.add(abs_path)
        self.resolver.allow_file(abs_path)

    # --- ICompilerService Implementation ---

    def compile_file(self, file_path: str) -> CompilationArtifact:
        """ICompilerService: Compiles a file and its dependencies."""
        return self.compile_project(file_path)

    def resolve_module_path(self, module_name: str) -> Optional[str]:
        """ICompilerService: Resolves a module name to its absolute file path."""
        # Check cache first
        if module_name in self.module_name_to_path:
            return self.module_name_to_path[module_name]
        
        # Try resolving relative to root_dir
        try:
            return self.resolver.resolve(module_name, (IbPath.from_native(self.root_dir) / "__init__.ibci").to_native())
        except ModuleResolveError as e:
            # 安全错误（越权访问）必须传播——降级为 None 会把安全违规掩盖成"模块未找到"
            if getattr(e, 'code', None) == DEP_SECURITY_ERROR:
                raise
            core_debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL,
                                f"Module resolve failed for '{module_name}': {e}")
            return None

    def get_module_source(self, module_name: str) -> Optional[str]:
        """ICompilerService: Returns the source content of a module."""
        path = self.resolve_module_path(module_name)
        if not path:
            return None
        return self.source_manager.get_full_source(path)

    # ---------------------------------------

    def compile_project(self, entry_file: str) -> CompilationArtifact:
        """
        Compiles the project starting from entry_file.
        Returns a CompilationArtifact (Blueprint) for the interpreter.
        """
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Starting project compilation: {entry_file}")
        # 0. Clear previous state
        self.issue_tracker.clear()
        self.modules.clear()
        self.module_name_to_path.clear()
        
        artifact = CompilationArtifact()
        
        # 1. Scan Dependencies (Recursive)
        # We manually drive the scanning process here to control token caching
        # entry 经 canonicalize_for_security 规范化（与 root 同源，解 symlink），
        # 替代散点 os.path.abspath（engine 上游已规范化，此处统一收口）。
        entry_file = PathValidator.canonicalize_for_security(entry_file).to_native()
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Phase 1: Scanning dependencies starting from {entry_file}")
        self._scan_and_cache(entry_file)
            
        if self.issue_tracker.has_errors():
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, "Dependency scanning failed with errors.")
            raise CompilerError(self.issue_tracker.diagnostics)

        # 2. Build Dependency Graph and Get Order
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, "Phase 2: Building dependency graph and determining compilation order.")
        graph = DependencyGraph(self.modules, debugger=self.debugger)
        try:
            compilation_order = graph.get_compilation_order()
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DATA, f"Compilation order determined:", data=compilation_order)
        except CircularDependencyError as e:
            self.issue_tracker.error(str(e), code=DEP_CIRCULAR_IMPORT)
            raise CompilerError(self.issue_tracker.diagnostics)
        except Exception as e:
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Graph error: {str(e)}")
            self.issue_tracker.error(str(e), code=DEP_GRAPH_ERROR)
            # 图构建异常也是内部 bug，但须以契约内异常（CompilerError）承载——
            # 否则记录的诊断成为孤儿，上层只按 "Runtime Error" 重抛（双通道）。
            raise CompilerError(self.issue_tracker.diagnostics)

        # 3. Compile in Topological Order
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Phase 3: Compiling {len(compilation_order)} files in topological order.")
        for file_path in compilation_order:
            mod_info = self.modules.get(file_path)
            if not mod_info:
                continue

            # Check if dependencies failed
            failed_deps = []
            for imp in mod_info.imports:
                if imp.file_path:
                    dep_info = self.modules.get(imp.file_path)
                    if dep_info and dep_info.status == ModuleStatus.FAILED:
                        failed_deps.append(imp.module_name)
            
            if failed_deps:
                self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Skipping {file_path} because dependencies failed: {failed_deps}")
                self.issue_tracker.error(f"IbModule '{file_path}' cannot be compiled because its dependencies failed: {', '.join(failed_deps)}", code=DEP_FAILED_DEPENDENCY)
                mod_info.status = ModuleStatus.FAILED
                continue

            # Determine module name
            rel_path = safe_relpath(file_path, self.root_dir)
            module_name = ModuleNameSpace.relpath_to_module_name(rel_path)
            self.module_name_to_path[module_name] = file_path

            # Check mtime or cache
            last_mtime = self.build_cache.get(file_path, 0.0)
            if mod_info.mtime > last_mtime or file_path not in self.ast_cache:
                # Recompile
                self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Compiling file: {file_path} (Cache miss/Outdated)")
                try:
                    res = self._compile_file(file_path, artifact)
                    artifact.add_module(module_name, res)
                    self.import_star_cache[file_path] = dict(res.import_star_members)
                    mod_info.status = ModuleStatus.SUCCESS
                except CompilerError:
                    self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Failed to compile: {file_path}")
                    mod_info.status = ModuleStatus.FAILED
                self.build_cache[file_path] = mod_info.mtime
            else:
                self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Using cached AST for: {file_path}")
                # Reconstruct result from cache
                res = CompilationResult(
                    module_ast=self.ast_cache[file_path], 
                    symbol_table=self.symbol_table_cache.get(file_path)
                )
                res.import_star_members = self.import_star_cache.get(file_path, {})
                artifact.add_module(module_name, res)
                mod_info.status = ModuleStatus.SUCCESS
            
        if self.issue_tracker.has_errors():
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, "Project compilation failed with errors.")
            raise CompilerError(self.issue_tracker.diagnostics)
            
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, "Project compilation successful.")
        
        # Set entry point
        entry_rel = safe_relpath(entry_file, self.root_dir)
        artifact.entry_module = ModuleNameSpace.relpath_to_module_name(entry_rel)
        artifact.global_symbols = self.predefined_symbols

        return artifact

    def _prune_cache(self):
        """
        Maintains the LRU cache by removing oldest items if capacity exceeded.

        统一剪枝 ast/token/symbol_table/build 五缓存（R2-E4：此前只剪 ast+token，
        symbol_table/build 无界增长；同路径的其它缓存条目一并淘汰）。
        """
        while len(self.ast_cache) > self.MAX_CACHE_SIZE:
            oldest_path, _ = self.ast_cache.popitem(last=False)
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Pruning cache for {oldest_path}")
            self.token_cache.pop(oldest_path, None)
            self.symbol_table_cache.pop(oldest_path, None)
            self.import_star_cache.pop(oldest_path, None)
            self.build_cache.pop(oldest_path, None)

    def _scan_and_cache(self, entry_file: str):
        """
        Recursively scan files, Lex them, cache tokens, and resolving imports.
        Manages the dependency graph creation and prevents cycles during scanning.
        """
        visited = set()
        queue = [entry_file]
        
        # We also need to track what we've processed in this session to avoid infinite loops if cycle exists
        # Although DependencyGraph will catch cycles later, we don't want infinite recursion here.
        processed_in_this_scan = set()

        while queue:
            current_path = queue.pop(0)
            if current_path in visited:
                continue
            
            visited.add(current_path)
            processed_in_this_scan.add(current_path)
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Scanning: {current_path}")
            
            # Security Check: Ensure file is within root_dir or explicitly allowed
            # 统一沙箱检查走 PathValidator（canonicalize_for_security 解符号链接 + is_within 判定）。
            abs_path_ib = PathValidator.canonicalize_for_security(current_path)
            if abs_path_ib.to_native() not in self.allowed_files:
                if not PathValidator.is_within(self._project_root, abs_path_ib):
                    self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Security violation: Access denied for {current_path}")
                    self.issue_tracker.error(f"Security Error: Access denied for file outside root: {current_path}", code=DEP_SECURITY_ERROR)
                    continue

            # 1. Read Content & Lex (if not cached or outdated)
            try:
                with open(current_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    mtime = os.path.getmtime(current_path)
            except (FileNotFoundError, OSError):
                self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"File not found: {current_path}")
                self.issue_tracker.error(f"File not found: {current_path}", code=DEP_FILE_NOT_FOUND)
                continue
            
            # Register source before lexing to enable context in errors
            self.source_manager.add_source(current_path, content)
            
            # Lexing
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Lexing for dependencies: {current_path}")
            lexer = Lexer(content, self.issue_tracker, debugger=self.debugger)
            try:
                tokens = lexer.tokenize()
                self.token_cache[current_path] = tokens
            except CompilerError:
                # Lexer 诊断已上报 tracker，跳过该模块（依赖分析继续）。
                continue
                
            # 2. Scan Imports using Main Parser (parse_imports_only)
            # Replaced ImportScanner with Parser.parse_imports_only
            parser = Parser(
                tokens, 
                self.issue_tracker, 
                debugger=self.debugger
            )
            imports = parser.parse_imports_only()
            
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DATA, f"Found imports in {current_path}:", data=[i.module_name for i in imports])
            
            # Create ModuleInfo
            mod_info = ModuleInfo(
                file_path=current_path,
                imports=imports,
                content=content,
                mtime=mtime
            )
            self.modules[current_path] = mod_info

            # 3. Resolve and Enqueue Imports
            for imp in imports:
                # Skip external modules - they don't have source files
                # 直接通过元数据注册表查询外部模块，消除 HostInterface 兼容性依赖
                module_name = imp.module_name
                resolved_spec = self.host_interface.metadata.resolve(module_name)
                if resolved_spec is not None and getattr(resolved_spec, 'kind', None) == TypeKind.MODULE.value:
                    self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Found external module: {module_name}")
                    continue

                try:
                    resolved_path = self.resolver.resolve(imp.module_name, current_path)
                    imp.file_path = resolved_path
                    self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Resolved import '{imp.module_name}' to {resolved_path}")
                    
                    # Cycle Prevention: Only add to queue if not visited
                    if resolved_path not in visited and resolved_path not in queue:
                        queue.append(resolved_path)
                        
                except Exception as e:
                     self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Failed to resolve '{imp.module_name}': {str(e)}")
                     # 结构化错误码分派（ModuleResolveError 携带 code 字段）
                     code = getattr(e, 'code', None) or DEP_MODULE_NOT_FOUND
                     
                     self.issue_tracker.report(
                         Severity.ERROR, 
                         code=code, 
                         message=str(e),
                         location=Location(file_path=current_path, line=imp.lineno, column=1)
                     )
                         
    def _compile_file(self, file_path: str, artifact: CompilationArtifact):
        """
        Compiles a single file: Lex (reuse) -> Parse -> Semantic.
        Populates caches.
        """
        module_info = self.modules.get(file_path)
        if not module_info:
            return 

        # Determine module name
        rel_path = safe_relpath(file_path, self.root_dir)
        module_name = ModuleNameSpace.relpath_to_module_name(rel_path)
        self.module_name_to_path[module_name] = file_path
        
        # Get content
        source = module_info.content
        self.source_manager.add_source(file_path, source)
        
        # Create per-file tracker
        file_tracker = IssueTracker(file_path, source_provider=self.source_manager)
        
        try:
            # 1. Reuse Tokens
            tokens = self.token_cache.get(file_path)
            if not tokens:
                # re-lex 纯粹的防御机制，常规情况下，理论上来讲不应该出现
                self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Token cache miss for {file_path}, re-lexing.")
                lexer = Lexer(source, file_tracker, debugger=self.debugger)
                tokens = lexer.tokenize()
            
            # 2. Parse
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Parsing: {file_path} (IbModule: {module_name})")
            parser = Parser(
                tokens, 
                file_tracker, 
                package_name=module_name, 
                module_resolver=self.resolver,
                host_interface=self.host_interface,
                debugger=self.debugger
            )
            ast_node = parser.parse()
            
            # 3. Semantic Analysis
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Semantic Analysis: {file_path}")
            
            # 在分析前预注册空的 ModuleMetadata 到注册表
            # 这样 TypeDef 才能在解析时找到目标，即使当前模块还未分析完
            if self.registry is None:
                raise RuntimeError("Scheduler.registry is required for compilation")
            pre_mod_meta = self.registry.factory.create_module(module_name)
            self.registry.register(pre_mod_meta)
            
            analyzer = SemanticAnalyzer(file_tracker, debugger=self.debugger, registry=self.registry, module_name=module_name)
            
            # Inject predefined symbols
            for name, val in self.predefined_symbols.items():
                if isinstance(val, Symbol):
                    analyzer.symbol_table.define(val)
                else:
                    # Log a warning for non-Symbol predefined symbols (should not happen now)
                    self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Warning: Predefined symbol '{name}' is not a Symbol object, skipping.")
            
            # Inject imported modules
            # ``from x import *`` 实际注入的成员名（按导入模块名记录）——精确契约
            # 集合只在编译期存在，序列化进 artifact 供运行时精确枚举。
            import_star_members: Dict[str, List[str]] = {}
            for imp in module_info.imports:
                # 查找已编译的结果或外部元数据
                s_mod_type = None
                imp_res = None
                
                if imp.file_path:
                    rel_imp_path = safe_relpath(imp.file_path, self.root_dir)
                    imp_mod_name = ModuleNameSpace.relpath_to_module_name(rel_imp_path)

                    # 解析已编译文件模块的真实元数据（其成员在依赖模块编译完成后已
                    # 由 _compile_file 写入 registry）：依赖图按拓扑序编译，被导入
                    # 模块先于导入者完成，故 resolve 必含真实成员。此前的 Lazy
                    # 描述符（ModuleMetadata(name=...)) members 恒为空，导致
                    # `from <ibci文件> import x` 全部无法解析（INT_INTERNAL_ERROR/
                    # SEM_UNDEFINED_SYMBOL）。
                    s_mod_type = self.registry.resolve(imp_mod_name) or ModuleMetadata(name=imp_mod_name)
                    # 必须绑定注册表以便后续解包
                else:
                    resolved_spec = self.host_interface.metadata.resolve(imp.module_name)
                    if resolved_spec is not None and getattr(resolved_spec, 'kind', None) == TypeKind.MODULE.value:
                        if imp.module_name in self.plugin_type_cache:
                            s_mod_type = self.plugin_type_cache[imp.module_name]
                        else:
                            s_mod_type = resolved_spec
                            self.registry.register(s_mod_type)
                            self.plugin_type_cache[imp.module_name] = s_mod_type
                
                if not s_mod_type:
                    continue
                    
                # 根据 import_type 进行符号注入
                if imp.import_type == ImportType.IMPORT:
                    # 1. 处理 import a.b as c
                    # 目前 parse_imports_only 为每个 alias 创建一个 ImportInfo
                    alias = imp.names[0] if imp.names else None
                    local_name = alias.asname if alias and alias.asname else imp.module_name
                    
                    # 如果是多段导入 (import a.b) 且没有 asname，则注入 a
                    parts = imp.module_name.split('.')
                    if not (alias and alias.asname) and len(parts) > 1:
                        root_name = parts[0]
                        # 构造嵌套模块结构
                        root_sym = analyzer.symbol_table.resolve(root_name)
                        # 使用 is_module() 代替 isinstance
                        if (
                            not root_sym
                            or not root_sym.spec
                            or root_sym.spec.kind != TypeKind.MODULE.value
                        ):
                            # 使用工厂创建
                            root_mod_type = self.registry.factory.create_primitive("module")
                            root_mod_type.name = root_name
                            root_sym = VariableSymbol(name=root_name, kind=SymbolKind.MODULE, spec=root_mod_type)
                            analyzer.symbol_table.define(root_sym)
                        
                        curr_mod = root_sym.spec
                        for i in range(1, len(parts)):
                            part_name = parts[i]
                            is_last = (i == len(parts) - 1)
                            if is_last:
                                target_sym = VariableSymbol(name=part_name, kind=SymbolKind.MODULE, spec=s_mod_type)
                                curr_mod.members[part_name] = target_sym
                            else:
                                next_mod_sym = curr_mod.members.get(part_name)
                                # 使用 is_module() 代替 isinstance
                                if (
                                    not next_mod_sym
                                    or not getattr(next_mod_sym, 'spec', None)
                                    or next_mod_sym.spec.kind != TypeKind.MODULE.value
                                ):
                                    next_mod_type = self.registry.factory.create_primitive("module")
                                    next_mod_type.name = part_name
                                    next_mod_sym = VariableSymbol(name=part_name, kind=SymbolKind.MODULE, spec=next_mod_type)
                                    curr_mod.members[part_name] = next_mod_sym
                                curr_mod = next_mod_sym.spec
                    else:
                        # 普通导入或带别名导入
                        existing = analyzer.symbol_table.resolve(local_name)
                        if existing:
                            if existing.kind == SymbolKind.MODULE:
                                # 同名 MODULE 符号已存在（同一模块被重复导入）——幂等跳过即可。
                                self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL,
                                    f"[import] Symbol '{local_name}' already exists as MODULE in '{file_path}', skipping re-injection.")
                            else:
                                # 用户定义的符号（CLASS / FUNCTION 等）与导入名冲突。
                                # 用户自有符号优先；发出 SEM_IMPORT_CONFLICT WARNING 提示用户检查命名。
                                file_tracker.warning(
                                    f"Import '{local_name}' conflicts with an already-defined "
                                    f"{existing.kind.name.lower()} symbol of the same name. "
                                    f"The import is ignored; the locally-defined symbol takes precedence.",
                                    location=Location(file_path=file_path, line=imp.lineno, column=1),
                                    code=SEM_IMPORT_CONFLICT,
                                )
                        else:
                            mod_sym = VariableSymbol(name=local_name, kind=SymbolKind.MODULE, spec=s_mod_type, provenance=Provenance.EXTERNAL_MODULE)
                            analyzer.symbol_table.define(mod_sym)
                            # `import file` also gates the disk-backed types
                            # (file_handle / audio / image / video) into the importing scope.
                            for exported_name in getattr(s_mod_type, "exported_types", []):
                                existing_exported = analyzer.symbol_table.resolve(exported_name)
                                if existing_exported:
                                    self.debugger.trace(
                                        CoreModule.SCHEDULER, DebugLevel.DETAIL,
                                        f"[import] Exported type '{exported_name}' from module '{imp.module_name}' "
                                        f"already exists in '{file_path}', skipping."
                                    )
                                    continue
                                exported_spec = self.registry.resolve(exported_name)
                                if exported_spec is None:
                                    self.debugger.trace(
                                        CoreModule.SCHEDULER, DebugLevel.DETAIL,
                                        f"[import] Exported type '{exported_name}' from module '{imp.module_name}' "
                                        f"not found in registry; skipping."
                                    )
                                    continue
                                type_sym = TypeSymbol(
                                    name=exported_name,
                                    kind=SymbolKind.CLASS,
                                    spec=exported_spec,
                                    provenance=Provenance.KERNEL_NATIVE,
                                    # align with runtime setup_context which
                                    # defines these kernel-native classes as `intrinsic:<name>`.
                                    uid=f"intrinsic:{exported_name}",
                                )
                                analyzer.symbol_table.define(type_sym)
                        
                elif imp.import_type == ImportType.FROM_IMPORT:
                    # 2. 处理 from mod import a, b as c, *
                    for alias in imp.names:
                        if alias.name == '*':
                            injected_names: List[str] = []
                            for name, member in s_mod_type.members.items():
                                existing = analyzer.symbol_table.resolve(name)
                                if existing:
                                    if existing.kind != SymbolKind.MODULE:
                                        file_tracker.warning(
                                            f"'from {imp.module_name} import *' conflicts with an already-defined "
                                            f"{existing.kind.name.lower()} symbol '{name}'. "
                                            f"The import is ignored; the locally-defined symbol takes precedence.",
                                            location=Location(file_path=file_path, line=imp.lineno, column=1),
                                            code=SEM_IMPORT_CONFLICT,
                                        )
                                    else:
                                        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL,
                                            f"[from-import *] Symbol '{name}' from module '{imp.module_name}' conflicts with existing symbol in '{file_path}', skipping.")
                                else:
                                    new_sym = self._create_symbol_from_member(name, member)
                                    if new_sym:
                                        analyzer.symbol_table.define(new_sym)
                                        injected_names.append(name)
                            if injected_names:
                                import_star_members.setdefault(imp.module_name, []).extend(injected_names)
                        else:
                            # 注入特定符号
                            target_member = s_mod_type.members.get(alias.name)
                            if target_member:
                                local_name = alias.asname if alias.asname else alias.name
                                existing = analyzer.symbol_table.resolve(local_name)
                                if existing:
                                    # 用户定义的符号与 from-import 名冲突。
                                    if existing.kind != SymbolKind.MODULE:
                                        file_tracker.warning(
                                            f"'from {imp.module_name} import {alias.name}' conflicts with an already-defined "
                                            f"{existing.kind.name.lower()} symbol '{local_name}'. "
                                            f"The import is ignored; the locally-defined symbol takes precedence.",
                                            location=Location(file_path=file_path, line=imp.lineno, column=1),
                                            code=SEM_IMPORT_CONFLICT,
                                        )
                                    else:
                                        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL,
                                            f"[from-import] Symbol '{local_name}' from module '{imp.module_name}' conflicts with existing symbol in '{file_path}', skipping.")
                                else:
                                    new_sym = self._create_symbol_from_member(local_name, target_member)
                                    if new_sym:
                                        analyzer.symbol_table.define(new_sym)
                                    else:
                                        analyzer.issue_tracker.report(
                                            Severity.ERROR, SEM_UNDEFINED_SYMBOL,
                                            f"Symbol '{alias.name}' in module '{imp.module_name}' has an unresolved type",
                                            location=Location(file_path=file_path, line=imp.lineno, column=1)
                                        )
                            else:
                                # 符号未找到报错
                                analyzer.issue_tracker.report(
                                    Severity.ERROR, SEM_UNDEFINED_SYMBOL,
                                    f"Symbol '{alias.name}' not found in module '{imp.module_name}'",
                                    location=Location(file_path=file_path, line=imp.lineno, column=1)
                                )
            
            result = analyzer.analyze(ast_node)
            result.import_star_members = import_star_members
            
            # 语义分析完成后，更新注册表中的元数据成员
            # 这确保了 TypeDef 在解析时能看到完整的符号表
            final_mod_meta = self.registry.resolve(module_name)
            if final_mod_meta:
                final_mod_meta.members = {
                    name: sym for name, sym in result.symbol_table.symbols.items()
                    if sym.provenance != Provenance.KERNEL_NATIVE
                }
            
            # Cache AST, Tokens, and SymbolTable
            self.ast_cache[file_path] = ast_node
            self.symbol_table_cache[file_path] = result.symbol_table
            
            self.ast_cache.move_to_end(file_path)
            self.symbol_table_cache.move_to_end(file_path)
            if file_path in self.token_cache:
                self.token_cache.move_to_end(file_path)
            
            self._prune_cache()
            
            module_info.status = ModuleStatus.COMPILED
            return result
            
        except CompilerError:
            raise
        except Exception as e:
            file_tracker.error(f"Internal compiler error: {str(e)}", code=INT_INTERNAL_ERROR)
            raise CompilerError(file_tracker.diagnostics) from e
        finally:
            self.issue_tracker.merge(file_tracker)
            
        if file_tracker.has_errors():
            raise CompilerError(file_tracker.diagnostics)

    def _create_symbol_from_member(self, name: str, member: Any) -> Optional[Symbol]:
        """
        from-import 符号构造：从 MemberSpec（插件模块）或 Symbol（已编译 IBCI 模块）
        创建可注入当前作用域的 Symbol。

        - MemberSpec / MethodMemberSpec：通过 registry.resolve_typeref 解析类型，
          构造 FunctionSymbol（method）或 VariableSymbol（field）。
        - Symbol（来自已编译模块的 members）：按原始 kind 重建同 kind Symbol。
        """
        if isinstance(member, Symbol):
            if member.kind == SymbolKind.FUNCTION:
                return FunctionSymbol(name=name, kind=SymbolKind.FUNCTION, spec=member.spec, provenance=Provenance.EXTERNAL_MODULE)
            elif member.kind == SymbolKind.VARIABLE:
                return VariableSymbol(name=name, kind=SymbolKind.VARIABLE, spec=member.spec, provenance=Provenance.EXTERNAL_MODULE)
            else:
                return TypeSymbol(name=name, kind=member.kind, spec=member.spec, provenance=Provenance.EXTERNAL_MODULE)

        if isinstance(member, MethodMemberSpec):
            # 构造 FUNCTION kind 的 TypeDef，携带 return_type 和 param_types，
            # 使语义分析器通过 get_call_cap 判定为可调用、通过 return_type 解析返回类型。
            func_spec = ModuleMetadata(
                name=name,
                kind=TypeKind.FUNCTION.value,
                return_type=member.return_type,
                param_types=list(member.param_types),
            )
            func_spec.param_descriptors = list(getattr(member, 'param_descriptors', None) or [])
            return FunctionSymbol(name=name, kind=SymbolKind.FUNCTION, spec=func_spec, provenance=Provenance.EXTERNAL_MODULE)

        if isinstance(member, MemberSpec):
            val_spec = self.registry.resolve_typeref(member.type_ref)
            if val_spec is None:
                val_spec = self.registry.resolve("any")
            return VariableSymbol(name=name, kind=SymbolKind.VARIABLE, spec=val_spec, provenance=Provenance.EXTERNAL_MODULE)

        return None

# DependencyGraph logic moved to core.compiler.dependencies
# This file imports DependencyGraph from there.
