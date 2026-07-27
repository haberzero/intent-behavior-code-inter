"""
core/kernel/axioms/primitives/media.py

Audio / Image / Video axioms for multimodal LLM behavior expressions.

media 类型是磁盘型 ``file_handle`` 子类。
本公理层只负责声明类型契约与能力标志；所有 I/O（字节物化 / base64）
下放到 runtime 层的 ``__path_payload_prompt__`` 协议方法。
"""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

from core.kernel.axioms.primitives.base import BaseAxiom, _m
from core.kernel.spec.member import MemberSpec, MethodMemberSpec
from core.kernel.spec.type_ref import TypeRef

if TYPE_CHECKING:
    from core.kernel.spec.base import IbSpec


class _MediaAxiomBase(BaseAxiom):
    """audio/image/video 公理的共享基类。"""

    has_payload_prompt_cap = True

    def get_parent_axiom_name(self) -> Optional[str]:
        # media 类型是 file_handle 的磁盘型子类。
        return "file_handle"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            # data 触发 I/O（base64 物化），保持 method；
            # format 从文件名扩展名推导，无 I/O，改为 field。
            "data":     _m("data",     ret="str"),
            "format":   MemberSpec(name="format",   kind="field", type_ref=TypeRef.of("str")),
            "duration": _m("duration", ret="float"),
            "cast_to":  _m("cast_to", params=["any"], ret="any"),
        }

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name == self.name

    def is_compatible(self, other_name: str) -> bool:
        return other_name == self.name

    def __payload_prompt__(self, value: Any, spec: Optional["IbSpec"] = None) -> Any:
        """Delegating payload prompt — actual content block built by the runtime value."""
        if value is None or not hasattr(value, "receive"):
            return {"type": "text", "text": f"[{self.name} data unavailable]"}
        return value.receive("__path_payload_prompt__", [])


class AudioAxiom(_MediaAxiomBase):
    """Axiom for the ``audio`` type — audio data carrier for multimodal LLM calls."""

    @property
    def name(self) -> str:
        return "audio"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        specs = super().get_method_specs()
        # 构造入口：audio.from_file(path)。
        specs["from_file"] = _m("from_file", params=["str"], ret="audio")
        return specs


class ImageAxiom(_MediaAxiomBase):
    """Axiom for the ``image`` type — image data carrier for multimodal LLM calls."""

    @property
    def name(self) -> str:
        return "image"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        specs = super().get_method_specs()
        # width/height 当前占位，未来可能读取图像头，保持 method。
        specs["width"] = _m("width", ret="int")
        specs["height"] = _m("height", ret="int")
        # 构造入口：image.from_file(path)。
        specs["from_file"] = _m("from_file", params=["str"], ret="image")
        return specs


class VideoAxiom(_MediaAxiomBase):
    """Axiom for the ``video`` type — video data carrier for multimodal LLM calls."""

    @property
    def name(self) -> str:
        return "video"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        specs = super().get_method_specs()
        # 构造入口：video.from_file(path)。
        specs["from_file"] = _m("from_file", params=["str"], ret="video")
        return specs
