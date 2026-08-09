"""
core.runtime.coordinator — 多任务/多 VM 生命周期协调器。

``spawn(fn, args)`` 在**后台线程**运行目标函数，使用**任务本地执行上下文**
（fresh runtime_context + fresh VMExecutor，共享只读 node_pool/registry），
实现 per-task 隔离与全局只读数据共享。

生命周期：``spawn`` → task handle → ``join``（阻塞等待结果）/ ``cancel``（协作式
请求取消）/ ``is_done``（非破坏检查）。

设计（thread 对象 + 句柄方法）：
- 轻量 VM 实例：每并发路径一个，完全隔离作用域/意图/llmexcept，共享只读数据。
- join/cancel 经 handle；结果为函数返回值。**SpawnedTask 不满足 Waitable 协议**
  （async/thread 彻底分离——线程生命周期经句柄方法管理，不供 VM yield 挂起）。
- 后台线程为 daemon（Python 无法强杀线程；cancel 为协作式请求）。

隔离边界（关键）：任务不写主环境作用域；跨任务数据经 Channel/Slot 显式通信。
任务运行期间，``get_current_execution_context`` 返回任务本地 EC（ContextVar
线程隔离），故 LLM 调用 / 内省在任务线程内正确解析到任务上下文。
"""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import Future
from typing import Any, Dict, List, Optional, Tuple

from core.runtime.frame import (
    set_current_execution_context,
    set_current_frame,
    reset_current_execution_context,
    reset_current_frame,
    set_in_thread_task,
    reset_in_thread_task,
)
from core.runtime.shared.waitable import Waitable
from core.runtime.vm.task_scheduler import TaskCancelled


class ThreadCancelled(Exception):
    """任务被协作式取消（经挂起点检查）。"""

    def __init__(self, handle: str):
        super().__init__(f"Task {handle!r} was cancelled.")
        self.handle = handle


def get_runtime_coordinator(executor: Any) -> "RuntimeCoordinator":
    """获取（或惰性创建）执行器关联的 RuntimeCoordinator（线程领域访问器）。

    惰性创建委托给 runtime_context 公开访问器（``get_runtime_coordinator``），
    与 CommRegistry 同级。interpreter 仅在首次创建时传入。
    """
    rc = executor.runtime_context
    interpreter = getattr(executor, "_interpreter", None)
    return rc.get_runtime_coordinator(interpreter)


class SpawnedTask:
    """一个 spawn 任务（后台线程 + 任务本地执行上下文）。

    线程生命周期经句柄方法管理（``join`` 阻塞等结果 / ``cancel`` 协作式请求 /
    ``is_done`` 非破坏检查）。**不满足 :class:`Waitable`**——async/thread 领域
    彻底分离，线程句柄不经 VM yield 挂起（清理：``result()`` 死方法已删除）。
    """

    def __init__(self, interpreter: Any, callable_obj: Any, args: Optional[List[Any]] = None):
        self._interpreter = interpreter
        self._callable = callable_obj
        self._args = list(args or [])
        self._handle = f"task_{uuid.uuid4().hex[:16]}"
        self._future: Future = Future()
        self._cancelled = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ #
    # 生命周期                                                            #
    # ------------------------------------------------------------------ #

    def start(self) -> "SpawnedTask":
        """启动后台线程执行。"""
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=self._handle,
        )
        self._thread.start()
        return self

    def _run(self) -> None:
        """后台线程入口：构建任务本地上下文并驱动函数体。

        协作式取消：任务体在挂起点（Waitable 等待 / 子节点驱动）检查
        ``_cancelled``，命中即抛 ``ThreadCancelled``（join 时重抛）。
        """
        try:
            result = _run_task_body(
                self._interpreter,
                self._callable,
                self._args,
                cancel_event=self._cancelled,
                handle=self._handle,
            )
            self._future.set_result(result)
        except ThreadCancelled as e:
            self._future.set_exception(e)
        except TaskCancelled as e:
            # 用户函数任务体经 VM 步进边界协作取消 → 统一转译为 ThreadCancelled
            self._future.set_exception(ThreadCancelled(self._handle))
        except BaseException as e:  # 任务内任何异常都捕获并传递（join 时重抛）
            self._future.set_exception(e)

    # ------------------------------------------------------------------ #
    # 查询 / 等待                                                        #
    # ------------------------------------------------------------------ #

    @property
    def handle(self) -> str:
        return self._handle

    @property
    def is_done(self) -> bool:
        return self._future.done()

    def try_result(self):
        """非阻塞取回 ``(ok, 结果)``（调度器专用；不阻塞）。"""
        if not self.is_done:
            return (False, None)
        return (True, self._future.result())

    def result(self):
        """阻塞等待并返回任务结果（宿主/线程体专用）。"""
        return self._future.result()

    def register_wake(self, event) -> None:
        """完成通知钩子（R2）：后台 Future 完成时设置 ``event``（可跨线程）。"""
        self._future.add_done_callback(lambda _future: event.set())

    def join(self) -> Any:
        """阻塞等待任务完成并返回结果。"""
        return self._future.result()

    def cancel(self) -> None:
        """请求取消任务（协作式）。

        未启动：直接标记取消并使 join 抛错。
        运行中：设置取消事件，任务在下一个挂起点（Waitable 等待 / 子节点
        驱动）检查并自行退出（``ThreadCancelled``）。纯 CPU 任务无可挂起点时
        cancel 无法强制中断（Python 无法强杀线程）。
        """
        self._cancelled.set()
        if self._thread is None or not self._thread.is_alive():
            # 未启动或已结束：直接让 join 抛取消
            if not self._future.done():
                self._future.set_exception(ThreadCancelled(self._handle))

    def to_dict(self) -> dict:
        return {
            "handle": self._handle,
            "done": self.is_done,
            "cancelled": self._cancelled.is_set(),
        }


