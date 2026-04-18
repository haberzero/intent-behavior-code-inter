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

# 当前 IBCI 执行帧寄存器。
# Interpreter.run() / execute_module() 在入口处设置，IbUserFunction.call() 读取。
_current_frame: ContextVar[Optional["IExecutionFrame"]] = ContextVar(
    "ibci_current_frame", default=None
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
