"""
core.runtime.vm.task — VM 调度单元与控制信号定义。

VMTask
------
* ``node_uid``  —— 当前帧对应的 AST 节点 uid
* ``generator`` —— Python 生成器协程，按 yield 协议表达节点求值的连续性

Signal 控制信号语义
------------------
控制流不再依赖 Python 异常跨帧传播，而是用
:class:`Signal` 数据对象作为生成器协程的 **返回值**
（即 ``StopIteration.value``）显式传递。调度循环识别 ``Signal`` 类型
的任务结果，沿帧栈数据化向上传递（通过 ``gen.send(Signal)``），由
循环帧 / 函数帧的 handler 通过 ``isinstance(res, Signal)`` 检查显式
拦截或继续传播。

:class:`UnhandledSignal` 是唯一的边界异常：仅在 ``VMExecutor.run()``
帧栈空且仍持有未消费的 Signal 时抛出，调用方（IbUserFunction.call、
execute_module）捕获后按 ``e.signal.kind`` 分类处理。

注：``ControlSignal`` / ``Signal`` / ``UnhandledSignal`` 定义在
``core/runtime/shared/signals.py`` 中，此处重新导出供 vm 包内
``from core.runtime.vm.task import ControlSignal`` 使用。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

# 控制流信号类型从 shared/ 叶子模块导入并重新导出，
# 保持 vm 包内部 ``from core.runtime.vm.task import ControlSignal`` 可用。
from core.runtime.shared.signals import (
    ControlSignal,
    Signal,
    UnhandledSignal,
)


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
    # task-local 元数据（保留供扩展，例如 LLMExceptTask 的
    # snapshot 字段、FunctionCallFrame 的 expected_signal 字段等）。
    locals: dict = field(default_factory=dict)
