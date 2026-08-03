"""多任务协作调度器（Stage 2 异步/协程地基）。

本模块是 VM 多任务化的**独立核心**：管理多个可挂起任务（每个是可挂起生成器），
在单线程内轮转推进，当一个任务等待 IO（waitable）时挂起、让出给其它任务。

任务契约（生成器）：
- ``yield waitable`` —— 挂起，等待 ``waitable`` 就绪（调度器就绪后 ``send(result)`` 恢复）
- ``return value``    —— 完成（``StopIteration.value``）

设计原则：
- 生成器本身就是可挂起状态（yield=挂起、send=恢复），无需额外帧快照协议。
- 单线程协作式，无锁；与现有 VM 单栈调度（``_drive_loop_body``）互补，本调度器
  是多重任务的公共地基，可被后续 VM 多任务入口复用。
- 目的：**服务 LLM 调用**（IO 密集，等待释放 GIL）。受 Python GIL 限制，不追求
  CPU 并行或通用并发框架——本调度器只做多路 LLM IO 的协作式推进。

与现有 ``control.ControlSignal`` 的关系：本模块先用纯 waitable 契约表达挂起，
不引入新的控制流信号；后续语言级 async/await 再在其上构建显式语法。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generator, List, Optional, Protocol, runtime_checkable

from core.runtime.shared.signals import Signal, ControlSignal


@runtime_checkable
class Waitable(Protocol):
    """可等待对象协议：调度器据此询问是否就绪并取完成结果。

    现有 ``LLMFuture``（``is_done`` 属性 + ``result()``）与宿主句柄应适配本协议。
    ``is_done`` 为属性（与 ``LLMFuture.is_done`` 一致），``result()`` 返回完成值。
    """

    @property
    def is_done(self) -> bool: ...

    def result(self) -> Any: ...


@dataclass
class Task:
    """调度器中的一个可挂起任务。"""

    gen: Any
    node_uid: str = ""
    started: bool = False  # 是否已首次推进（区分 next() 与 send()）
    waiting_on: Optional[Waitable] = None


class TaskScheduler:
    """多任务协作调度器。

    用法：``submit(gen)`` 加入任务，``run()`` 推进到全部完成，返回各任务返回值。
    """

    def __init__(self) -> None:
        self._ready: List[Task] = []
        self._waiting: List[Task] = []
        self._results: List[Any] = []

    def submit(self, gen: Generator, node_uid: str = "") -> None:
        self._ready.append(Task(gen=gen, node_uid=node_uid))

    def run(self) -> List[Any]:
        """运行到所有任务完成，返回各任务的完成值（按提交序）。"""
        while self._ready or self._waiting:
            self._advance()
        return self._results

    # ------------------------------------------------------------------
    # 内部推进
    # ------------------------------------------------------------------

    def _advance(self) -> None:
        """推进一轮：先检查等待任务是否就绪，再推进就绪任务。"""
        # 1) 检查等待任务：waitable 就绪 → 恢复（回到就绪）
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
            self._step(t, still_ready)
        self._ready = still_ready

    def _step(self, t: Task, still_ready: List[Task]) -> None:
        """推进单个任务一步。"""
        try:
            if not t.started:
                t.started = True
                yielded = t.gen.send(None)
            else:
                yielded = t.gen.send(t.waiting_on.result() if t.waiting_on else None)
        except StopIteration as si:
            self._results.append(si.value)
            return
        except Exception as e:  # 任务内部异常 → fail-fast 向上抛
            raise

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