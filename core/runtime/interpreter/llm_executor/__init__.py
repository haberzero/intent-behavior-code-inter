"""``llm_executor`` 包 —— LLM 执行核心 (mixin 组合)。

通过 mixin 组合为最终的 :class:`LLMExecutorImpl`：

- :class:`LLMExecutorCore` (``_core``)         —— 共享状态、属性、类型栈、``_call_llm``
- :class:`_PromptMixin` (``_prompt``)          —— 提示词构建与结果解析（CPS 唯一实现 + 同步泵）
- :class:`_SchedulerMixin` (``_scheduler``)    —— ``dispatch_eager_cps``（CPS 权威）/ ``resolve`` / 线程池
- :class:`_BehaviorMixin` (``_behavior``)       —— behavior 表达式执行 (CPS + 同步薄包装)
- :class:`_LLMCallableMixin` (``_llm_callable``) —— LLMCallable 统一装配与执行

``LLMExecutorImpl`` 继承顺序 (MRO) 保证 :class:`LLMExecutorCore` 的 ``__init__``
成为唯一构造器，各 mixin 仅贡献方法。对外保持 ``from core.runtime.interpreter.llm_executor
import LLMExecutorImpl`` 不变。
"""

from ._core import LLMExecutorCore
from ._prompt import _PromptMixin
from ._scheduler import _SchedulerMixin
from ._behavior import _BehaviorMixin
from ._llm_callable import _LLMCallableMixin


class LLMExecutorImpl(_BehaviorMixin, _LLMCallableMixin, _SchedulerMixin, _PromptMixin, LLMExecutorCore):
    pass


__all__ = ["LLMExecutorImpl"]
