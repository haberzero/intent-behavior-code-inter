"""
[IES 2.1+] LLM 异步任务管理层

本模块提供最低限度的 LLM 异步调用支持可能性。

当前实现为最小可行层（MVP），采用 Future 模式封装同步调用。
真正的多线程/async 支持需要解释器核心架构大规模重构。

妥协说明：
1. submit() 只是立即执行并返回已完成的结果，而非真正异步
2. 所有任务在提交时同步阻塞执行
3. wait_all() 只是收集已完成结果，无实际并发
4. 需要解释器支持 await/Future 语义才能实现真正异步

架构演进路径：
- 当前：同步调用封装 → Future 模式（无并发）
- 未来：解释器核心重构 → 支持 async/await 语法
- 未来：线程池/进程池 → 真正的并发执行
- 最终：分布式 LLM 调度 → 跨进程/跨机器的 LLM 调用
"""
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import threading
import queue


class TaskState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class LLMTaskResult:
    """LLM 任务执行结果"""
    task_id: str
    state: TaskState
    response: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.state == TaskState.COMPLETED and self.response is not None


class LLMTask:
    """
    LLM 异步任务封装

    当前为同步封装，真正的异步需要解释器支持。
    """
    def __init__(
        self,
        task_id: str,
        sys_prompt: str,
        user_prompt: str,
        scene: str = "general",
        llm_executor: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.task_id = task_id
        self.sys_prompt = sys_prompt
        self.user_prompt = user_prompt
        self.scene = scene
        self.llm_executor = llm_executor
        self.metadata = metadata or {}
        self._state = TaskState.PENDING
        self._result: Optional[LLMTaskResult] = None
        self._future_lock = threading.Lock()

    @property
    def state(self) -> TaskState:
        return self._state

    @property
    def result(self) -> Optional[LLMTaskResult]:
        return self._result

    def _execute_sync(self) -> LLMTaskResult:
        """
        同步执行 LLM 调用

        妥协点：当前只是同步执行，真正的异步需要解释器支持。
        """
        self._state = TaskState.RUNNING

        if not self.llm_executor:
            return LLMTaskResult(
                task_id=self.task_id,
                state=TaskState.FAILED,
                error="LLM executor not available"
            )

        try:
            response = self.llm_executor.execute_llm_function(
                node_uid=self.task_id,
                execution_context=None,
                call_intent=None
            )
            native_response = response.to_native() if hasattr(response, 'to_native') else str(response)
            self._state = TaskState.COMPLETED
            return LLMTaskResult(
                task_id=self.task_id,
                state=TaskState.COMPLETED,
                response=native_response,
                metadata=self.metadata
            )
        except Exception as e:
            self._state = TaskState.FAILED
            return LLMTaskResult(
                task_id=self.task_id,
                state=TaskState.FAILED,
                error=str(e),
                metadata=self.metadata
            )

    def submit(self) -> 'LLMTask':
        """
        提交任务执行

        妥协说明：当前实现为同步执行。
        未来解释器支持 async 后，此方法应变为 async def。
        """
        with self._future_lock:
            result = self._execute_sync()
            self._result = result
        return self

    def cancel(self) -> bool:
        """
        尝试取消任务

        妥协说明：当前仅能取消待执行任务，已执行任务无法取消。
        """
        if self._state == TaskState.PENDING:
            self._state = TaskState.CANCELLED
            self._result = LLMTaskResult(
                task_id=self.task_id,
                state=TaskState.CANCELLED
            )
            return True
        return False


class LLMTaskPool:
    """
    LLM 任务池

    提供批量 LLM 任务管理和结果收集能力。

    妥协说明：
    1. 当前为单线程同步执行，无真正并发
    2. 批量提交实际上是逐个执行
    3. 需要解释器支持任务调度才能实现真正并发
    """
    def __init__(self, llm_executor: Optional[Any] = None):
        self.llm_executor = llm_executor
        self._tasks: Dict[str, LLMTask] = {}
        self._task_counter = 0
        self._lock = threading.Lock()

    def _generate_task_id(self) -> str:
        with self._lock:
            self._task_counter += 1
            return f"llm_task_{self._task_counter}"

    def submit(
        self,
        sys_prompt: str,
        user_prompt: str,
        scene: str = "general",
        metadata: Optional[Dict[str, Any]] = None
    ) -> LLMTask:
        """
        提交单个 LLM 任务

        妥协说明：立即同步执行，不返回 Future。
        未来应返回 asyncio.Future 或 concurrent.futures.Future。
        """
        task_id = self._generate_task_id()
        task = LLMTask(
            task_id=task_id,
            sys_prompt=sys_prompt,
            user_prompt=user_prompt,
            scene=scene,
            llm_executor=self.llm_executor,
            metadata=metadata
        )
        with self._lock:
            self._tasks[task_id] = task

        task.submit()
        return task

    def submit_batch(
        self,
        tasks: List[Dict[str, Any]]
    ) -> List[LLMTask]:
        """
        批量提交 LLM 任务

        妥协说明：逐个同步执行，无并发。
        未来解释器支持后，应使用 asyncio.gather() 或类似机制。
        """
        results = []
        for task_spec in tasks:
            task = self.submit(
                sys_prompt=task_spec.get("sys_prompt", ""),
                user_prompt=task_spec.get("user_prompt", ""),
                scene=task_spec.get("scene", "general"),
                metadata=task_spec.get("metadata")
            )
            results.append(task)
        return results

    def wait_all(self, timeout: Optional[float] = None) -> List[LLMTaskResult]:
        """
        等待所有任务完成

        妥协说明：由于任务是同步执行的，调用时已经全部完成。
        真正异步时需要使用 asyncio.wait() 或类似机制。
        """
        results = []
        for task in self._tasks.values():
            if task.result:
                results.append(task.result)
        return results

    def get_task(self, task_id: str) -> Optional[LLMTask]:
        """获取指定任务"""
        return self._tasks.get(task_id)

    def get_results(self) -> List[LLMTaskResult]:
        """获取所有已完成任务的结果"""
        return [task.result for task in self._tasks.values() if task.result]

    def clear(self):
        """清空任务池"""
        with self._lock:
            self._tasks.clear()
            self._task_counter = 0


def create_task_pool(llm_executor: Optional[Any] = None) -> LLMTaskPool:
    """工厂函数：创建 LLM 任务池"""
    return LLMTaskPool(llm_executor=llm_executor)
