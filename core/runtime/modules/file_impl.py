"""
core/runtime/modules/file_impl.py

Kernel-native IBCI ``file`` 模块实现。

⚠️ 命名红线：本文件实现的是 **IBCI 语言层**的 ``file`` 内核模块，不是 Python 的 ``file``
内建对象（Python 2 内建）。为避免 Python import shadowing，**本文件必须保持
``file_impl.py``，绝对不可重命名为 ``file.py``**。相关守护测试见
``tests/meta/test_layering.py::TestRuntimeModulesNamingRedLine``。

- 提供 IBCI 脚本可见的自由函数：``open/read/read_bytes/write_copy/write_copy_bytes/
  write_overwrite/write_overwrite_bytes/write_new/write_new_bytes/exists/remove``。
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

    def write_copy(
        self,
        source: Union[str, IbFileHandle],
        new_path: str,
        data: str,
    ) -> IbFileHandle:
        """
        Copy-on-write 写入：在 ``new_path`` 创建新文件，写入 ``data``。
        ``source`` 及其所有别名均不受影响。返回指向新文件的只读 handle。
        """
        self._guard_no_file_write_in_retry("write_copy")
        # 校验 source（提供沙箱上下文与 lineage）。
        self._resolve_path(source, operation="read")
        # 解析并校验目标路径。
        dest_ib_path = self.capabilities.execution_context.resolve_path(new_path)
        dest_native = dest_ib_path.to_native()
        self.permission_manager.validate_path(dest_native, operation="write")

        native_data = data.to_native() if hasattr(data, "to_native") else data
        with open(dest_native, "w", encoding="utf-8") as f:
            f.write(native_data)

        return IbFileHandle(
            FileBacking(IbPath.from_native(dest_native), sandboxed=True),
            self._file_handle_class(),
        )

    def write_copy_bytes(
        self,
        source: Union[str, IbFileHandle],
        new_path: str,
        data: Any,
    ) -> IbFileHandle:
        """Copy-on-write 的字节版本。"""
        self._guard_no_file_write_in_retry("write_copy_bytes")
        self._resolve_path(source, operation="read")
        dest_ib_path = self.capabilities.execution_context.resolve_path(new_path)
        dest_native = dest_ib_path.to_native()
        self.permission_manager.validate_path(dest_native, operation="write")

        native_data = data.to_native() if hasattr(data, "to_native") else data
        if isinstance(native_data, list):
            native_data = bytes(native_data)
        with open(dest_native, "wb") as f:
            f.write(native_data)

        return IbFileHandle(
            FileBacking(IbPath.from_native(dest_native), sandboxed=True),
            self._file_handle_class(),
        )

    def write_new(self, new_path: str, data: str) -> IbFileHandle:
        """
        创建/写新文件：在 ``new_path`` 写入 ``data``，返回指向新文件的只读 handle。

        与 ``write_copy`` 不同，本函数不需要 ``source`` 参数，适用于从无到有
        生成一份新工件的场景。若 ``new_path`` 已存在，行为与 Python ``open(path, "w")``
        一致——覆盖原文件；若需保留原文件，请使用 ``write_copy``。

        未来支持命名/可选参数后，``write_overwrite(target, data)`` 在 ``target`` 为路径、
        且未提供 source 上下文时，将等价于 ``write_new(target, data)``。
        """
        self._guard_no_file_write_in_retry("write_new")
        dest_ib_path = self.capabilities.execution_context.resolve_path(new_path)
        dest_native = dest_ib_path.to_native()
        self.permission_manager.validate_path(dest_native, operation="write")

        native_data = data.to_native() if hasattr(data, "to_native") else data
        with open(dest_native, "w", encoding="utf-8") as f:
            f.write(native_data)

        return IbFileHandle(
            FileBacking(IbPath.from_native(dest_native), sandboxed=True),
            self._file_handle_class(),
        )

    def write_new_bytes(self, new_path: str, data: Any) -> IbFileHandle:
        """``write_new`` 的字节版本。"""
        self._guard_no_file_write_in_retry("write_new_bytes")
        dest_ib_path = self.capabilities.execution_context.resolve_path(new_path)
        dest_native = dest_ib_path.to_native()
        self.permission_manager.validate_path(dest_native, operation="write")

        native_data = data.to_native() if hasattr(data, "to_native") else data
        if isinstance(native_data, list):
            native_data = bytes(native_data)
        with open(dest_native, "wb") as f:
            f.write(native_data)

        return IbFileHandle(
            FileBacking(IbPath.from_native(dest_native), sandboxed=True),
            self._file_handle_class(),
        )

    def write_overwrite(self, target: Union[str, IbFileHandle], data: str) -> Any:
        """
        显式副作用写入：覆盖 ``target`` 指向的文件。
        所有共享同一 backing 路径的 handle 都会观察到新内容。
        """
        # llmexcept retry body 中禁用 overwrite 写入，避免污染快照。
        self._guard_no_file_write_in_retry("write_overwrite")
        native_path = self._resolve_path(target, operation="write")
        native_data = data.to_native() if hasattr(data, "to_native") else data
        with open(native_path, "w", encoding="utf-8") as f:
            f.write(native_data)
        return self._registry().get_none()

    def write_overwrite_bytes(self, target: Union[str, IbFileHandle], data: Any) -> Any:
        """显式副作用写入的字节版本。"""
        # llmexcept retry body 中禁用 overwrite 写入。
        self._guard_no_file_write_in_retry("write_overwrite_bytes")
        native_path = self._resolve_path(target, operation="write")
        native_data = data.to_native() if hasattr(data, "to_native") else data
        if isinstance(native_data, list):
            native_data = bytes(native_data)
        with open(native_path, "wb") as f:
            f.write(native_data)
        return self._registry().get_none()

    def exists(self, path: str) -> bool:
        """检查文件是否存在（受沙箱约束）。"""
        try:
            native_path = self._resolve_path(path, operation="read")
            return os.path.exists(native_path)
        except Exception:
            return False

    def remove(self, target: Union[str, IbFileHandle]) -> Any:
        """删除文件（受沙箱约束）。"""
        self._guard_no_file_write_in_retry("remove")
        native_path = self._resolve_path(target, operation="remove")
        if os.path.exists(native_path):
            os.remove(native_path)
        return self._registry().get_none()