def _run_task_body(
    interpreter: Any,
    callable_obj: Any,
    args: List[Any],
    cancel_event: Optional[threading.Event] = None,
    handle: str = "",
) -> Any:
    """在任务本地执行上下文中驱动目标函数体，返回结果。

    构建流程：
    1. 新建任务本地 ``RuntimeContextImpl`` 并经 ``setup_context`` 注入内置。
    2. 新建任务本地 ``ExecutionContextImpl``（共享只读 node_pool/side_tables，
       任务本地 runtime_context/logical_stack/current_module）。
    3. 新建任务本地 ``VMExecutor`` 绑定到该 EC。
    4. 若可调用是 ``IbUserFunction``：经其 ``call()`` 驱动（内部 run_body）。
       否则（lambda/fn_callable/behavior）经 ``_vm_call_fn_callable`` CPS 驱动。

    ``handle``：任务句柄标识，用于协作式取消错误上报（不再依赖失效的
    ``_task_handle`` 属性读取）。
    """
    from core.runtime.interpreter.runtime_context import RuntimeContextImpl
    from core.runtime.interpreter.execution_context import ExecutionContextImpl
    from core.runtime.interpreter.call_stack import LogicalCallStack
    from core.runtime.vm import VMExecutor
    from core.runtime.objects.kernel import IbUserFunction, IbValue, IbObject, IbFunction
    from core.runtime.objects.cell import IbCell

    main_ec = interpreter.execution_context
    registry = interpreter.registry

    # 1. 任务本地 runtime_context（隔离作用域/意图/llmexcept）。
    #    全局作用域链到入口模块作用域（main interpreter 的 global_scope），使模块级
    #    函数（含递归目标自身）在任务体可解析；任务对全局的写入落在任务本地全局
    #    子作用域（parent=模块作用域），不污染主环境（隔离 + 可读模块符号）。
    from core.runtime.interpreter.runtime_context import ScopeImpl
    main_global_scope = interpreter.runtime_context.global_scope
    task_global = ScopeImpl(parent=main_global_scope, registry=registry)
    task_rt = RuntimeContextImpl(initial_scope=task_global, registry=registry)
    interpreter.setup_context(task_rt)

    # 2. 任务本地 EC：共享只读回调（node_pool/side_tables/factory），任务本地状态
    task_logical_stack = LogicalCallStack(max_depth=interpreter.max_call_stack)
    task_ec = ExecutionContextImpl(
        registry=registry,
        factory=main_ec.factory,
        get_node_data_callback=interpreter.get_node_data,
        get_side_table_callback=interpreter.get_side_table,
        push_stack_callback=task_logical_stack.push,
        pop_stack_callback=task_logical_stack.pop,
        get_instruction_count_callback=lambda: 0,
        get_captured_intents_callback=interpreter.get_captured_intents,
        is_truthy_callback=interpreter.is_truthy,
        resolve_type_from_symbol_callback=interpreter._resolve_type_from_symbol,
        extract_name_id_callback=interpreter._extract_name_id,
        resolve_value_callback=interpreter._resolve_value,
        module_manager=interpreter.service_context.module_manager,
        strict_mode=True,
        entry_file=main_ec.get_entry_path(),
        entry_dir=main_ec.get_entry_dir(),
    )
    task_ec.runtime_context = task_rt
    task_ec.node_pool = main_ec.node_pool
    task_ec.symbol_pool = main_ec.symbol_pool
    task_ec.scope_pool = main_ec.scope_pool
    task_ec.type_pool = main_ec.type_pool
    task_ec.asset_pool = main_ec.asset_pool
    task_ec.logical_stack = task_logical_stack
    task_ec.current_module_name = interpreter.current_module_name

    # 3. 任务本地 VMExecutor（cancel_event 经驱动循环步进边界检查——协作取消覆盖
    #    用户函数任务体，D5 闭合）
    task_vm = VMExecutor(task_ec, interpreter=interpreter, cancel_event=cancel_event)
    task_ec.vm_executor = task_vm

    # 4. 线程本地 ContextVar：任务线程内的 LLM/内省正确解析到任务 EC
    frame_token = set_current_frame(task_rt)
    ec_token = set_current_execution_context(task_ec)
    task_token = set_in_thread_task(True)
    try:
        # P3 隔离：把与主线程共享的闭包 cell 标记为"任务内禁写"——任务内对捕获
        # 变量赋值会写共享 cell（主线程可见），违反隔离承诺。覆盖用户函数/lambda/
        # behavior 全部任务体（其 closure 均为主线程共享的闭包 cell）。
        for _sym_uid, (_var_name, _cell) in (getattr(callable_obj, "closure", None) or {}).items():
            if isinstance(_cell, IbCell):
                _cell.mark_shared_with_main()

        if isinstance(callable_obj, IbUserFunction):
            # 用户函数：构建任务本地函数包装（绑定 task EC），函数体经
            # CPS 生成器驱动（与 lambda 分支同构，R1）——避免同步 call()
            # 嵌套（线程内深递归同样受 Python 栈限制，CPS 驱动消除之）。
            from core.runtime.objects.kernel import IbUserFunction as _UF

            task_func = _UF(
                node_uid=callable_obj.node_uid,
                context=task_ec,
                ib_class=callable_obj.ib_class,
                spec=callable_obj.spec,
                module_name=callable_obj.module_name,
                owner_class=getattr(callable_obj, "owner_class", None),
            )
            task_func.closure = callable_obj.closure
            from core.runtime.vm.handlers._shared import _vm_call_user_function

            gen = _vm_call_user_function(task_vm, task_func, registry.get_none(), args)
            return _drive_generator(task_vm, gen, cancel_event=cancel_event, handle=handle)
        if isinstance(callable_obj, IbValue) and callable_obj.ib_class.name in (
            "fn_callable",
            "behavior",
        ):
            # lambda/snapshot/behavior：CPS 内联驱动
            from core.runtime.vm.handlers._shared import _vm_call_fn_callable, _vm_invoke_behavior
            from core.runtime.vm.task import VMTask

            if callable_obj.ib_class.name == "behavior":
                # behavior：经 CPS 驱动
                result = _run_behavior_cps(task_vm, callable_obj, args, cancel_event=cancel_event, handle=handle)
                return result
            # fn_callable（lambda/snapshot）：经 CPS 驱动
            gen = _vm_call_fn_callable(task_vm, callable_obj, args)
            return _drive_generator(task_vm, gen, cancel_event=cancel_event, handle=handle)
        # 兜底：原生函数 / 绑定方法（IbFunction 家族；hasattr(call) 探测改为
        # isinstance 精确判别——call 仅定义于 IbFunction 子类）
        if isinstance(callable_obj, IbFunction):
            return callable_obj.call(registry.get_none(), args)
        raise RuntimeError(
            f"spawn: 目标 {callable_obj!r} 不可作为任务执行（非函数/lambda/behavior）"
        )
    finally:
        reset_current_execution_context(ec_token)
        reset_current_frame(frame_token)
        reset_in_thread_task(task_token)


