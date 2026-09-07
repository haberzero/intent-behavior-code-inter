from typing import Any
from ..kernel import IbObject, IbValue
from ..ib_type_mapping import register_ib_type
from core.kernel.issue import InterpreterError

@register_ib_type("Exception")
class IbException(IbValue):
    """Exception 类型的运行时实现"""

    def message(self) -> IbObject:
        msg = self.fields.get("message")
        if msg: return msg
        return self.ib_class.registry.box("")

    def __to_prompt__(self) -> str:
        """字符串化渲染：`<类型名>: <message>`（用户/LLM 视角一致）。

        异常值对象的 message 字段即人类可读描述；无消息时只渲染类型名
        （非默认 fallback ``<Instance of T>``——后者丢失类型语义之外的
        一切信息）。经 str(e)（类调用 __call__ 的 __to_prompt__ 通道）
        与 prompt 渲染两条路径共用（单一渲染契约）。
        """
        msg = self.fields.get("message")
        text = ""
        if isinstance(msg, IbObject):
            text = msg.to_native()
        elif msg is not None:
            text = str(msg)
        return f"{self.ib_class.name}: {text}" if text else self.ib_class.name

    def cast_to(self, target_class: Any) -> IbObject:
        """支持 Exception 的强转逻辑（仅 str/any；其余目标 fail-fast）。

        无法转换时显式报错而非静默返回自身——静默回落会让 `int(e)`
        拿到异常对象本身（类型谎言），违反 fail-fast 优于静默回退纪律
        （与通用 cast_to 转换链的无法转换即报错行为同构）。
        """
        if target_class.name in ("str", "any"):
            msg = self.fields.get("message")
            if msg: return msg
            return self.ib_class.registry.box("Exception")
        raise InterpreterError(
            f"TypeError: Cannot cast 'Exception' to '{target_class.name}': "
            f"only str/any conversion is supported.",
            error_code="RUN_TYPE_MISMATCH",
        )
