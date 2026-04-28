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
M3b 的核心改动：控制流不再依赖 Python 异常 (``ControlSignalException``)
跨帧传播，而是用 :class:`Signal` 数据对象作为生成器协程的 **返回值**
（即 ``StopIteration.value``）显式传递。调度循环识别 ``Signal`` 类型
的任务结果，沿帧栈数据化向上传递（通过 ``gen.send(Signal)``），由
循环帧 / 函数帧的 handler 通过 ``isinstance(res, Signal)`` 检查显式
拦截或继续传播。

仅在以下两种情况下仍会出现 :class:`ControlSignalException`：

1. **顶层未消费 Signal**：``VMExecutor.run()`` 帧栈空且仍持有未消费的
   Signal 时，包装为 ``ControlSignalException`` 抛给调用者（保持与旧
   行为兼容，便于 ``break`` 顶层裸 break 测试与外部 try/except 集成）
2. **fallback 路径**：当 VM 回退到 ``execution_context.visit(uid)``
   时，旧路径仍可能抛出 ``ReturnException`` / ``BreakException``
   等 Python 原生异常。调度器照常以 ``Exception`` 通用路径捕获 + 沿
   生成器栈 ``throw`` 给父帧（保持向后兼容直至 M3d 主路径切换）。
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


class ControlSignalException(Exception):
    """控制流信号的边界封装（M3b 后仅用于 VM 顶层与 fallback 路径）。

    用途：
    1. ``VMExecutor.run()`` 在帧栈耗尽仍持有未消费 Signal 时包装抛出
    2. 旧递归 ``Interpreter.visit()`` fallback 路径中的兼容入口
    3. 现有测试 ``pytest.raises(ControlSignalException)`` 的契约保持

    M3b 起，VM **内部**不再用本异常跨帧传播；handler 必须使用
    ``return Signal(...)`` 数据形式触发信号。
    """
    __slots__ = ("signal", "value")

    def __init__(self, signal: ControlSignal, value: Any = None):
        super().__init__(f"ControlSignal({signal.value})")
        self.signal = signal
        self.value = value

    @classmethod
    def from_signal(cls, sig: "Signal") -> "ControlSignalException":
        return cls(sig.kind, sig.value)


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
      * raise ControlSignalException —— 已废弃路径（M3b 之前）；仍兼容
                                     fallback 旁路抛出的 Python 原生
                                     ReturnException 等
    """
    node_uid: str
    generator: Any = None
    # task-local 元数据；M3a 暂未启用（保留供 M3b/M3c 扩展，例如 LLMExceptTask 的
    # snapshot 字段、FunctionCallFrame 的 expected_signal 字段等）。
    locals: dict = field(default_factory=dict)
