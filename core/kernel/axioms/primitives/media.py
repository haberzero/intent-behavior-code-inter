"""
core/kernel/axioms/primitives/media.py

Audio / Image / Video axioms for multimodal LLM behavior expressions.

These axioms enable IBCI's multimodal type system:
- ``audio`` — audio data carrier (wav, mp3, etc.)
- ``image`` — image data carrier (png, jpeg, etc.)
- ``video`` — video data carrier (mp4, webm, etc.)

Each axiom declares ``has_payload_prompt_cap = True`` and implements
``__payload_prompt__`` to return a structured content block for the
LLM API payload (e.g., ``{"type": "input_audio", ...}``).

Per ADR-012, these types are registered as ordinary class names (not
lexer keywords), following the same axiom → builtin_initializer path
as ``Enum``, ``Exception``, and other non-keyword built-in types.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

from core.kernel.axioms.primitives.base import BaseAxiom, _m
from core.kernel.spec.member import MemberSpec, MethodMemberSpec
from core.kernel.spec.type_ref import TypeRef

if TYPE_CHECKING:
    from core.kernel.spec.base import IbSpec


class AudioAxiom(BaseAxiom):
    """Axiom for the ``audio`` type — audio data carrier for multimodal LLM calls.

    ``audio`` variables participate in behavior expressions (``@~ ... $recording ... ~``)
    via ``__payload_prompt__``, which returns an ``input_audio`` content block.
    """

    has_payload_prompt_cap = True

    @property
    def name(self) -> str:
        return "audio"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "data":     MemberSpec(name="data",     kind="field", type_ref=TypeRef.of("str")),
            "format":   MemberSpec(name="format",   kind="field", type_ref=TypeRef.of("str")),
            "duration": MemberSpec(name="duration", kind="field", type_ref=TypeRef.of("float")),
            "cast_to":  _m("cast_to", params=["any"], ret="any"),
        }

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name == "audio"

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "audio"

    def __payload_prompt__(self, value: Any, spec: Optional["IbSpec"] = None) -> Dict[str, Any]:
        """Return an ``input_audio`` content block for the LLM API payload.

        ``value`` is expected to be an ``IbAudio`` instance (or a MediaStorage
        wrapper). The raw audio bytes are base64-encoded per the OpenAI
        audio content block format.
        """
        # Extract media data from the IbAudio value
        storage = _extract_media_storage(value)
        if storage is None:
            return {"type": "text", "text": "[audio data unavailable]"}

        import base64
        b64_data = base64.b64encode(storage.data).decode("ascii")
        return {
            "type": "input_audio",
            "input_audio": {
                "data": b64_data,
                "format": storage.format,
            },
        }


class ImageAxiom(BaseAxiom):
    """Axiom for the ``image`` type — image data carrier for multimodal LLM calls.

    ``image`` variables participate in behavior expressions via ``__payload_prompt__``,
    which returns an ``image_url`` content block with a data URI.
    """

    has_payload_prompt_cap = True

    @property
    def name(self) -> str:
        return "image"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "data":   MemberSpec(name="data",   kind="field", type_ref=TypeRef.of("str")),
            "format": MemberSpec(name="format", kind="field", type_ref=TypeRef.of("str")),
            "width":  MemberSpec(name="width",  kind="field", type_ref=TypeRef.of("int")),
            "height": MemberSpec(name="height", kind="field", type_ref=TypeRef.of("int")),
            "cast_to": _m("cast_to", params=["any"], ret="any"),
        }

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name == "image"

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "image"

    def __payload_prompt__(self, value: Any, spec: Optional["IbSpec"] = None) -> Dict[str, Any]:
        """Return an ``image_url`` content block with a base64 data URI."""
        storage = _extract_media_storage(value)
        if storage is None:
            return {"type": "text", "text": "[image data unavailable]"}

        import base64
        b64_data = base64.b64encode(storage.data).decode("ascii")
        mime_type = storage.mime_type or f"image/{storage.format}"
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{b64_data}",
            },
        }


class VideoAxiom(BaseAxiom):
    """Axiom for the ``video`` type — video data carrier for multimodal LLM calls.

    ``video`` variables participate in behavior expressions via ``__payload_prompt__``,
    which returns a ``video`` content block.
    """

    has_payload_prompt_cap = True

    @property
    def name(self) -> str:
        return "video"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "data":     MemberSpec(name="data",     kind="field", type_ref=TypeRef.of("str")),
            "format":   MemberSpec(name="format",   kind="field", type_ref=TypeRef.of("str")),
            "duration": MemberSpec(name="duration", kind="field", type_ref=TypeRef.of("float")),
            "cast_to":  _m("cast_to", params=["any"], ret="any"),
        }

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name == "video"

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "video"

    def __payload_prompt__(self, value: Any, spec: Optional["IbSpec"] = None) -> Dict[str, Any]:
        """Return a ``video`` content block for the LLM API payload."""
        storage = _extract_media_storage(value)
        if storage is None:
            return {"type": "text", "text": "[video data unavailable]"}

        import base64
        b64_data = base64.b64encode(storage.data).decode("ascii")
        return {
            "type": "video",
            "video": {
                "data": b64_data,
                "format": storage.format,
            },
        }


# ------------------------------------------------------------------ #
# Helper                                                              #
# ------------------------------------------------------------------ #

def _extract_media_storage(value: Any) -> Optional[Any]:
    """Extract a MediaStorage from an IbObject value.

    Handles both IbAudio/IbImage/IbVideo instances (which carry a
    MediaStorage in their payload) and raw MediaStorage objects.
    Returns None if no storage can be extracted.
    """
    # Direct MediaStorage
    if hasattr(value, 'data') and hasattr(value, 'format') and hasattr(value, 'mime_type'):
        return value
    # IbValue with MediaStorage payload
    if hasattr(value, 'payload'):
        payload = value.payload
        if payload is not None and hasattr(payload, 'data'):
            return payload
    # IbValue with to_native returning MediaStorage
    if hasattr(value, 'to_native'):
        try:
            native = value.to_native()
            if hasattr(native, 'data') and hasattr(native, 'format'):
                return native
        except Exception:
            pass
    return None
