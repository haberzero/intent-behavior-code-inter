"""
core/runtime/frame.py

IBCI 执行帧的 ContextVar 注册中心。

使用 contextvars.ContextVar 而非 threading.local 的原因：
- asyncio Task 创建时自动复制父 Context，协程间天然隔离
- set/reset 原子性（通过 Token 机制）
- 与 Python 生态（FastAPI/Starlette）对齐

这是 IbUserFunction.call() 去除 context 参数依赖的基础设施。
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.base.interfaces import IExecutionFrame
    from core.runtime.interfaces import IExecutionContext

# 当前 IBCI 执行帧寄存器。
# Interpreter.run() / execute_module() 在入口处设置，IbUserFunction.call() 读取。
_current_frame: ContextVar[Optional["IExecutionFrame"]] = ContextVar(
    "ibci_current_frame", default=None
)

# 当前 IBCI 执行上下文（ExecutionContext）寄存器。
#
# ``IbBehavior`` / ``IbFnCallable`` 在定义时捕获 ``_execution_context``
# 字段；跨 Interpreter / 跨线程场景下，定义时刻的 EC 可能与调用时刻的 EC
# 不一致。
#
# 设计语义：
#   - lambda / snapshot / immediate behavior 的调用机制（VM、节点池、副表）
#     总是取**调用现场**的 EC。
#   - 定义时刻的 ``_execution_context`` 字段降级为回退源——仅当当前没有
#     活跃 EC 时才使用。
#
# Interpreter.run() / execute_module() / vm.run() 在入口处设置此变量。
_current_execution_context: ContextVar[Optional["IExecutionContext"]] = ContextVar(
    "ibci_current_execution_context", default=None
)


def get_current_frame() -> Optional["IExecutionFrame"]:
    """获取当前线程/协程的执行帧。如果在 Interpreter 执行上下文之外调用，返回 None。"""
    return _current_frame.get()


def set_current_frame(frame: "IExecutionFrame"):
    """
    设置当前执行帧，返回 Token（用于 reset）。
    调用方应在 finally 中 reset 以保证帧栈正确弹出。
    """
    return _current_frame.set(frame)


def reset_current_frame(token) -> None:
    """重置执行帧到 token 时刻的状态。"""
    _current_frame.reset(token)


def get_current_execution_context() -> Optional["IExecutionContext"]:
    """获取当前线程/协程的执行上下文。

    在 Interpreter 执行循环之外调用返回 None。``IbBehavior.call`` /
    ``IbFnCallable.call`` 应优先使用本函数返回值，仅在为 None 时回退到
    定义时刻捕获的 ``_execution_context`` 字段。
    """
    return _current_execution_context.get()


def set_current_execution_context(ec: "IExecutionContext"):
    """设置当前执行上下文，返回 Token（用于 reset）。

    调用方约定与 ``set_current_frame`` 对称，应在 ``finally`` 中 reset。
    """
    return _current_execution_context.set(ec)


def reset_current_execution_context(token) -> None:
    """重置执行上下文到 token 时刻的状态。"""
    _current_execution_context.reset(token)
