"""``llm_executor`` 包 —— LLM 执行核心 (mixin 组合)。

通过 mixin 组合为最终的 :class:`LLMExecutorImpl`：

- :class:`LLMExecutorCore` (``_core``)         —— 共享状态、属性、类型栈、``_call_llm``
- :class:`_PromptMixin` (``_prompt``)          —— 提示词构建与结果解析（CPS 唯一实现 + 同步泵）
- :class:`_SchedulerMixin` (``_scheduler``)    —— ``dispatch_eager_cps``（CPS 权威）/ ``resolve`` / 线程池
- :class:`_LLMFunctionMixin` (``_llm_function``) —— 命名 LLM 函数执行 (CPS)
- :class:`_BehaviorMixin` (``_behavior``)       —— behavior 表达式执行 (CPS + 同步薄包装)

``LLMExecutorImpl`` 继承顺序 (MRO) 保证 :class:`LLMExecutorCore` 的 ``__init__``
成为唯一构造器，各 mixin 仅贡献方法。对外保持 ``from core.runtime.interpreter.llm_executor
import LLMExecutorImpl`` 不变。
"""

from ._core import LLMExecutorCore
from ._prompt import _PromptMixin
from ._scheduler import _SchedulerMixin
from ._llm_function import _LLMFunctionMixin
from ._behavior import _BehaviorMixin


class LLMExecutorImpl(_BehaviorMixin, _LLMFunctionMixin, _SchedulerMixin, _PromptMixin, LLMExecutorCore):
    pass


__all__ = ["LLMExecutorImpl"]
