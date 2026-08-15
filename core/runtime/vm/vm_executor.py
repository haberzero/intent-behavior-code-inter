"""
core.runtime.vm.vm_executor — VM 调度循环主类。

调度协议
--------
1. 调用 ``run(node_uid)`` 启动新执行：把入口节点封装为 :class:`VMTask` 推入帧栈。
2. 主循环按以下规则前进：

   * 取栈顶任务的生成器，执行 ``send(value)`` （或首次 ``send(None)``）：
     - 若生成器 ``yield child_uid``：基于 ``child_uid`` 创建新 VMTask 并压栈，
       下一轮调度新任务（由它产生 child 的求值结果）
     - 若生成器 ``StopIteration(value)``：弹栈
        - 若 ``value`` 是 :class:`Signal` 数据对象（控制信号数据化）：
          视作控制流信号，沿帧栈向上数据化传递（``send(Signal)`` 给父帧）；
          父 handler 用 ``isinstance(res, Signal)`` 决定拦截或继续传播。
          若帧栈空仍持有未消费 Signal，以 :class:`UnhandledSignal` 形式
          抛给调用者。
        - 否则把 value 通过 ``send`` 传给父帧
     - 若生成器 ``raise``：弹栈，沿帧栈向上 ``throw`` 给父帧的生成器；调度循环
       会持续向上传播，直到某帧的 ``except`` 子句捕获或栈空（向调用者抛出）

3. 当帧栈空时，最后一个 ``send`` 的结果即为整体执行结果。

主循环不使用 Python 递归。CPS dispatch table 覆盖全部 43 种 AST 节点类型；
``Interpreter.execute_module()`` 和 ``IbUserFunction.call()`` 以本执行器为主路径。
"""
from __future__ import annotations
import inspect
from typing import Any, Optional

from core.runtime.vm.task import (
    VMTask,
    ControlSignal,
    UnhandledSignal,
    Signal,
)
from core.runtime.vm.task_scheduler import TaskScheduler, TaskCancelled, Waitable
from core.runtime.vm.handlers import (
    build_dispatch_table,
    build_one_shot_intent_from_annotation,
)
from core.runtime.shared.user_call import UserFunctionCall
from core.runtime.shared.signals import GeneratorYield


