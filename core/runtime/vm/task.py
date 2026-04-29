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

Signal 控制信号语义（M3b 起）
----------------------------
M3b 的核心改动：控制流不再依赖 Python 异常跨帧传播，而是用
:class:`Signal` 数据对象作为生成器协程的 **返回值**
（即 ``StopIteration.value``）显式传递。调度循环识别 ``Signal`` 类型
的任务结果，沿帧栈数据化向上传递（通过 ``gen.send(Signal)``），由
循环帧 / 函数帧的 handler 通过 ``isinstance(res, Signal)`` 检查显式
拦截或继续传播。

:class:`UnhandledSignal` 是唯一的边界异常（C5）：仅在 ``VMExecutor.run()``
帧栈空且仍持有未消费的 Signal 时抛出，调用方（IbUserFunction.call、
execute_module）捕获后按 ``e.signal.kind`` 分类处理。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ControlSignal(Enum):
    """控制流信号枚举（公理 CF-1）。"""
    RETURN = "return"
    BREAK = "break"
    CONTINUE = "continue"
    THROW = "throw"


@dataclass(frozen=True)
class Signal:
    """显式控制流信号数据对象（M3b）。

    handler 通过 ``return Signal(kind, value)`` 让任务以 Signal 作为
    ``StopIteration.value`` 结束；调度循环识别后把 Signal 作为
    ``gen.send(Signal)`` 的值传递给父帧的下一个 ``yield``。父 handler
    用 ``isinstance(res, Signal)`` 判断是否为信号并自行处理：

    * 循环 handler 拦截 BREAK/CONTINUE
    * 函数 handler（M3c/M3d 启用）拦截 RETURN
    * 其他 handler 通过 ``return res`` 透传

    使用 frozen 数据类：因为 Signal 在帧间作为不可变值流转，避免误改。
    """
    kind: ControlSignal
    value: Any = None

    def __repr__(self) -> str:  # pragma: no cover
        return f"Signal({self.kind.value}, {self.value!r})"


class UnhandledSignal(Exception):
    """VM 顶层未消费信号的边界异常（C5）。

    ``VMExecutor.run()`` 在帧栈耗尽仍持有未消费 Signal 时以
    ``raise UnhandledSignal(signal)`` 抛给调用者。

    调用方通过 ``e.signal.kind`` 判断信号类型（ControlSignal 枚举），
    通过 ``e.signal.value`` 获取关联值。

    VM 内部不使用本异常跨帧传播；handler 必须使用 ``return Signal(...)``
    数据形式触发信号。
    """
    __slots__ = ("signal",)

    def __init__(self, signal: "Signal"):
        super().__init__(f"UnhandledSignal({signal.kind.value})")
        self.signal = signal


@dataclass
class VMTaskResult:
    """调度结果数据对象。

    M3a 中作为标记类型供文档与未来 M3b 复用；M3b 起 SIGNAL 形态由
    :class:`Signal` 数据对象在生成器返回值中直接承担，本数据类仍保
    留作为公开类型标签（含 ``DONE`` / ``SUSPEND`` / ``SIGNAL``）。
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
      * return value              —— 完成（``StopIteration.value``）；若
                                     value 是 :class:`Signal`，则视为
                                     控制流信号沿帧栈数据化向上传播
    """
    node_uid: str
    generator: Any = None
    # task-local 元数据；M3a 暂未启用（保留供 M3b/M3c 扩展，例如 LLMExceptTask 的
    # snapshot 字段、FunctionCallFrame 的 expected_signal 字段等）。
    locals: dict = field(default_factory=dict)
