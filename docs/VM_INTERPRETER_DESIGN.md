# IBCI VM 与解释器架构设计说明（当前正式版）

> 本文档描述**当前代码状态**下的 VM 与解释器正式架构。
> 历史里程碑和旧演进路线不作为当前规范。
>
> 最后更新：2026-05-08

---

## 1. 执行模型

- 主路径：`VMExecutor` CPS 调度循环
- 单元：`VMTask` 生成器任务栈
- 控制流：`Signal(kind, value)` 数据化传播
- 顶层未消费信号：`UnhandledSignal`

---

## 2. 解释器与 VM 分工

- Interpreter：装配上下文、模块/作用域/服务注入
- VMExecutor：节点调度与执行主循环
- handlers：节点级 CPS 语义实现

---

## 3. llmexcept 与快照隔离

- `LLMExceptFrame` 保存变量/意图上下文/循环上下文快照
- retry 前恢复快照，保证重试输入一致
- LLM 不确定性通过 `LLMResult` 结构传递，不依赖跨帧异常链

---

## 4. LLM 调度（程序内并发）

- `dispatch_eligible=True` 的 behavior 走 eager dispatch
- 运行时使用 `LLMFuture` 占位，变量使用点再 resolve
- 对 cell 捕获变量，编译期强制 `dispatch_eligible=False`，避免向 cell 写入 future 占位

---

## 5. Intent 上下文在执行模型中的位置

- `RuntimeContextImpl` 持有 `_intent_ctx: IbIntentContext`
- 函数调用时 fork 子上下文，返回时恢复调用者上下文
- `lambda` 与 `snapshot` 在 callable-instance 层分别对应“调用时上下文”与“创建时冻结上下文”

---

## 6. 当前后续收敛重点

- 注释语法路径与 `intent_context` 对象路径收敛
- callable-instance 历史命名与注释清理（减少“deferred”旧语义噪音）
- `llm_uncertain` 在字符串拼接与真值路径的过渡策略收口
