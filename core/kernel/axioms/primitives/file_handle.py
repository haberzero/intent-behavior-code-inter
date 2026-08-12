"""
core/kernel/axioms/primitives/file_handle.py

``file_handle`` 类型的公理声明。

- 零 I/O：不导入 ``os`` / ``base64`` / ``open``；所有文件操作在 runtime 值类中实现。
- 声明 ``storage_model = DISK_BACKED``，使 deep_clone / 序列化器按磁盘协议分发。
- 方法签名仅用于类型系统/编译期校验。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.base.enums import StorageModel
from core.kernel.spec.member import MemberSpec, MethodMemberSpec
from core.kernel.spec.type_ref import TypeRef

from .base import BaseAxiom, _m


class FileHandleAxiom(BaseAxiom):
    """Axiom for the ``file_handle`` type — disk-backed file container."""

    has_payload_prompt_cap = True

    @property
    def name(self) -> str:
        return "file_handle"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            # path 是 field（纯内省，无 I/O）。
            "path": MemberSpec(name="path", kind="field", type_ref=TypeRef.of("str")),
            "read": _m("read", ret="str"),
            "read_bytes": _m("read_bytes", ret="list[int]"),
            # file_handle 实例只读，无 write() 方法。
            "close": _m("close", ret="void"),
            "cast_to": _m("cast_to", params=["any"], ret="any"),
        }

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "file_handle"

    def __payload_prompt__(self, value: Any, spec: Optional[Any] = None) -> Any:
        """Delegating payload prompt — the actual logic lives on the runtime value."""
        return value.receive("__payload_prompt__", [])
