"""
[IES 2.2] File 文件操作插件

纯 Python 实现，零侵入。
最小版本暂时绕过 permission_manager。
"""
import os


class FileLib:
    """
    [IES 2.2] File 2.2: 文件操作插件。
    不继承任何核心类，完全独立。
    最小版本：暂时不做沙箱路径验证。
    """
    def read(self, path: str) -> str:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def write(self, path: str, content: str) -> None:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def exists(self, path: str) -> bool:
        return os.path.exists(path)


def create_implementation():
    return FileLib()
