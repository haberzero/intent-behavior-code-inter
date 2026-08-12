"""VM 控制流信号类型（跨子包共享叶子模块）。

此模块位于 ``core/runtime/shared/`` —— 运行时各子包（interpreter / vm / objects）
共享的叶子模块，用于打破 interpreter ↔ vm 和 objects ↔ vm 循环依赖。

包含三类纯控制流信号（stdlib-only，无跨包导入）：
- ``ControlSignal``：控制流信号枚举（RETURN / BREAK / CONTINUE / THROW）
- ``Signal``：显式控制流信号数据对象（frozen dataclass）
- ``UnhandledSignal``：VM 顶层未消费信号的边界异常

帧/调度数据类型（``VMTask``）保留在 ``vm/task.py`` 中，
因为它们仅在 ``vm`` 包内部使用。
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ControlSignal(Enum):
    """控制流信号枚举（公理 EXEC-2）。"""
    RETURN = "return"
    BREAK = "break"
    CONTINUE = "continue"
    THROW = "throw"


@dataclass(frozen=True)
class Signal:
    """显式控制流信号数据对象。

    handler 通过 ``return Signal(kind, value)`` 让任务以 Signal 作为
    ``StopIteration.value`` 结束；调度循环识别后把 Signal 作为
    ``gen.send(Signal)`` 的值传递给父帧的下一个 ``yield``。父 handler
    用 ``isinstance(res, Signal)`` 判断是否为信号并自行处理：

    * 循环 handler 拦截 BREAK/CONTINUE
    * 函数 handler 拦截 RETURN
    * 其他 handler 通过 ``return res`` 透传

    使用 frozen 数据类：因为 Signal 在帧间作为不可变值流转，避免误改。
    """
    kind: ControlSignal
    value: Any = None

    def __repr__(self) -> str:  # pragma: no cover
        return f"Signal({self.kind.value}, {self.value!r})"


class UnhandledSignal(Exception):
    """VM 顶层未消费信号的边界异常。

    ``VMExecutor.run()`` 在帧栈耗尽仍持有未消费 Signal 时以
    ``raise UnhandledSignal(signal)`` 抛给调用方。

    调用方通过 ``e.signal.kind`` 判断信号类型（ControlSignal 枚举），
    通过 ``e.signal.value`` 获取关联值。

    VM 内部不使用本异常跨帧传播；handler 必须使用 ``return Signal(...)``
    数据形式触发信号。
    """
    __slots__ = ("signal",)

    def __init__(self, signal: "Signal"):
        super().__init__(f"UnhandledSignal({signal.kind.value})")
        self.signal = signal


class GeneratorYield:
    """惰性生成器产出值标记（阶段 5 yield）。

    ``vm_handle_IbYieldExpr`` 对 ``yield x`` 求值后 ``yield`` 本对象（而非
    child uid），生成器驱动循环识别后：暂停生成器体、交付值 ``value`` 给迭代方；
    迭代恢复后 ``send`` 回驱动循环继续推进。与 ``Waitable``（宿主等待）区分——
    本对象是**语言级生成器产出**，非异步等待。
    """

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value
