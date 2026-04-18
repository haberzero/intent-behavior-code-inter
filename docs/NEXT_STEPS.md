# IBC-Inter 近期优先任务

> 记录接下来可以直接开工的具体任务，按优先级排列。  
> 中长期任务见 `docs/PENDING_TASKS.md`，已完成工作见 `docs/COMPLETED.md`。  
> VM 架构长期设想见 `docs/PENDING_TASKS_VM.md`。
>
> **最后更新**：2026-04-18（Step 4b 完成；VM 架构路线讨论完成；
> 下一重点：Step 5 IbFunction.call() 去除 context 依赖 + Step 6 IbIntentContext 公理化设计）

---

## 1. Step 5：IbFunction.call() 去除 context 参数依赖 [P1 - 当前主线]

**背景**：`IbUserFunction.call(self, receiver, args)` / `IbNativeFunction.call()` 当前仍通过外部传入 `execution_context` 执行，与"函数对象自洽执行"的公理化原则冲突（`IbBehavior` 已通过 `_execution_context` 捕获实现了自洽，IbUserFunction 还没有）。

**技术方案（已明确）**：引入 `contextvars.ContextVar[IExecutionFrame]` 作为"CPU 上下文切换寄存器"。  
- 新文件 `core/runtime/frame.py`：暴露 `get_current_frame()` / `push_frame(frame)` 两个全局函数  
- `Interpreter.execute_module()` / `run()` 入口设置 ContextVar（`token = push_frame(exec_ctx)`）  
- `IbUserFunction.call()` 通过 `get_current_frame()` 自主获取当前执行帧，不再需要 context 参数  
- `IbBehavior` 的意图捕获语义澄清：**意图是定义时捕获的（snapshot），执行帧是调用时获取的（ContextVar）**

**选择 ContextVar 的原因**：asyncio 协程安全（Task 创建时自动复制父 Context）；嵌套 set/reset 原子性；与 Python 生态（FastAPI/Starlette）对齐。详见 `docs/PENDING_TASKS_VM.md` 层次 1。

**注意**：此步骤是 Step 6（意图栈公理化）的前提。在开工前需确认"帧的生命周期与意图 context 生命周期如何对齐"。

**文件**：`core/runtime/objects/kernel.py`（IbUserFunction）、`core/runtime/interpreter/interpreter.py`（执行入口）、新增 `core/runtime/frame.py`

---

## 2. Step 6：IbIntentContext 公理化 [P1 - 设计阶段]

**背景**：当前意图栈是 `RuntimeContextImpl` 中的全局可变状态（`_intent_top`、`_pending_smear_intents` 等），函数调用时意图栈的继承/隔离语义不明确。

**设计目标**（详见 `docs/PENDING_TASKS_VM.md` 第四节）：  
- 将意图栈本身实例化为 `IbIntentContext`，成为公理体系中的类型  
- 明确语义：**默认是帧级隔离（进入函数时 fork 快照），显式传递才是引用共享**  
- 函数内 `@+ intent` 仅修改当前帧的 IntentContext，不影响父帧  
- `IExecutionFrame.intent_context` 持有当前帧的 `IbIntentContext` 引用  
- 全局意图（`@@ intent`）写入 Engine 级全局 IntentContext，跨帧持久

**前提**：Step 5 完成（IExecutionFrame 作为第一公民存在，才能让 IntentContext 绑定到帧）。

**文件**：新增 `core/kernel/axioms/intent_context.py`、`core/runtime/objects/intent_context.py`；重构 `core/runtime/interpreter/runtime_context.py`（将意图相关字段迁出）

---

## 3. 概念边界文档化 [P2 - 不阻塞代码工作]

**背景**：Interpreter / Engine / IExecutionFrame / DynamicHost 四个概念的职责边界已在 `docs/PENDING_TASKS_VM.md` 第五节明确定义，但尚未体现在代码注释中。

**任务**：  
- 在 `core/runtime/interpreter/interpreter.py` 头部注释中明确 Interpreter 的职责边界  
- 在 `core/engine.py` 头部注释中明确 Engine 是"组装者"的角色  
- 在 `core/runtime/host/service.py` 头部注释中明确 DynamicHost 是"编排者而非执行者"  
- 明确多 Interpreter 实例的创建/销毁规范（禁止共享可变 RuntimeContext）

---

*本文档记录近期可执行任务。中长期任务见 `docs/PENDING_TASKS.md`；VM 架构长期设想见 `docs/PENDING_TASKS_VM.md`。*

