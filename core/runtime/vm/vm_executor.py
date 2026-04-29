"""
core.runtime.vm.vm_executor — VM 调度循环主类（M3a + M3b）。

调度协议
--------
1. 调用 ``run(node_uid)`` 启动新执行：把入口节点封装为 :class:`VMTask` 推入帧栈。
2. 主循环按以下规则前进：

   * 取栈顶任务的生成器，执行 ``send(value)`` （或首次 ``send(None)``）：
     - 若生成器 ``yield child_uid``：基于 ``child_uid`` 创建新 VMTask 并压栈，
       下一轮调度新任务（由它产生 child 的求值结果）
     - 若生成器 ``StopIteration(value)``：弹栈
        - 若 ``value`` 是 :class:`Signal` 数据对象（M3b 控制信号数据化）：
          视作控制流信号，沿帧栈向上数据化传递（``send(Signal)`` 给父帧）；
          父 handler 用 ``isinstance(res, Signal)`` 决定拦截或继续传播。
          若帧栈空仍持有未消费 Signal，包装为 :class:`ControlSignalException`
          抛给调用者（边界兼容）。
        - 否则把 value 通过 ``send`` 传给父帧
     - 若生成器 ``raise``：弹栈，沿帧栈向上 ``throw`` 给父帧的生成器；调度循环
       会持续向上传播，直到某帧的 ``except`` 子句捕获或栈空（向调用者抛出）

3. 当帧栈空时，最后一个 ``send`` 的结果即为整体执行结果。

主循环不使用 Python 递归。这是 M3a/M3b 的核心成果——为 M3c 的 LLM 流水线、
DynamicHost 切片调度奠定调度层基础。

未实现的节点类型自动回退到 ``execution_context.visit(uid)`` （递归路径），
M3d 阶段才把全部节点纳入 CPS。
"""
from __future__ import annotations
from typing import Any, Optional

from core.runtime.vm.task import (
    VMTask,
    VMTaskResult,
    ControlSignal,
    ControlSignalException,
    Signal,
)
from core.runtime.vm.handlers import build_dispatch_table


