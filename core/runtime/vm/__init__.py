"""
core.runtime.vm — VM Executor (CPS Scheduling Loop)
====================================================

M3a (Step 9a) 骨架实现：使用显式帧栈调度循环替代 Python 递归栈进行 IBCI AST 求值。

核心组成
--------
* :class:`VMTask`           —— 单个调度单元（包装一个生成器协程）
* :class:`VMTaskResult`     —— 调度结果数据对象（DONE/SUSPEND/SIGNAL，M3a 阶段为标记类型）
* :class:`ControlSignal`    —— 控制流信号枚举（return/break/continue/throw）
* :class:`VMExecutor`       —— 调度循环主类，维护显式 ``frame_stack``

设计说明
--------
M3a 阶段实现采用 **基于 Python 生成器的 trampoline 调度** ：每个支持的 AST 节点
对应一个 generator function，节点之间通过 ``yield child_uid`` 让出控制权，
trampoline 主循环负责在帧栈上压入新任务、传递结果、传播控制流信号。

这与"显式帧栈"在语义上完全等价（生成器对象即帧），但 Python 实现层面更紧凑。
M3b 将把控制信号从 Python 异常迁移到显式 ``ControlSignal`` 数据传递；M3c 将把
``LLMExceptFrame`` retry 循环纳入调度器；M3d 将把 ``Interpreter.visit()`` 主路径
切换到本执行器。

VMExecutor 是 ``Interpreter.visit()`` 的**并行路径**，不替换原有递归实现。
未实现的节点类型自动回退到 ``execution_context.visit(uid)``，确保完整程序仍能
正确执行（M3a 范围内）。
"""
from core.runtime.vm.task import (
    VMTask,
    VMTaskResult,
    ControlSignal,
    ControlSignalException,
    Signal,
)
from core.runtime.vm.vm_executor import VMExecutor

__all__ = [
    "VMTask",
    "VMTaskResult",
    "ControlSignal",
    "ControlSignalException",
    "Signal",
    "VMExecutor",
]
