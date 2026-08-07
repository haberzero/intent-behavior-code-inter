"""多任务协作调度器（统一执行地基 · 阶段 1a：等待策略接入）。

本模块是 VM 多任务化的**执行核心**：管理多个可挂起任务（每个是可挂起生成器），
在单线程内轮转推进，当一个任务等待 IO（waitable）时挂起、让出给其它任务。

任务契约（生成器）：
- ``yield waitable`` —— 挂起，等待 ``waitable`` 就绪（调度器就绪后 ``send(result)`` 恢复）
- ``return value``    —— 完成（``StopIteration.value``）

等待策略（阶段 1a）：
- 每轮推进：先恢复就绪的等待任务（poll ``is_done``），再推进就绪任务；
- 无就绪但有待决任务时 **park**（短睡眠）后重新轮询。

帧数控制（深递归友好）：
- ``run`` 循环**内联**推进与恢复逻辑（不拆 ``_advance``/``_step`` 方法）——用户函数递归
  调用每层经 ``run_body → run → scheduler.run`` 嵌套，方法帧会推高 Python 递归栈；
  内联使每层帧数低于旧 ``_drive_loop`` 路径（EXEC-1 无 Python 递归是目标，函数调用
  路径的 trampoline 化列为阶段 1 后续工作项，本阶段先保证不劣于基线）。

设计原则：
- 生成器本身就是可挂起状态（yield=挂起、send=恢复），无需额外帧快照协议。
- 单线程协作式，无锁；是 VM 主路径（``run``/``run_many``）与线程体（阶段 1e）的公共地基。
- 目的：**服务 LLM 调用**（IO 密集，等待释放 GIL）。受 Python GIL 限制，不追求
  CPU 并行或通用并发框架——本调度器只做多路 LLM IO 的协作式推进。

与现有 ``control.ControlSignal`` 的关系：本模块先用纯 waitable 契约表达挂起，
不引入新的控制流信号；后续语言级 async/await 再在其上构建显式语法。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Generator, List, Optional

from core.runtime.shared.signals import Signal, ControlSignal
from core.runtime.shared.waitable import Waitable

# Waitable 协议定义于叶子模块 core/runtime/shared/waitable.py（避免 vm ↔ host /
# vm ↔ bootstrapper 循环导入）；此处重导出，保持 ``from core.runtime.vm.task_scheduler
# import Waitable`` 的既有导入路径可用。
__all__ = ["Task", "TaskScheduler", "Waitable"]


@dataclass
class Task:
    """调度器中的一个可挂起任务。

    ``index`` 为提交序号（自 0 起），用于把完成值按提交序收集到结果槽位，
    保证 ``run()`` 返回序与提交序一致（而非完成序——完成序不可预测）。

    ``cancelled``：协作取消标志（阶段 1c 接线；先声明字段）。
    """

    gen: Any
    index: int = 0
    node_uid: str = ""
    started: bool = False  # 是否已首次推进（区分 next() 与 send()）
    waiting_on: Optional[Waitable] = None
    cancelled: bool = False


class TaskScheduler:
    """多任务协作调度器。

    用法：``submit(gen)`` 加入任务，``run()`` 推进到全部完成，返回各任务返回值。

    结果序契约：``run()`` 返回的列表**按提交序**（与 ``submit`` 调用顺序一致），
    而非完成序——完成序不可预测，按提交序才使调用方能按索引取回对应任务结果。

    等待策略：poll ``is_done`` + park（无就绪但有等待时短睡眠轮询）。
    ``run`` 循环内联推进/恢复/等待（帧数控制见模块 docstring）。
    """

    def __init__(self, park_interval: float = 0.001):
        self._ready: List[Task] = []
        self._waiting: List[Task] = []
        self._submit_count: int = 0
        self._results: List[Any] = []
        self._park_interval = park_interval

    def submit(self, gen: Generator, node_uid: str = "") -> None:
        task = Task(gen=gen, index=self._submit_count, node_uid=node_uid)
        self._submit_count += 1
        self._results.append(None)  # 预分配结果槽位，按提交序收集
        self._ready.append(task)

    def run(self) -> List[Any]:
        """运行到所有任务完成，返回各任务的完成值（按提交序）。

        循环（帧数内联）：
        1. 恢复就绪的等待任务（waitable ``is_done`` → 回就绪）；
        2. 推进就绪任务（``send`` 一步；yield Waitable → 等待表；完成 → 写结果槽）；
        3. 无就绪但有等待 → park 短睡眠后重新轮询。
        """
        park = self._park_interval
        while self._ready or self._waiting:
            # 1) 等待任务：waitable 就绪 → 回就绪
            still_waiting: List[Task] = []
            for t in self._waiting:
                if t.waiting_on is not None and t.waiting_on.is_done:
                    self._ready.append(t)
                else:
                    still_waiting.append(t)
            self._waiting = still_waiting

            # 2) 推进本轮就绪任务
            still_ready: List[Task] = []
            for t in self._ready:
                try:
                    if not t.started:
                        t.started = True
                        yielded = t.gen.send(None)
                    else:
                        yielded = t.gen.send(t.waiting_on.result() if t.waiting_on else None)
                except StopIteration as si:
                    self._results[t.index] = si.value
                    continue

                # 任务 yield 了一个 waitable → 挂起
                if isinstance(yielded, Waitable):
                    t.waiting_on = yielded
                    if yielded.is_done:
                        still_ready.append(t)  # 已就绪，下一轮立即恢复
                    else:
                        self._waiting.append(t)
                else:
                    # 非 waitable（未知 yield 值）→ fail-fast：任务契约只允许 yield waitable
                    raise RuntimeError(
                        f"TaskScheduler: 任务 yield 了非 waitable 值 {yielded!r}（task={t.node_uid!r}）。"
                        f"任务契约只允许 yield Waitable 或 return 完成值。"
                    )
            self._ready = still_ready

            # 3) 无就绪但有待决 → park 后重新轮询（不得在此消费 result()——
            #    HostAwaitable.result() 消耗性，二次消费会报 Unknown handle）
            if not self._ready and self._waiting:
                time.sleep(park)
        return self._results