class VMExecutor:
    """显式帧栈 CPS 调度执行器（M3a + M3b）。

    构造参数:
        execution_context: 已配置的 :class:`ExecutionContextImpl`，提供节点池、
                           侧表、运行时上下文与对象工厂等服务。
        interpreter: 可选 :class:`Interpreter` 引用；用于复用其 ``_assign_to_target``
                     等高阶帮助方法（M3a 简化路径）。若为 None 则 ``assign_to_target``
                     不可用。
    """

    def __init__(self, execution_context: Any, interpreter: Optional[Any] = None):
        self._ec = execution_context
        self._interpreter = interpreter
        self._dispatch = build_dispatch_table()
        # 调度计数：所有 yield/StopIteration 步骤的累计；用于诊断与未来限速。
        self.step_count: int = 0
        self.max_steps: int = 0  # 0 == unlimited

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
    def service_context(self) -> Any:
        """ServiceContext（通过 interpreter 间接访问）；若无 interpreter 则返回 None。

        handlers 通过此属性获取 capability_registry（例如 llm_provider.get_retry()）。
        """
        if self._interpreter is not None:
            return getattr(self._interpreter, "service_context", None)
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

    def fallback_visit(self, node_uid: str) -> Any:
        """对未实现的节点回退到原递归 ``visit()`` 路径。

        在 generator handler 内部直接调用即可（同步返回结果）。
        """
        return self._ec.visit(node_uid)

    def assign_to_target(self, target_uid: str, value: Any) -> None:
        """已废弃——由 C7 CPS 重写替代（``_vm_assign_to_target`` generator helper）。

        handlers.py 内部不再调用此方法；保留仅供外部工具链或旧测试脚本的过渡期兼容。
        M3a 早期版本通过 Interpreter 的 ``stmt_handler._assign_to_target`` 间接路径
        完成赋值；C7 之后所有赋值目标均在 handler 内部以 ``yield from`` 方式 CPS 处理。
        """
        if self._interpreter is None:
            raise RuntimeError(
                "VMExecutor.assign_to_target requires interpreter reference; "
                "construct VMExecutor(ec, interpreter=...)"
            )
        # Interpreter 在初始化期间把 stmt_handler 暴露为属性。
        stmt_handler = getattr(self._interpreter, "stmt_handler", None)
        if stmt_handler is None:
            raise RuntimeError("VMExecutor: interpreter.stmt_handler not initialized")
        stmt_handler._assign_to_target(target_uid, value)

    # ------------------------------------------------------------------
    # 主调度循环
    # ------------------------------------------------------------------

    def run(self, node_uid: str) -> Any:
        """执行 ``node_uid`` 的 AST 子树并返回最终结果（IbObject）。

        这是调度循环的入口；不使用 Python 递归。
        """
        if node_uid is None:
            return self.registry.get_none()
        node_uid = self._apply_protection_redirect(node_uid)
        if not self.supports(node_uid):
            # 不支持的根节点：直接走旧路径
            return self.fallback_visit(node_uid)

        return self._drive_loop([self._make_task(node_uid)])

    def run_body(self, stmt_uids: Any) -> Any:
        """C10 + C6：执行一个语句列表（模块或函数体），统一处理 ``node_protection``
        重定向与 ``IbLLMExceptionalStmt`` 直接子节点跳过。

        替代 ``Interpreter.execute_module()`` 与 ``IbUserFunction.call()`` 中
        各自维护的内联 body 循环——既消除重复逻辑，又确保 M4 多 Interpreter
        并发场景下两条路径保持一致。

        参数:
            stmt_uids: 语句 UID 序列（``IbModule.body`` / ``IbFunctionDef.body``）。

        返回:
            最后一条语句的求值结果；空 body 返回 ``IbNone``。

        异常:
            ``ControlSignalException``（C6）：顶层未消费的控制信号直接以
                ``ControlSignalException`` 形式向调用方传播，不再经由
                ``ReturnException`` / ``BreakException`` / ``ContinueException``
                中转。调用方（``IbUserFunction.call``、``execute_module``）直接
                捕获 CSE 并按 ``cse.signal`` 分类处理。
        """
        result = self.registry.get_none()
        for stmt_uid in stmt_uids or ():
            stmt_data = self._ec.get_node_data(stmt_uid)
            if stmt_data and stmt_data.get("_type") == "IbLLMExceptionalStmt":
                # IbLLMExceptionalStmt 直接出现在 body 中：由其 target 的
                # node_protection 重定向驱动，这里直接跳过。
                continue
            result = self.run(stmt_uid)
        return result

    # ------------------------------------------------------------------
    # 内部：调度循环主体（被 run() / future 入口共享）
    # ------------------------------------------------------------------

    def _drive_loop(self, stack: list) -> Any:
        """主调度循环本体；接受预填充的栈，返回最终结果。

        独立成方法让 ``run()`` 和将来其他入口（例如 ``run_body``-内联化）
        共享同一段循环代码，避免漂移。
        """
        # (value, exception) — 互斥；下一次循环将传递给栈顶任务
        pending_value: Any = None
        pending_exception: Optional[BaseException] = None

        while stack:
            self.step_count += 1
            if self.max_steps and self.step_count > self.max_steps:
                raise RuntimeError(
                    f"VMExecutor step limit exceeded ({self.max_steps})"
                )

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
                # M3b：StopIteration.value 若是 Signal，作为控制流数据沿栈传递
                if isinstance(ret_value, Signal):
                    pending_value = ret_value
                else:
                    pending_value = (
                        ret_value if ret_value is not None else self.registry.get_none()
                    )
                continue
            except ControlSignalException as cse:
                # M3b：内部 handler 不再 raise CSE；此分支仅用于 fallback 路径
                # 旧解释器 visit() 抛出的 ReturnException/BreakException/...
                # 走这条路径继续沿生成器栈传播。
                stack.pop()
                pending_exception = cse
                continue
            except Exception as e:
                # 其他运行时异常：弹栈并向上传递
                stack.pop()
                pending_exception = e
                continue

            # 生成器 yield 了一个子节点 uid：决定是 CPS 求值还是 fallback
            if child_uid is None:
                # yield None —— 视作 None 立即返回
                pending_value = self.registry.get_none()
                continue

            if isinstance(child_uid, str):
                # M3d：在调度入口应用 llmexcept 保护重定向
                # （等价于 Interpreter.visit() 顶部的 node_protection 拦截）。
                # 通过比对当前活跃的 LLMExceptFrame.target_uid 避免对正在
                # 被 llmexcept 处理的 target 再次重定向（防止无限递归）。
                child_uid = self._apply_protection_redirect(child_uid)

            if isinstance(child_uid, str) and self.supports(child_uid):
                stack.append(self._make_task(child_uid))
            else:
                # 不支持的子节点：通过 fallback 同步求值，把结果送回父生成器
                try:
                    pending_value = self._ec.visit(child_uid)
                except ControlSignalException as cse:
                    # fallback 路径产生的 CSE：转为 pending_exception 沿栈传递
                    pending_exception = cse
                except Exception as e:
                    pending_exception = e

        # 栈空：处理最终结果
        if pending_exception is not None:
            raise pending_exception
        # M3b：未消费的顶层 Signal → 包装为 ControlSignalException 抛出（边界兼容）
        if isinstance(pending_value, Signal):
            raise ControlSignalException.from_signal(pending_value)
        return pending_value if pending_value is not None else self.registry.get_none()

    # ------------------------------------------------------------------
    # 内部：任务构造
    # ------------------------------------------------------------------

    def _make_task(self, node_uid: str) -> VMTask:
        node_data = self._ec.get_node_data(node_uid)
        if not node_data:
            return self._make_const_task(node_uid, self.registry.get_none())
        node_type = node_data.get("_type")
        handler = self._dispatch.get(node_type)
        if handler is None:
            # 调用方已通过 supports() 排除，不应到达
            raise RuntimeError(
                f"VMExecutor: no CPS handler for node type {node_type!r} "
                f"(uid={node_uid})"
            )
        gen = handler(self, node_uid, node_data)
        return VMTask(node_uid=node_uid, generator=gen)

    def _apply_protection_redirect(self, node_uid: str) -> str:
        """应用 llmexcept 保护重定向（与 ``Interpreter.visit()`` 顶部语义一致）。

        若 ``node_uid`` 在 ``node_protection`` 侧表中且当前没有任何活跃的
        ``LLMExceptFrame`` 正在保护该节点，则返回对应的 IbLLMExceptionalStmt
        UID；否则原样返回。

        "已在被保护中" 的判定通过比对 ``LLMExceptFrame.target_uid`` 实现：
        当 ``vm_handle_IbLLMExceptionalStmt`` 通过 ``yield target_uid``
        驱动 target 执行时，调度器需要直接执行 target 而非再次走重定向，
        否则会形成 ``llmexcept ↔ target`` 的无限循环。
        """
        if not isinstance(node_uid, str):
            return node_uid
        handler_uid = self._ec.get_side_table("node_protection", node_uid)
        if not handler_uid:
            return node_uid
        # 检查活跃 LLMExceptFrame 是否已经在保护此 target
        rc = self.runtime_context
        if rc is not None and hasattr(rc, "get_llm_except_frames"):
            for frame in rc.get_llm_except_frames():
                if getattr(frame, "target_uid", None) == node_uid:
                    return node_uid  # 已被保护中，跳过重定向
        return handler_uid

    def _make_const_task(self, node_uid: str, value: Any) -> VMTask:
        """把一个已知值包装成立即完成的任务（仅供未知节点 fallback）。"""
        def _gen():
            return value
            yield  # pragma: no cover
        return VMTask(node_uid=node_uid, generator=_gen())
