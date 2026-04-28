"""
core.runtime.vm.task — VM 调度单元与控制信号定义。

VMTask
------
* ``node_uid``  —— 当前帧对应的 AST 节点 uid
* ``generator`` —— Python 生成器协程，按 yield 协议表达节点求值的连续性

VMTaskResult
------------
* DONE(value)         —— 任务完成，值返回给上游帧
* SUSPEND(child_uid)  —— 任务挂起，等待子节点求值完成
* SIGNAL(signal,val)  —— 触发控制流信号（return/break/continue/throw）

M3a 阶段，``VMTaskResult`` 主要作为**类型标记**存在；调度器内部仍依赖
生成器原生协议（``next()`` / ``StopIteration`` / ``throw``）传递结果。
M3b 将把控制流信号从 Python 异常切换为 ``VMTaskResult.SIGNAL`` 显式数据。

ControlSignal / ControlSignalException
--------------------------------------
M3a 中，控制流信号通过 ``ControlSignalException`` 跨帧传播（沿用 Python 异常
机制；M3b 将替换为显式数据传递）。``ControlSignal`` 枚举提供与未来 M3b 兼容
的命名空间。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ControlSignal(Enum):
    """控制流信号枚举（公理 CF-1）。

    M3a 阶段，这些信号通过 :class:`ControlSignalException` 在帧栈中传播；
    M3b 将把它们改为 :class:`VMTaskResult` 数据对象，由调度循环显式拦截。
    """
    RETURN = "return"
    BREAK = "break"
    CONTINUE = "continue"
    THROW = "throw"


class ControlSignalException(Exception):
    """跨帧传播的控制流信号（M3a 过渡实现）。

    生成器协程通过 ``raise ControlSignalException(signal, value)`` 触发；
    调度循环捕获后沿帧栈向上 ``throw`` 给父帧的生成器，由对应处理帧
    （函数帧拦截 RETURN，循环帧拦截 BREAK/CONTINUE）以 ``except`` 子句
    消费。M3b 重写后，本类将仅供旧 ``visit()`` 路径使用。
    """
    __slots__ = ("signal", "value")

    def __init__(self, signal: ControlSignal, value: Any = None):
        super().__init__(f"ControlSignal({signal.value})")
        self.signal = signal
        self.value = value


@dataclass
class VMTaskResult:
    """调度结果数据对象。

    M3a 中作为标记类型供文档与未来 M3b 复用；当前调度循环不强制返回该类型。
    """
    kind: str  # "done" | "suspend" | "signal"
    value: Any = None

    @classmethod
    def DONE(cls, value: Any = None) -> "VMTaskResult":
        return cls("done", value)

    @classmethod
    def SUSPEND(cls, child_uid: str) -> "VMTaskResult":
        return cls("suspend", child_uid)

    @classmethod
    def SIGNAL(cls, signal: ControlSignal, value: Any = None) -> "VMTaskResult":
        return cls("signal", (signal, value))

    @property
    def is_done(self) -> bool:
        return self.kind == "done"

    @property
    def is_suspend(self) -> bool:
        return self.kind == "suspend"

    @property
    def is_signal(self) -> bool:
        return self.kind == "signal"


@dataclass
class VMTask:
    """调度循环中的单个工作单元。

    包装一个 Python 生成器协程，该协程：
      * yield child_uid           —— 挂起，等待 ``child_uid`` 的求值结果
      * return value (StopIteration.value) —— 完成，把 value 传给上游帧
      * raise ControlSignalException —— 触发控制流信号，沿帧栈传播
    """
    node_uid: str
    generator: Any = None
    # task-local 元数据；M3a 暂未启用（保留供 M3b/M3c 扩展，例如 LLMExceptTask 的
    # snapshot 字段、FunctionCallFrame 的 expected_signal 字段等）。
    locals: dict = field(default_factory=dict)
