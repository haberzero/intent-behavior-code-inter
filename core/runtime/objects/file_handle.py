"""
core/runtime/objects/file_handle.py

IBCI ``file_handle`` 运行时实现。

设计要点
--------
- ``IbFileHandle`` 是**路径引用身份对象**，不是 Python 的有状态 fd 流对象。
- 不持有 OS fd，不维护游标；可序列化、可深拷贝、可快照。
- 所有 FS I/O 都发生在 runtime 层协议方法中；kernel axiom 层零 I/O。
- 通过 ``storage_model = DISK_BACKED`` 让 deep_clone / RuntimeSerializer
  走磁盘协议族（浅拷贝路径引用、序列化路径描述符）。
"""

from __future__ import annotations

import base64
from typing import Any, Dict

from core.base.enums import StorageModel
from core.base.path import IbPath
from core.kernel.path import PathValidator
from core.kernel.issue import InterpreterError

from .ib_type_mapping import register_ib_type, get_ib_implementation
from .kernel import IbValue, IbClass
from .media_backing import FileBacking, GeneratedBacking, MediaBacking


@register_ib_type("file_handle")
class IbFileHandle(IbValue):
    """
    ``file_handle`` 类型的 IBCI 运行时对象。

    持有一个 ``MediaBacking``（路径引用），并通过磁盘协议族参与
    deep_clone、序列化、LLM payload 构建与快照恢复。
    """

    __slots__ = ()

    def __init__(self, backing: MediaBacking, ib_class: IbClass):
        super().__init__(ib_class, payload=backing)
        # path 是 field，无 I/O。
        self.fields["path"] = ib_class.registry.box(backing.path.to_native())

    @property
    def backing(self) -> MediaBacking:
        """返回底层 ``MediaBacking``（路径引用）。"""
        return self.payload

    def _permission_manager(self) -> Any:
        """从 registry 获取当前 ExecutionContext 的 PermissionManager。"""
        ctx = self.ib_class.registry.get_execution_context()
        if ctx is None:
            return None
        return getattr(ctx, "permission_manager", None)

    def _validate_path(self, operation: str = "read") -> None:
        """所有 I/O 前必须经过 PermissionManager 沙箱校验。"""
        pm = self._permission_manager()
        if pm is None:
            raise InterpreterError(
                f"file_handle: no PermissionManager available for {operation} "
                f"on {self.backing.path}"
            )
        pm.validate_path(self.backing.path.to_native(), operation)

    # ------------------------------------------------------------------ #
    # 磁盘协议族（与 ``__prompt__`` 族平行，通过 receive() 分发）          #
    # ------------------------------------------------------------------ #

    def __materialize__(self) -> bytes:
        """惰性物化：从 backing 路径读取原始字节。"""
        self._validate_path("read")
        path = self.backing.path.to_native()
        with open(path, "rb") as f:
            return f.read()

    def __path_payload_prompt__(self) -> Dict[str, Any]:
        """从路径构建 LLM payload（通用 file_handle 的文本回退）。"""
        return {
            "type": "text",
            "text": f"[file_handle: {self.backing.path}]",
        }

    def __clone_ref__(self) -> "IbFileHandle":
        """深拷贝时复制路径引用，不物化字节。"""
        return type(self)(self.backing, self.ib_class)

    def __to_descriptor__(self) -> Dict[str, Any]:
        """序列化为可跨 isolation 重建的路径描述符。"""
        backing = self.backing
        return {
            "path": backing.path.to_native(),
            "backing_type": "file" if isinstance(backing, FileBacking) else "generated",
        }

    def __from_descriptor__(self, descriptor_obj: Any) -> "IbFileHandle":
        """从路径描述符重建 FileHandle（由 RuntimeDeserializer 调用）。

        作为类级别协议方法注册：运行时调用 ``audio.__from_descriptor__(descriptor)``
        时 ``self`` 为 ``IbClass``；因此返回的实例类型由 ``self`` 决定。
        """
        descriptor = descriptor_obj.to_native() if hasattr(descriptor_obj, "to_native") else descriptor_obj
        path = IbPath.from_native(descriptor["path"])
        backing_type = descriptor.get("backing_type", "file")
        backing: MediaBacking = (
            FileBacking(path) if backing_type == "file" else GeneratedBacking(path)
        )
        ib_class = self if isinstance(self, IbClass) else self.ib_class
        impl_cls = get_ib_implementation(ib_class.name) or IbFileHandle
        return impl_cls(backing, ib_class)

    # ------------------------------------------------------------------ #
    # 用户可见原生方法                                                      #
    # ------------------------------------------------------------------ #

    def read(self) -> str:
        """以文本模式读取文件内容。"""
        self._validate_path("read")
        with open(self.backing.path.to_native(), "r", encoding="utf-8") as f:
            return f.read()

    def read_bytes(self) -> Any:
        """读取文件字节并返回 ``list[int]``（IBCI 可装箱类型）。"""
        data = self.__materialize__()
        return self.ib_class.registry.box(list(data))

    def close(self) -> Any:
        """FileHandle 不持有 fd，close 为无操作语义占位。"""
        return self.ib_class.registry.get_none()

    def to_native(self, memo=None) -> Any:
        """返回 backing 路径字符串，供调试/可观测性使用。"""
        return self.backing.path.to_native()

    def to_bool(self) -> Any:
        return self.ib_class.registry.box(True)

    def __repr__(self) -> str:
        return f"<{self.ib_class.name} handle {self.backing}>"