class VMExecutor:
    """显式帧栈 CPS 调度执行器。

    构造参数:
        execution_context: 已配置的 :class:`ExecutionContextImpl`，提供节点池、
                           侧表、运行时上下文与对象工厂等服务。
        interpreter: 可选 :class:`Interpreter` 引用；当前未使用，可传 None。
        cancel_event: 可选 ``threading.Event``。设置后 ``_drive_loop_gen`` 在每个
                      步进边界检查并 ``raise TaskCancelled``（线程体协作取消；主
                      VM 为 None 不启用）。
    """

    def __init__(self, execution_context: Any, interpreter: Optional[Any] = None,
                 cancel_event: Any = None):
        self._ec = execution_context
        self._interpreter = interpreter
        self._cancel_event = cancel_event
        self._dispatch = build_dispatch_table()
        # 当前正在执行的帧栈引用；仅在 _drive_loop_gen 驱动活跃时非 None
        # （调度器多任务下为"当前推进任务"的栈，随任务步进切换）。
        self._current_stack: Optional[list] = None

    # ------------------------------------------------------------------
    # Service accessors
    # ------------------------------------------------------------------

    @property
    def ec(self) -> Any:
        """ExecutionContext 引用。"""
        return self._ec

    @property
    def runtime_context(self) -> Any:
        return self._ec.runtime_context

    @property
    def registry(self) -> Any:
        return self._ec.registry

    @property
    def frame_stack_depth(self) -> int:
        """当前 CPS 帧栈深度。

        仅在调度循环（``_drive_loop_gen``）驱动期间非零。供调试器 / 测试观察
        正在执行的 VMTask 帧层级（``_vm_invoke_behavior`` /
        ``_vm_invoke_llm_function`` yield 后，本属性应 ≥ 2）。
        """
        return len(self._current_stack) if self._current_stack is not None else 0

    @property
    def service_context(self) -> Any:
        """ServiceContext（通过 interpreter 间接访问）；若无 interpreter 则返回 None。

        handlers 通过此属性获取 capability_registry（例如 llm_provider.get_retry()）。
        """
        if self._interpreter is not None:
            return self._interpreter.service_context
        return None

    # ------------------------------------------------------------------
    # 节点求值入口
    # ------------------------------------------------------------------

    def supports(self, node_uid: str) -> bool:
        """判断 ``node_uid`` 对应节点类型是否有 CPS 处理器。"""
        node_data = self._ec.get_node_data(node_uid)
        if not node_data:
            return False
        return node_data.get("_type") in self._dispatch

    # ------------------------------------------------------------------
    # 主调度循环
    # ------------------------------------------------------------------

    def run(self, node_uid: str) -> Any:
        """执行 ``node_uid`` 的 AST 子树并返回最终结果（IbObject）。

        这是调度循环的入口；不使用 Python 递归。
        """
        if node_uid is None:
            return self.registry.get_none()
        if not self.supports(node_uid):
            # 所有 AST 节点类型均已有 CPS handler；到达此处意味着节点类型
            # 不在 dispatch table（新增节点未实现 handler，或 artifact 损坏）。
            node_data = self._ec.get_node_data(node_uid) if isinstance(node_uid, str) else None
            node_type = (node_data.get("_type") if node_data else None) or repr(node_uid)
            raise RuntimeError(
                f"VMExecutor: No CPS handler for root node type {node_type!r} "
                f"(uid={node_uid!r}). Add vm_handle_{node_type} to core/runtime/vm/handlers.py."
            )

        scheduler = TaskScheduler(cancel_event=self._cancel_event)
        scheduler.submit(self._drive_loop_gen([self._make_task(node_uid)]))
        results = scheduler.run()
        if isinstance(results[0], TaskCancelled):
            # 协作取消（线程体 cancel_event / VM 级取消）→ 转译为异常向调用方传播
            raise results[0]
        return results[0]

    def run_many(self, roots: "List[str]") -> "List[Any]":
        """并发执行多个根任务（多任务/宿主异步入口）。

        每个根是一棵独立 AST 子树；用 ``TaskScheduler`` 协作式推进，各根在
        等待 LLM/IO（Waitable）时挂起、让出给其它根，就绪后恢复。返回各根
        结果（按 roots 提交序）。

        受 Python GIL 限制，本并发只为服务 LLM 调用（IO 密集）。
        """
        scheduler = TaskScheduler(cancel_event=self._cancel_event)
        for root in roots:
            scheduler.submit(self._drive_loop_gen([self._make_task(root)]), node_uid=root)
        return scheduler.run()

    def run_body(self, stmt_uids: Any) -> Any:
        """执行一个语句列表（模块或函数体）。

        body 中的 IbLLMExceptionalStmt 节点已是正则 stmt，直接 run() 即可，无需特殊跳过逻辑。

        确保多 Interpreter 并发场景下两条路径保持一致。

        参数:
            stmt_uids: 语句 UID 序列（``IbModule.body`` / ``IbFunctionDef.body``）。

        返回:
            最后一条语句的求值结果；空 body 返回 ``IbNone``。

        异常:
            ``UnhandledSignal``：顶层未消费的控制信号直接以
                ``UnhandledSignal`` 形式向调用方传播。调用方（``IbUserFunction.call``、
                ``execute_module``）直接捕获并按 ``e.signal.kind`` 分类处理。
        """
        result = self.registry.get_none()
        pending_one_shot = None

        for stmt_uid in stmt_uids or ():
            node_data = self._ec.get_node_data(stmt_uid) if stmt_uid else None
            if node_data and node_data.get("_type") == "IbIntentAnnotation":
                pending_one_shot = build_one_shot_intent_from_annotation(self, node_data)
                continue

            if pending_one_shot is not None:
                self.runtime_context.activate_statement_one_shot_intent(pending_one_shot)

            try:
                result = self.run(stmt_uid)
            finally:
                if pending_one_shot is not None:
                    self.runtime_context.cleanup_statement_one_shot_intent(pending_one_shot)
                    pending_one_shot = None
        return result

    # ------------------------------------------------------------------
    # 内部：调度循环主体（被 run() / future 入口共享）
    # ------------------------------------------------------------------

    def _drive_loop_gen(self, stack: list, *, yield_generator_values: bool = False) -> Any:
        """可挂起的调度循环生成器（单一权威驱动，阶段 1a）。

        逐帧推进栈；当某 handler yield 一个 Waitable（如 ``LLMFuture``）时挂起
        （``yield waitable``），把控制权交还调用方；调用方（调度器 / 线程体）
        在 waitable 就绪后 ``send(result)`` 恢复。栈耗尽时返回最终结果。

        ``yield_generator_values=True``：惰性生成器体驱动模式——识别
        ``GeneratorYield`` 语言级产出标记（``vm_handle_IbYieldExpr`` 求值后
        yield），把它**挂起向外交付**（``yield`` 给迭代方），迭代恢复（``send``）
        后继续推进，保持生成器体循环位置 / 局部变量（EXEC-FOUNDATION §5.2
        单可恢复驱动）。主路径（False）下 GeneratorYield 不产生；若出现则走
        通用 child 处理（报未知 handler）。

        ``_current_stack`` 绑定（供 ``frame_stack_depth`` 观察 CPS 栈深度）在
        本生成器内保存/恢复：多任务下每任务的栈视图随其步进自然切换；嵌套
        ``run`` 重入（如意图消解的 ``vm.run(segment)``）经 finally 恢复外层视图。

        协作取消（``cancel_event``）在生成器体驱动模式同样生效
        （覆盖生成器体内深递归）。
        """
        prev_stack = self._current_stack
        self._current_stack = stack
        try:
            # (value, exception) — 互斥；下一次循环将传递给栈顶任务
            pending_value: Any = None
            pending_exception: Optional[BaseException] = None

            while stack:
                if self._cancel_event is not None and self._cancel_event.is_set():
                    # 协作取消（线程体）：每个步进边界检查，覆盖全任务体（含用户函数）
                    raise TaskCancelled()

                task = stack[-1]
                gen = task.generator
                try:
                    if pending_exception is not None:
                        exc = pending_exception
                        pending_exception = None
                        child_uid = gen.throw(exc)
                    else:
                        val = pending_value
                        pending_value = None
                        child_uid = gen.send(val)
                except StopIteration as si:
                    stack.pop()
                    ret_value = si.value
                    # StopIteration.value 若是 Signal，作为控制流数据沿栈传递
                    if isinstance(ret_value, Signal):
                        pending_value = ret_value
                    else:
                        pending_value = (
                            ret_value if ret_value is not None else self.registry.get_none()
                        )
                    continue
                except UnhandledSignal as use:
                    # IbUserFunction.call() 等通过 vm.run_body() 执行函数体，
                    # 若内部 BREAK/CONTINUE 逃逸出函数体，以 UnhandledSignal 透传。
                    stack.pop()
                    pending_exception = use
                    continue
                except Exception as e:
                    # 其他运行时异常：弹栈并向上传递
                    stack.pop()
                    pending_exception = e
                    continue

                if yield_generator_values and isinstance(child_uid, GeneratorYield):
                    # 语言级产出（生成器体）：挂起向外交付 value，迭代恢复后继续
                    pending_value = yield child_uid
                    continue

                # 生成器 yield 了一个子节点 uid：决定是 CPS 求值还是 fallback
                if child_uid is None:
                    # yield None —— 视作 None 立即返回
                    pending_value = self.registry.get_none()
                    continue

                # 生成器 yield 了一个 Waitable（如 LLMFuture）→ 挂起，等待其完成。
                # 调度器挂起该根、让出给其它根，就绪后 send 结果恢复。
                # 异常对称投递：Waitable 失败时调度器把 worker 线程异常经
                # gen.throw 投进本 yield 点（此处于内部 try/except 之外）。
                # 捕获后置入 pending_exception，经循环顶部 gen.throw 重投递给
                # 挂起该 Waitable 的 innermost 任务帧——其 try/except 优先处理，
                # 未捕获则走下方弹栈通道沿 CPS 栈上抛。TaskCancelled 为
                # BaseException，不被 except Exception 捕获，正常穿透给调度器。
                if isinstance(child_uid, Waitable):
                    try:
                        pending_value = yield child_uid
                    except Exception as e:
                        pending_exception = e
                    continue

                # R1 trampoline：用户函数调用请求（vm_handle_IbCall 对
                # IbUserFunction yield）——把函数体作为独立 VMTask 压栈，
                # 函数体生成器挂起时不在 Python 栈上（EXEC-1：深递归
                # Python 深度恒定）。函数完成 return 后调度器 send 回调用点。
                # 惰性生成器（含 yield）：产出可恢复驱动（IbGenerator 承载），
                # 迭代驱动函数体、yield 点产出值。
                if isinstance(child_uid, UserFunctionCall):
                    # func 可为 IbUserFunction/IbNativeFunction/IbLLMFunction；
                    # is_generator 在 IbFunction 基类声明（缺省 False），
                    # 属性直读分派生成器 vs 普通函数体压栈。
                    if child_uid.func.is_generator:
                        pending_value = self.make_generator_driver(child_uid)
                    else:
                        stack.append(self._make_user_function_task(child_uid))
                    continue

                if isinstance(child_uid, str) and self.supports(child_uid):
                    stack.append(self._make_task(child_uid))
                else:
                    # dispatch table 覆盖所有 47 个 AST 节点类型；到达此处
                    # 意味着 handler yield 了一个未知节点 uid（artifact 损坏或新
                    # 增了未实现 handler 的节点）。
                    node_data = self._ec.get_node_data(child_uid) if isinstance(child_uid, str) else None
                    node_type = (node_data.get("_type") if node_data else None) or repr(child_uid)
                    raise RuntimeError(
                        f"VMExecutor: No CPS handler for node type {node_type!r} "
                        f"(uid={child_uid!r}). Add vm_handle_{node_type} to core/runtime/vm/handlers.py."
                    )

            # 栈空：处理最终结果
            if pending_exception is not None:
                raise pending_exception
            # 未消费的顶层 Signal → 以 UnhandledSignal 抛给调用方
            if isinstance(pending_value, Signal):
                raise UnhandledSignal(pending_value)
            return pending_value if pending_value is not None else self.registry.get_none()
        finally:
            self._current_stack = prev_stack

    # ------------------------------------------------------------------
    # 内部：任务构造
    # ------------------------------------------------------------------

    def _make_task(self, node_uid: str) -> VMTask:
        node_data = self._ec.get_node_data(node_uid)
        if not node_data:
            # 调用方已通过 supports() 排除，不应到达——fail-fast。
            raise RuntimeError(
                f"VMExecutor: missing node data for uid={node_uid!r} "
                "(supports() should have filtered it)"
            )
        node_type = node_data.get("_type")
        handler = self._dispatch.get(node_type)
        if handler is None:
            # 调用方已通过 supports() 排除，不应到达
            raise RuntimeError(
                f"VMExecutor: no CPS handler for node type {node_type!r} "
                f"(uid={node_uid})"
            )
        if not inspect.isgeneratorfunction(handler):
            # 非生成器 handler（纯 return 值）：中央化包装为生成器，
            # 消除各 handler 内的 ``if False: yield`` 身份 hack（R2-D5）。
            def _gen(h=handler):
                return h(self, node_uid, node_data)
                yield  # pragma: no cover
            return VMTask(node_uid=node_uid, generator=_gen())
        gen = handler(self, node_uid, node_data)
        return VMTask(node_uid=node_uid, generator=gen)

    def _make_user_function_task(self, call: "UserFunctionCall") -> VMTask:
        """为 R1 用户函数调用请求创建函数体 VMTask（trampoline 压栈）。

        函数体生成器为 ``_vm_call_user_function``（CPS 内联驱动，帧准备 +
        逐语句 yield），作为独立 VMTask 压入同一帧栈。函数完成后其返回值
        经 ``_drive_loop_gen`` 的 ``StopIteration.value`` send 回调用点。
        """
        from core.runtime.vm.handlers._shared import _vm_call_user_function

        gen = _vm_call_user_function(
            self, call.func, call.receiver, call.args
        )
        return VMTask(node_uid=getattr(call.func, "node_uid", ""), generator=gen)

    def make_generator_driver(self, call: "UserFunctionCall"):
        """为惰性生成器函数调用创建单可恢复体驱动（阶段 5 yield）。

        生成器函数体经 ``_vm_call_user_function``（CPS 帧准备 + 逐语句 yield）
        作为**单一** VMTask 压栈，由 ``_drive_loop_gen``（可恢复驱动，
        ``yield_generator_values=True``）推进：在 ``yield`` 点 ``GeneratorYield``
        挂起向外交付、迭代恢复。返回驱动生成器，``next()`` 取产出值、``send``
        恢复。与普通函数（trampoline 压栈同级，但驱动循环可暂停）同构。
        """
        from core.runtime.vm.handlers._shared import _vm_call_user_function

        gen = _vm_call_user_function(
            self, call.func, call.receiver, call.args
        )
        return self._drive_loop_gen(
            [VMTask(node_uid=getattr(call.func, "node_uid", ""), generator=gen)],
            yield_generator_values=True,
        )
