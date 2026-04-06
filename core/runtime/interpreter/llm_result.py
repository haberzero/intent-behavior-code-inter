from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.runtime.objects.kernel import IbObject

@dataclass
class LLMResult:
    """
    LLM 执行结果的显式返回类型。

    替代传统的异常机制，提供清晰的成功/失败状态区分。

    字段说明:
    - success: 执行是否成功完成
    - is_uncertain: LLM 返回结果是否不确定/无法解析
    - value: 成功时的返回值
    - error_message: 错误信息（如果有）
    - raw_response: LLM 的原始回复
    - retry_hint: 重试提示（如果 is_uncertain=True）
    """
    success: bool = False
    is_uncertain: bool = False
    value: Optional['IbObject'] = None
    error_message: Optional[str] = None
    raw_response: str = ""
    retry_hint: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """执行成功且结果确定"""
        return self.success and not self.is_uncertain

    def unwrap(self) -> 'IbObject':
        """获取返回值，假设已成功"""
        if not self.success:
            raise RuntimeError(f"Cannot unwrap failed result: {self.error_message}")
        if self.value is None:
            from core.runtime.objects.builtins import IbNone
            return IbNone()
        return self.value

    @staticmethod
    def success_result(value: Optional['IbObject'] = None, raw_response: str = "") -> 'LLMResult':
        """创建成功结果"""
        return LLMResult(
            success=True,
            is_uncertain=False,
            value=value,
            raw_response=raw_response
        )

    @staticmethod
    def uncertain_result(raw_response: str, retry_hint: Optional[str] = None) -> 'LLMResult':
        """创建不确定结果"""
        return LLMResult(
            success=True,
            is_uncertain=True,
            value=None,
            raw_response=raw_response,
            retry_hint=retry_hint
        )

    @staticmethod
    def error_result(error_message: str) -> 'LLMResult':
        """创建错误结果"""
        return LLMResult(
            success=False,
            is_uncertain=False,
            error_message=error_message
        )