def _run_behavior_cps(task_vm: Any, behavior: Any, args: List[Any], cancel_event: Optional[threading.Event] = None, handle: str = "") -> Any:
    """在任务本地 VM 中 CPS 驱动 behavior 表达式。"""
    from core.runtime.vm.handlers._shared import _vm_invoke_behavior

    gen = _vm_invoke_behavior(task_vm, behavior, args)
    return _drive_generator(task_vm, gen, cancel_event=cancel_event, handle=handle)


def _drive_generator(task_vm: Any, gen: Any, send_first: Any = None, cancel_event: Optional[threading.Event] = None, handle: str = "") -> Any:
    """驱动一个 CPS 生成器到完成（阻塞等待每个 Waitable）。

    任务线程内使用：对 LLM Future / 通信 Channel recv 等 Waitable 阻塞等待。

    生成器契约（与 VM 主循环一致）： ``send(None)`` 启动；后续 yield 的
    若是 Waitable 则阻塞等待其完成再 ``send(result)`` 恢复；yield child
    uid 经任务本地 VM 求值后恢复；yield ``UserFunctionCall`` 则把函数体
    生成器作为独立帧压栈（trampoline——线程体内深递归不
    再嵌套 Python 栈，与 VM 主路径 ``_drive_loop_gen`` 同构）。

    协作式取消：每个挂起点（Waitable 等待 / 子节点驱动前）检查
    ``cancel_event``，命中即抛 ``ThreadCancelled``。``handle`` 为任务句柄标识
    （由调用方传入，不再读取失效的 ``_task_handle`` 属性）。
    """
    from core.runtime.shared.waitable import Waitable
    from core.runtime.shared.signals import UnhandledSignal
    from core.runtime.shared.user_call import UserFunctionCall

    def _check_cancel() -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise ThreadCancelled(handle)

    # 显式生成器栈（trampoline）：UserFunctionCall 压栈而非递归 _drive_generator，
    # 消除线程体内深递归的 Python/OS 栈嵌套（与 _drive_loop_gen 同构）。
    stack = [gen]
    pending_value: Any = send_first
    while stack:
        _check_cancel()
        cur = stack[-1]
        try:
            yielded = cur.send(pending_value)
        except StopIteration as si:
            stack.pop()
            pending_value = si.value
            continue
        except Exception as e:
            # 环境限制异常（栈溢出/内存/系统）非语义错误：保留根因传播
            from core.runtime.observability.diagnostics import handle_environment_limit
            if handle_environment_limit(e, rc=task_vm.runtime_context):
                raise
            raise

        pending_value = None
        if isinstance(yielded, Waitable):
            pending_value = yielded.result()
        elif isinstance(yielded, str) and task_vm.supports(yielded):
            # 子节点 uid：经任务本地 VM 求值后恢复。
            # RETURN 信号在独立 run() 中无函数上下文 → UnhandledSignal；
            # 此处把它转回 Signal 投递给生成器（函数体用 Signal 表达返回）。
            try:
                pending_value = task_vm.run(yielded)
            except UnhandledSignal as us:
                pending_value = us.signal
        elif isinstance(yielded, UserFunctionCall):
            # 用户函数调用请求（R1 trampoline）：压栈函数体生成器，循环继续
            # 驱动栈顶——线程体内深递归 Python 深度恒定（不再嵌套 _drive_generator）。
            from core.runtime.vm.handlers._shared import _vm_call_user_function

            inner = _vm_call_user_function(
                task_vm, yielded.func, yielded.receiver, yielded.args
            )
            stack.append(inner)
        else:
            raise RuntimeError(
                f"spawn task: generator yielded non-waitable, non-node value {yielded!r}"
            )
    return pending_value


