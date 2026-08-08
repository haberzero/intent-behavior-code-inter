"""用户函数调用请求（R1 trampoline 共享标记类型）。

本模块位于 ``core/runtime/shared/`` —— 运行时各子包（vm / interpreter / objects）
共享的叶子模块。``UserFunctionCall`` 是跨模块共享的**协议类型**（与
``shared/signals.py`` 的 ``Signal`` 同类）：由 handler 层（``vm/handlers/leaf.py``
的 ``vm_handle_IbCall``）对 :class:`IbUserFunction` 调用 yield 本对象，VM 调度循环
（``vm_executor.py``）与线程体驱动（``coordinator.py``）识别后把函数体作为独立
VMTask 压栈（而非 ``yield from`` 生成器嵌套），使函数体生成器挂起时不在 Python
栈上——深递归 Python 深度恒定（EXEC-1）。

定义在此（而非 vm_executor 内部）是为避免 handler/线程体向上依赖 VMExecutor
内部类，保持"handler 是叶子、VMExecutor 调度"的分层方向。
"""

from __future__ import annotations


class UserFunctionCall:
    """用户函数调用请求（R1 trampoline 共享标记类型）。

    ``vm_handle_IbCall`` 对 :class:`IbUserFunction` 调用 yield 本对象，
    VMExecutor 调度循环 / 线程体驱动识别后把函数体作为独立 VMTask 压栈
    （而非 ``yield from`` 生成器嵌套），使函数体生成器挂起时不在 Python
    栈上——深递归 Python 深度恒定（EXEC-1）。
    """

    __slots__ = ("func", "args", "receiver")

    def __init__(self, func, args, receiver=None):
        self.func = func
        self.args = args
        self.receiver = receiver