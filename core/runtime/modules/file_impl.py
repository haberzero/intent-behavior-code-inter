"""
core/runtime/modules/file_impl.py

Kernel-native IBCI ``file`` 模块实现。

⚠️ 命名红线：本文件实现的是 **IBCI 语言层**的 ``file`` 内核模块，不是 Python 的 ``file``
内建对象（Python 2 内建）。为避免 Python import shadowing，**本文件必须保持
``file_impl.py``，绝对不可重命名为 ``file.py``**。相关守护测试见
``tests/meta/test_layering.py::TestRuntimeModulesNamingRedLine``。

- 提供 IBCI 脚本可见的自由函数：``open/read/read_bytes/write/exists/remove``。
- 所有 FS I/O 都经过 ``ExecutionContext.resolve_path()`` + ``PermissionManager`` 沙箱校验。
- ``open`` 返回 ``IbFileHandle``（磁盘型 file_handle）；其他函数接受路径字符串或 file_handle。
- 本模块位于 runtime 层，可被 kernel-native 注册流程直接引用。
"""

from __future__ import annotations

import os
from typing import Any, Union

from core.base.path import IbPath
from core.kernel.issue import InterpreterError
from core.runtime.objects.file_handle import IbFileHandle
from core.runtime.objects.media_backing import FileBacking
from core.runtime.objects.kernel.base import unbox


class FileLib:
    """
    ``file`` 模块的核心实现（kernel-native）。

    - 不持有 ``capabilities`` 之外的持久状态；
    - 不实现高级文件分析函数（search/list/size 等），这些留待后续评估；
    - 多模态读取已迁移为 runtime 值类原生能力，本模块不再提供 ``read_audio`` 等；
    - ``file_handle`` 实例只读，写入必须通过本模块的显式函数完成。
    """

    def setup(self, capabilities):
        """插件式注入入口（kernel-native 注册时调用）。"""
        self.capabilities = capabilities
        self.permission_manager = capabilities.service_context.permission_manager

    def _guard_no_file_write_in_retry(self, op_name: str) -> None:
        """llmexcept retry body 内禁止一切文件写/删：磁盘型快照是浅路径引用，
        任何写/删都会污染黄金快照（共享同一 backing 路径）。编译期亦拦 SEM_LLMEXCEPT_FILE_WRITE；
        运行时为兜底（覆盖别名导入/动态分派等编译期漏检情形）。
        """
        if self.capabilities.execution_context.llmexcept_body_depth > 0:
            raise InterpreterError(
                f"file.{op_name} is disabled inside an llmexcept retry body: "
                f"file writes/removes mutate the shared backing and corrupt the retry snapshot. "
                f"Use 'retry \"hint\"' for correction guidance, or perform file I/O outside the handler."
            )

    def _resolve_path(
        self, path: Union[str, IbPath, IbFileHandle], operation: str = "access"
    ) -> str:
        """统一路径解析 + 沙箱校验，返回原生绝对路径字符串。"""
        if isinstance(path, IbPath):
            native = path.to_native()
        elif isinstance(path, IbFileHandle):
            native = path.backing.path.to_native()
        else:
            ib_path = self.capabilities.execution_context.resolve_path(path)
            native = ib_path.to_native()
        self.permission_manager.validate_path(native, operation)
        return native

    def _file_handle_class(self):
        """从 registry 获取 file_handle 类。"""
        return self.capabilities.service_context.registry.get_class("file_handle")

    def _registry(self):
        """从 service_context 获取 registry。"""
        return self.capabilities.service_context.registry

    def open(self, path: str, mode: str = "r") -> IbFileHandle:
        """打开路径并返回 ``file_handle``（不读字节）。"""
        # file_handle 只读，mode 仅允许读模式。
        if mode not in ("", "r", "rb", "rt"):
            raise ValueError(f"file.open: file_handle is read-only; mode={mode!r} not allowed")
        native_path = self._resolve_path(path, operation="read")
        ib_path = IbPath.from_native(native_path)
        return IbFileHandle(FileBacking(ib_path, sandboxed=True), self._file_handle_class())

    def read(self, target: Union[str, IbFileHandle]) -> str:
        """读取文本内容；``target`` 可以是路径或 file_handle。"""
        if isinstance(target, IbFileHandle):
            return target.read()
        native_path = self._resolve_path(target, operation="read")
        with open(native_path, "r", encoding="utf-8") as f:
            return f.read()

    def read_bytes(self, target: Union[str, IbFileHandle]):
        """读取字节并返回 ``list[int]``。"""
        if isinstance(target, IbFileHandle):
            return target.read_bytes()
        native_path = self._resolve_path(target, operation="read")
        with open(native_path, "rb") as f:
            data = f.read()
        return self._registry().box(list(data))

    def write(self, target: Any, data: Any, overwrite_flag: str = "new") -> Any:
        """统一写入接口。

        ``overwrite_flag``：
        - ``"new"``（默认）：``target`` 为路径字符串，创建/覆盖写入（若目标已存在则
          覆盖，等价于 ``open(path, "w")``），返回指向该文件的新 ``file_handle``。
        - ``"overwrite"``：``target`` 为路径或 ``file_handle``，就地覆盖其 backing 文件，
          返回指向该文件的 ``file_handle``。

        ``data`` 为 ``str``（UTF-8 文本）或 ``list[int]``（字节）时自动判别编码模式。
        两模式均返回 ``file_handle``，使模块 spec 的返回类型恒定。
        """
        self._guard_no_file_write_in_retry("write")

        native_data = unbox(data)
        if isinstance(native_data, list):
            native_data = bytes(native_data)
        binary = isinstance(native_data, (bytes, bytearray))

        if overwrite_flag == "new":
            dest_ib_path = self.capabilities.execution_context.resolve_path(target)
            dest_native = dest_ib_path.to_native()
            self.permission_manager.validate_path(dest_native, operation="write")
        elif overwrite_flag == "overwrite":
            dest_native = self._resolve_path(target, operation="write")
        else:
            raise RuntimeError(
                f"file.write: unknown overwrite_flag '{overwrite_flag}' "
                f"(expected 'new' or 'overwrite')"
            )

        if binary:
            with open(dest_native, "wb") as f:
                f.write(native_data)
        else:
            with open(dest_native, "w", encoding="utf-8") as f:
                f.write(native_data)

        return IbFileHandle(
            FileBacking(IbPath.from_native(dest_native), sandboxed=True),
            self._file_handle_class(),
        )

    def exists(self, path: str) -> bool:
        """检查文件是否存在（受沙箱约束）。

        沙箱权限拒绝（InterpreterError）必须传播——降级为 False 会
        把越权访问掩盖成"文件不存在"。
        """
        try:
            native_path = self._resolve_path(path, operation="read")
            return os.path.exists(native_path)
        except (OSError, ValueError):
            return False

    def remove(self, target: Union[str, IbFileHandle]) -> Any:
        """删除文件（受沙箱约束）。"""
        self._guard_no_file_write_in_retry("remove")
        native_path = self._resolve_path(target, operation="remove")
        if os.path.exists(native_path):
            os.remove(native_path)
        return self._registry().get_none()
