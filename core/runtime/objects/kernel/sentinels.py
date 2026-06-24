from typing import Optional, Dict, Any, List

from ..ib_type_mapping import register_ib_type
from .base import IbObject, IbValue


class IbNone(IbValue):
    """
    IBC-Inter 的空对象 (None)。
    现在通过 Registry 获取单例。
    """
    def __init__(self, ib_class: 'IbClass'):
        super().__init__(ib_class, payload=None)

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        if message == '__eq__':
            right = args[0] if args else None
            return self.ib_class.registry.box(isinstance(right, IbNone))
        if message == '__ne__':
            right = args[0] if args else None
            return self.ib_class.registry.box(not isinstance(right, IbNone))
        return super().receive(message, args)

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        return None

    def __to_prompt__(self) -> str:
        return "null"

    def to_bool(self) -> IbObject:
        """ None 始终为 False"""
        return self.ib_class.registry.box(0)

    def cast_to(self, target_class: Any) -> IbObject:
        """ 支持 None 的强转逻辑"""
        if target_class.name == "str":
            return self.ib_class.registry.box("None")
        if target_class.name in ("int", "float"):
            return self.ib_class.registry.box(0)
        if target_class.name == "bool":
            return self.ib_class.registry.box(0)
        return self

    def __repr__(self):
        return "null"


@register_ib_type("llm_uncertain")
class IbLLMUncertain(IbValue):
    """
    表示 LLM 调用重试耗尽后仍无法得到确定结果的特殊值。

    公理类型：llm_uncertain（有独立 IbClass / AxiomSpec，不依附于 None 类型）

    语义：
    - 布尔上下文中为 False（if r: → 不进入分支）
    - to_native 返回 None
    - __to_prompt__ / (str) 强转返回 "uncertain"
    - 可以赋值给任何类型的变量（LLMUncertainAxiom.is_compatible 宽松策略）
    - 不进入异常体系——用户通过 if/while 逻辑主动检测
    """
    def __init__(self, ib_class: 'IbClass'):
        super().__init__(ib_class, payload=None)

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        return None

    def __to_prompt__(self) -> str:
        return "uncertain"

    def to_bool(self) -> IbObject:
        """IbLLMUncertain 在布尔上下文中为 False"""
        return self.ib_class.registry.box(0)

    def cast_to(self, target_class: Any) -> IbObject:
        """支持 IbLLMUncertain 的强转逻辑"""
        if target_class.name == "str":
            return self.ib_class.registry.box("uncertain")
        if target_class.name in ("int", "float"):
            return self.ib_class.registry.box(0)
        if target_class.name == "bool":
            return self.ib_class.registry.box(0)
        return self

    def __repr__(self):
        return "uncertain"


@register_ib_type("llm_call_result")
class IbLLMCallResult(IbValue):
    """
    LLM 调用结果的结构化类型。

    替代 IbLLMUncertain 的"例外特殊对象"模式，使 LLM 调用结果成为
    公理体系中有完整语义的独立类型。

    字段：
    - is_certain: bool      结果是否确定（LLM 返回了可解析的有效值）
    - value: IbObject       确定时的值；不确定时为 IbNone
    - raw_response: str     LLM 原始响应（用于 retry_hint 生成）
    - retry_hint: str       不确定时的重试提示（传递给下一次 LLM 调用）

    语义：
    - is_certain=True  → 调用成功，value 包含有效 IbObject
    - is_certain=False → 调用不确定，retry_hint 描述问题，llmexcept 应处理此情况

    与 IbLLMUncertain 的关系：
    - IbLLMUncertain 仍是变量赋值"不确定值"的标记类型（保持不变）
    - IbLLMCallResult 是 llmexcept 保护块的"调用结果容器"（新增）
    - 未来 llmexcept 可改为接收 IbLLMCallResult 而非捕获异常
    """
    def __init__(self, ib_class: 'IbClass', is_certain: bool, value: Optional['IbObject'] = None,
                 raw_response: str = "", retry_hint: str = ""):
        super().__init__(
            ib_class,
            payload=value,
            meta={
                "is_certain": is_certain,
                "raw_response": raw_response,
                "retry_hint": retry_hint,
            },
        )
        self.is_certain = is_certain
        self.result_value = value
        self.raw_response = raw_response
        self.retry_hint = retry_hint

    def to_native(self, memo=None) -> Any:
        if self.is_certain and self.result_value is not None:
            return self.result_value.to_native(memo) if hasattr(self.result_value, 'to_native') else self.result_value
        return None

    def __to_prompt__(self) -> str:
        if self.is_certain:
            return f"LLMCallResult(certain, value={self.result_value})"
        return f"LLMCallResult(uncertain, hint={self.retry_hint!r})"

    def __repr__(self) -> str:
        status = "certain" if self.is_certain else "uncertain"
        return f"<LLMCallResult {status}: {self.result_value if self.is_certain else self.retry_hint!r}>"