class RuntimeCoordinator:
    """多任务生命周期协调器。

    ``spawn(fn, args)`` → ``SpawnedTask``（后台线程 + 任务本地上下文）。
    ``join`` / ``cancel`` / ``is_done`` 经 handle。
    """

    def __init__(self, interpreter: Any):
        self._interpreter = interpreter
        self._tasks: Dict[str, SpawnedTask] = {}
        self._lock = threading.Lock()

    def spawn(self, callable_obj: Any, args: Optional[List[Any]] = None) -> SpawnedTask:
        """在后台线程运行目标函数，返回任务句柄。

        任务完成（正常/失败/取消）后自动从 ``_tasks`` 移除，防止句柄表
        无限增长（资源生命周期，F-2）。
        """
        task = SpawnedTask(self._interpreter, callable_obj, args).start()
        with self._lock:
            self._tasks[task.handle] = task
        self._schedule_cleanup(task)
        return task

    def _schedule_cleanup(self, task: SpawnedTask) -> None:
        """在任务完成回调中移除自身（防泄漏）。"""
        task._future.add_done_callback(
            lambda fut: self.cleanup(task.handle)
        )

    def lookup(self, handle: str) -> Optional[SpawnedTask]:
        with self._lock:
            return self._tasks.get(handle)

    def is_done(self, handle: str) -> bool:
        task = self.lookup(handle)
        return task.is_done if task else True

    def join(self, handle: str) -> Any:
        task = self.lookup(handle)
        if task is None:
            raise RuntimeError(f"Unknown task handle: {handle!r}")
        return task.join()

    def cancel(self, handle: str) -> None:
        task = self.lookup(handle)
        if task is not None:
            task.cancel()

    def snapshot(self) -> list:
        with self._lock:
            return [t.to_dict() for t in self._tasks.values()]

    def unfinished_handles(self) -> List[str]:
        """返回所有未完成任务的句柄（save_state 检测用）。"""
        with self._lock:
            return [h for h, t in self._tasks.items() if not t.is_done]

    def cleanup(self, handle: str) -> None:
        with self._lock:
            self._tasks.pop(handle, None)
