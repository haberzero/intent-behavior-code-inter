"""
LLM 异步任务支持模块

最小可行层（MVP），为未来真正的多线程/async 支持做准备。
详见 llm_tasks.py 中的妥协说明。
"""
from .llm_tasks import (
    TaskState,
    LLMTaskResult,
    LLMTask,
    LLMTaskPool,
    create_task_pool,
)

__all__ = [
    "TaskState",
    "LLMTaskResult",
    "LLMTask",
    "LLMTaskPool",
    "create_task_pool",
]
