"""
core/kernel/axioms/primitives/enum.py

Enum axiom for user-defined Enum classes.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

from core.kernel.axioms.primitives.base import BaseAxiom

if TYPE_CHECKING:
    from core.kernel.spec.base import IbSpec


# Mock 哨兵 pass-through：与 core.runtime.shared.llm_result.MOCK_AMBIGUOUS_SENTINEL
# 保持同步（kernel 层禁止依赖 runtime，故此处局部定义大写形式，供 from_prompt 比对）
_MOCK_AMBIGUOUS_SENTINEL_UPPER = "MAYBE_YES_MAYBE_NO_THIS_IS_AMBIGUOUS"


# ------------------------------------------------------------------ #
# enum                                                                #
# ------------------------------------------------------------------ #

class EnumAxiom(BaseAxiom):
    """
    Axiom for user-defined Enum classes.

    Design notes
    ------------
    * ``_enum_index_registry`` is an instance dict (not class-level) to
      eliminate the cross-engine global-state bug from the original design.
    * All type parameters use string names (no IbSpec objects required).
    """

    has_from_prompt_cap = True
    has_output_hint_cap = True
    has_converter_cap = True

    def __init__(self) -> None:
        self._enum_index_registry: Dict[str, Dict[str, str]] = {}

    @property
    def name(self) -> str:
        return "enum"

    def is_class(self) -> bool:
        return True

    def get_parent_axiom_name(self) -> Optional[str]:
        return None

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name == "str"

    def _get_enum_index_map(self, spec: Optional["IbSpec"]) -> Optional[Dict[str, str]]:
        """Build / return the {member_name → member_name} map for the enum."""
        if spec is None:
            return None
        class_name = spec.name
        if class_name in self._enum_index_registry:
            return self._enum_index_registry[class_name]

        members = getattr(spec, "members", None)
        if not members:
            return None

        intrinsic_method_names = {
            "to_bool", "to_list", "len", "cast_to",
            "__getitem__", "__setitem__", "sort", "pop",
            "append", "clear", "__eq__", "__init__",
        }
        name_to_value: Dict[str, str] = {}
        for mname in members:
            if mname.startswith("_") or mname in intrinsic_method_names:
                continue
            name_to_value[mname] = mname

        self._enum_index_registry[class_name] = name_to_value
        return name_to_value

    def __outputhint_prompt__(self, spec: Optional["IbSpec"] = None) -> str:
        index_map = self._get_enum_index_map(spec)
        if not index_map:
            return "Reply with one of the valid enum values."
        return f"Reply with exactly one of: {', '.join(index_map.keys())}."

    def from_prompt(self, raw_response: str, spec: Optional["IbSpec"] = None) -> Tuple[bool, Any]:
        # 契约：入参为原始响应字符串（protocols.py 与全部调用点均传 str）。
        # 非字符串属协议违反——fail-fast 显式暴露，不再做 to_native/receive 双轨
        # 探测或宽 except 静默兜底（unbox 收敛方向）。
        if not isinstance(raw_response, str):
            raise TypeError(
                f"EnumAxiom.from_prompt expects str, got {type(raw_response).__name__}"
            )

        upper = raw_response.upper().strip()
        # MOCK 哨兵值直通
        if upper in (_MOCK_AMBIGUOUS_SENTINEL_UPPER, "1", "0", "TRUE", "FALSE"):
            return (True, raw_response)

        if spec is None:
            return (False, "无法解析枚举值：缺少类型信息")

        index_map = self._get_enum_index_map(spec)
        if not index_map:
            return (False, "无法解析枚举值：缺少成员信息")

        if upper in index_map:
            return (True, upper)

        names = list(index_map.keys())
        preview = ", ".join(names[:5]) + (" 等" if len(names) > 5 else "")
        return (False, f"无法解析 '{raw_response}'，请回复有效枚举值如: {preview}")

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "enum"
