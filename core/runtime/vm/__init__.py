"""
core.runtime.vm — VM Executor (CPS Scheduling Loop)
====================================================

IBCI AST 求值的主执行引擎，基于 Python 生成器实现的 trampoline 调度循环。

核心组成
--------
* :class:`VMTask`           —— 单个调度单元（包装一个生成器协程）
* :class:`VMTaskResult`     —— 调度结果数据对象（DONE/SUSPEND/SIGNAL）
* :class:`ControlSignal`    —— 控制流信号枚举（return/break/continue/throw）
* :class:`VMExecutor`       —— 调度循环主类，维护显式 ``frame_stack``

设计说明
--------
每个支持的 AST 节点对应一个 generator function，节点之间通过 ``yield child_uid``
让出控制权，trampoline 主循环负责在帧栈上压入新任务、传递结果、传播控制流信号。

生成器对象即帧（与"显式帧栈"在语义上完全等价），但 Python 实现层面更紧凑。
控制流（return/break/continue）通过 :class:`Signal` 数据对象沿帧栈传递，不依赖
Python 异常。``LLMExceptFrame`` retry 循环通过 ``vm_handle_IbFor`` 内联实现。

CPS dispatch table 覆盖全部 43 种 AST 节点类型（M3a–M3d + Phase 1–4 完成），
``Interpreter.execute_module()`` 和 ``IbUserFunction.call()`` 均以本执行器
为主路径。原有递归路径仅作为极端边角情形的兜底保留（如 vm=None 的边角测试）。
"""
from core.runtime.vm.task import (
    VMTask,
    VMTaskResult,
    ControlSignal,
    UnhandledSignal,
    Signal,
)
from core.runtime.vm.vm_executor import VMExecutor

__all__ = [
    "VMTask",
    "VMTaskResult",
    "ControlSignal",
    "UnhandledSignal",
    "Signal",
    "VMExecutor",
]
