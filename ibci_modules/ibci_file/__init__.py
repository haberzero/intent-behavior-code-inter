"""
File 文件操作插件

纯 Python 实现，零侵入。
最小版本暂时绕过 permission_manager。
"""
import os


class FileLib:
    """
    File 2.2: 文件操作插件。
    具备基准路径解析能力，支持位置无关代码。
    """
    def setup(self, capabilities):
        self.capabilities = capabilities
        # 统一通过权限管理器校验路径，强制执行沙箱规则
        self.permission_manager = capabilities.service_context.permission_manager

    def _resolve_path(self, path: str) -> str:
        """
        核心路径解析逻辑。
        - 绝对路径：直接校验权限并使用。
        - 以 ./ 或 ../ 开头：基于当前 IBCI 脚本所在目录解析。
        - 裸路径：基于当前工作目录 (CWD) 解析。
        """
        if os.path.isabs(path):
            self.permission_manager.validate_path(path)
            return path
            
        # 1. 相对脚本路径支持 (Position-Independent Code)
        if path.startswith("./") or path.startswith("../"):
            script_dir = self.capabilities.stack_inspector.get_current_script_dir()
            if script_dir:
                abs_path = os.path.normpath(os.path.join(script_dir, path))
                self.permission_manager.validate_path(abs_path)
                return abs_path
        
        # 2. 传统相对路径支持 (Backward Compatibility)
        abs_path = os.path.abspath(path)
        self.permission_manager.validate_path(abs_path)
        return abs_path

    def read(self, path: str) -> str:
        res_path = self._resolve_path(path)
        with open(res_path, 'r', encoding='utf-8') as f:
            return f.read()

    def write(self, path: str, content: str) -> None:
        res_path = self._resolve_path(path)
        with open(res_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def exists(self, path: str) -> bool:
        try:
            res_path = self._resolve_path(path)
            return os.path.exists(res_path)
        except:
            return False

    def remove(self, path: str) -> None:
        try:
            res_path = self._resolve_path(path)
            if os.path.exists(res_path):
                os.remove(res_path)
        except:
            pass


def create_implementation():
    return FileLib()
