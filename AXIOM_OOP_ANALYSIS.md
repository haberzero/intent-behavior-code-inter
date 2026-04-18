# 公理体系 / 万物皆对象 — 架构分析与迭代路线

> 本文件记录 IBC-Inter 公理化/面向对象重构的架构分析结论与设计决策，供未来 PR 迭代使用。
>
> **最后更新**：2026-04-18（第八次修订：§8 OOP×Protocol 边界清理完成——`IIbObject.descriptor` 幽灵字段删除，所有显式 Protocol 继承链条清除，所有 Protocol isinstance 替换为具体实现类检查，`_get_llmoutput_hint` 死代码路径修复，497 个测试全部通过）
>
> 当前已完成的修复见第五章，正在进行中的工作见第四章，未来远期高风险任务见第六章，OOP×Protocol 边界清理（已完成）见第八章。

---

## 一、现状：哪些东西已经公理化，哪些还没有

### 已完整公理化的类型

| 类型 | Spec | Axiom | IbObject | 自洽 `call()` |
|------|------|-------|----------|--------------|
| int / float / str / bool | ✅ | ✅ | ✅ | ✅ |
| list / tuple / dict | ✅ | ✅ | ✅ | ✅ |
| None / slice / Exception | ✅ | ✅ | ✅ | ✅ |
| Enum | ✅ | ✅ | ✅ | ✅ |
| bound_method | ✅ | ✅ | ✅ | ✅ |
| **callable** | ✅ | ✅（`CallableAxiom`） | N/A（抽象父类型） | N/A |
| **deferred** | ✅（`DeferredSpec`） | ✅（`DeferredAxiom`） | ✅（`IbDeferred`） | ✅ |
| **behavior** | ✅ | ✅（`BehaviorAxiom`） | ✅（`IbBehavior.call()` 自主执行） | ✅ |
| **void** | ✅（`VOID_SPEC`） | ✅（`VoidAxiom`，`is_dynamic=False`） | N/A（无返回值标注） | N/A |
| **IbLLMFunction** | ✅（`FuncSpec(is_llm=True)`） | 部分（FuncSpec） | ✅ | ✅（Step 4a 完成，通过 `registry.get_llm_executor()` 自主执行） |

### 尚未完整公理化的类型

| 类型 | 问题描述 |
|------|---------|
| **IbFunction** | `call()` 需要外部传入 `context`（`IExecutionContext`），不能自主执行。是 Step 5（线程本地存储）的目标，当前功能正确，属架构不优雅而非 Bug。 |
| **Intent** | 内置 ClassSpec（通过 `Bootstrapper.initialize()` 创建），无专用 Axiom。完整 IntentAxiom 公理化属于 Step 6 长期目标。 |

### 公理类型层次（当前完整状态）

```
Object（根）
  ├─ int / float / str / bool / list / tuple / dict / None / slice / Exception / Enum
  ├─ void   (VoidAxiom, is_dynamic=False) — 无返回值的函数返回类型标注
  └─ callable  (CallableAxiom, is_dynamic=False) — 可调用对象的公理父类型
       ├─ bound_method  (BoundMethodAxiom) — 已绑定接收者的方法
       └─ deferred  (DeferredAxiom) — 延迟执行的通用表达式
            └─ behavior  (BehaviorAxiom) — 延迟执行的 LLM 行为表达式（特化）
```

**注意**：此层次是 IBCI 类型系统（公理层）的声明，与 Python 实现类的继承无关。
`IbDeferred` 和 `IbBehavior` 都直接继承自 `IbObject`，不存在 Python 级别的互相继承关系——
这是有意为之：两者的执行机制（AST 重访 vs LLM 调用）完全不同，不应共享实现代码。
IBCI 类型系统通过公理声明类型层次，Python 类继承只用于实现代码复用。

### `is_compatible(target)` 方向原则

`is_compatible(target_name)` 的语义是：**"我（source 类型）能否被赋值给 `target_name` 类型的变量？"**

子类型向上兼容，父类型不向下兼容：

| source | 可赋值的目标类型 |
|--------|---------------|
| behavior | behavior、deferred、callable |
| deferred | deferred、callable |
| callable | callable（仅自身） |
| bound_method | bound_method、callable |

**禁止的反向赋值**：`callable → deferred`、`callable → behavior`、`deferred → behavior` 均为非法，
`is_compatible()` 现已正确返回 False（已修复历史 Bug）。

---

## 二、核心诊断：为什么 `behavior` 无法自洽

根本原因不是"behavior 的公理怎么写"，而是 **`LLMExecutor` 的归属没有明确定义**。

### 当前架构中 `LLMExecutor` 的位置

```
ServiceContext
  ├── llm_executor        ← 问题所在：既是"内核服务"又是"潜在可替换插件"
  ├── issue_tracker
  └── debugger
```

`IbBehavior` 是一个 IBC-Inter 对象（有 `IbClass`、有 Spec），但它执行时需要 `llm_executor`。由于 `llm_executor` 不在 `KernelRegistry` 内，`IbBehavior` 无法在 `call()` 中合法地拿到它，因此 `call()` 被设计为抛异常，实际执行权交给 handler 层。

这就是"behavior 公理化最后一公里"卡住的真正原因。

### 同样问题的其他对象

- `IbFunction.call(context, args)` — `context` 参数本质上是同一个问题：函数执行需要解释器环境，而解释器环境不在对象体系内。
- `ibci_ihost`、`ibci_idbg` 等核心插件 — 它们需要访问 `HostService`/`debugger`，但这些服务同样游离于对象体系之外。

---

## 三、架构重构方向：已确认的核心设计决策

### 3.1 @~...~ 是语言核心特性，不依赖 `import ai`

**已确认**：`@~ ... ~` 行为描述语句是 IBC-Inter 的语言核心特性，**不应该依赖于 `import ai` 显式导入**。

- `import ai` 的职责仅是：配置 LLM provider（API key、模型名称、重试次数、提示词自定义等）
- 从语言原则上讲，`@~...~` 作为一等公民存在，LLM 执行能力由内核提供
- 用户不可能在未配置 LLM provider 的情况下真正完成调用——但这是**运行时约束**，而非**语言层约束**
- 这意味着：`LLMExecutor` 的执行接口属于内核服务，`ibci_ai` 只负责注册和配置具体的 LLM provider 实现

### 3.2 架构分层：三层切割

```
┌─────────────────────────────────────────────────────────────┐
│  第一层：KernelServices（永远不可替换，调用语义固定）            │
│  - IILLMExecutor（接口）：behavior 执行的内核入口              │
│  - KernelRegistry：类型体系、对象注册表、内核服务注册           │
│  - AxiomRegistry：公理体系                                    │
│  → 硬编码进解释器；IbBehavior.call() 通过接口安全调用           │
│  → kernel 层只依赖 IILLMExecutor 接口，实现由外部注入           │
├─────────────────────────────────────────────────────────────┤
│  第二层：HostServices（可配置，接口固定）                       │
│  - LLM provider 实现（ibci_ai 提供，注入到 IILLMExecutor）     │
│  - HostService（run_isolated 等）                             │
│  → 通过 import ai 配置，接口是稳定合约                          │
├─────────────────────────────────────────────────────────────┤
│  第三层：ExtensionPlugins（真正的用户插件）                     │
│  - ibci_math / net / json / time / schema / file 等            │
│  - 高级用户自定义扩展                                          │
│  → 走完整 IbPlugin 体系，无法接触内核状态                       │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 kernel 层不允许架构穿透

**核心原则**：`kernel` 层在公理化过程中不能直接依赖具体的 `LLMExecutorImpl`。

**正确做法**（接口注入模式）：

```
kernel/interfaces/ 中定义：
    IILLMExecutor(Protocol)
        execute_behavior_expression(node_uid, context, ...) -> LLMResult
        execute_behavior_object(behavior, context) -> IbObject

KernelRegistry 中：
    register_llm_executor(executor: IILLMExecutor, token: KernelToken) → None
    get_llm_executor() → IILLMExecutor

IbBehavior.call() 中：
    executor = self.ib_class.registry.get_llm_executor()
    return executor.execute_behavior_object(self, ...)
```

**禁止的做法**（架构穿透）：

```
# ❌ 不允许：kernel 层直接 import 具体实现
from core.runtime.interpreter.llm_executor import LLMExecutorImpl
```

`IILLMExecutor` 接口在 `kernel/interfaces/` 或 `kernel/spec/` 下定义，仅包含执行行为所需的最小 API，不涉及任何解释器具体实现。

### 3.4 BehaviorCallCapability 的返回类型：`"auto"` 是正确的现阶段设计

**实际实现**：`BehaviorCallCapability.resolve_return_type_name()` 返回 `"auto"`（编译期延迟），运行时通过 `push_expected_type(behavior.expected_type)` 在 LLM 调用时强制解析为具体类型。

**为什么不能直接返回 `behavior.expected_type`**：`CallCapability.resolve_return_type_name(self, arg_type_names: List[str])` 是**编译期接口**，参数为类型名字符串列表，在协议层面**无法持有** IbObject 实例（`IbBehavior`）。任何试图从接口内访问 `receiver.expected_type` 的伪代码在当前架构下都无法实现。

**`"auto"` ≠ `"any"`**：
- `"any"` 表示"放弃类型信息"（永久未知）
- `"auto"` 表示"编译期延迟，运行时精确解析"

运行时路径：`invoke_behavior()` → `push_expected_type(behavior.expected_type)` → LLM 结果被约束为 `expected_type` 对应的类型。类型约束从未丢失，只是延迟到运行时生效。

**✅ 已解决（本 PR）**：
- `BehaviorSpec(value_type_name="int")` 已在当前 PR 中完整实现（详见 §6.4 COMPLETED 记录）。
- `int result = compute()` 编译期不再产生 SEM_003 错误。
- `SpecRegistry.resolve_return()` 对 `DeferredSpec`/`BehaviorSpec` 且 `value_type_name` 非 auto 时，直接返回声明的值类型。

### 3.5 彻底重构原则（禁止渐进式补丁）

**已确认**：公理化和面向对象体系的重构**必须以彻底且清晰明确的方式进行深层次结构性重构，不允许留下渐进式的补丁妥协**。

具体含义：
- 不允许为新公理化类型保留旧的 `DynamicAxiom` 占位符
- 不允许 `IbBehavior.call()` 继续抛 `RuntimeError`（这是临时状态，必须彻底消除）
- 不允许 `_execute_behavior()` 旁路在 `BehaviorAxiom` 完成后继续存在
- 不允许 `"behavior"` 硬编码字符串在任何新增代码中出现（已有的 `is_behavior()` 是正确做法）
- 每个完成的重构步骤必须是完整的、不留后门的——要么完全迁移，要么不动

### 3.6 显式 import 原则保留

`import ai`、`import ihost`、`import idbg` 等显式导入**必须保留**。用户代码中的显式导入是清晰的依赖声明，是好的设计。

但这与"@~...~ 是语言核心特性"不矛盾：
- `@~...~` 的执行能力由内核提供（`IILLMExecutor` 接口）
- `import ai` 是向内核注册具体 LLM provider 实现的入口
- `import ihost`/`import idbg` 暴露了宿主服务/调试服务的 IBCI 接口，与它们的内部实现方式无关

### 3.7 明确放弃的设计

- ❌ 允许用户插件替换解释器运行逻辑（元操作）
  - 理由：与公理化方向对立。一旦解释器行为可被任意替换，所有公理定义都退化为"当前插件下的公理"，语言丧失确定性语义。
- ❌ `LLMExecutor` 的具体实现（`LLMExecutorImpl`）作为可替换插件
  - 理由：它是语言语义的一部分，不是外部扩展。provider 可配置，执行接口不可替换。
- ❌ 渐进式补丁修复（在旧结构上打补丁）
  - 理由：公理化的正确性要求结构完整性，打补丁最终导致两套并行体系，增加维护负担。

---

## 四、下一步迭代路线图（完整版）

### Step 1 ✅ COMPLETED（已于本轮落地）

**确立 `IILLMExecutor` 接口 + 注入 `KernelRegistry`**

已完成内容：
1. `IILLMExecutor` Protocol 在 `core/base/interfaces.py` 定义：
   - `invoke_behavior(behavior, context) -> IbObject`
   - `execute_behavior_expression(node_uid, context, call_intent=None, captured_intents=None) -> LLMResult`
   - `execute_behavior_object(behavior, context) -> LLMResult`
   - `get_last_call_info() -> Dict`
2. `KernelRegistry` 增加了：
   - `register_llm_executor(executor, token)` （内核令牌保护，免封印检查）
   - `get_llm_executor() -> IILLMExecutor`
   - `clone()` 传播 `_llm_executor` 引用
3. `LLMExecutorImpl` 新增 `invoke_behavior()` 方法
4. `engine._prepare_interpreter()` 完成后将 `llm_executor` 注入 `KernelRegistry`

---

### Step 2 ✅ COMPLETED（已于本轮落地，与 Step 1 同一 PR）

**给 `behavior` 类型声明真正的 `BehaviorAxiom` + `BehaviorCallCapability`**

已完成内容：
1. `BehaviorAxiom` 替换 `DynamicAxiom("behavior")`：
   - `is_dynamic() = False` —— `behavior` 是一等公民具体类型，**严格不等于 `any`**
   - `is_compatible()` 为身份匹配
   - `BehaviorCallCapability.resolve_return_type_name()` 返回 `"auto"`（编译期延迟，运行期按 `expected_type` 解析）
2. `IbBehavior` 完成公理化重构：
   - 构造时捕获 `execution_context`（与 `IbUserFunction` 同构模式）
   - `call()` 通过 `registry.get_llm_executor().invoke_behavior(self, ctx)` 自主执行
   - 不再抛 `RuntimeError`
3. `_execute_behavior()` **已从 `BaseHandler` 彻底删除**
4. `visit_IbCall` 中的 `is_behavior()` 特殊路由 **已删除** —— behavior 通过标准 `hasattr(func, 'call')` 分支流转
5. `visit_IbExprStmt` 中的 `_execute_behavior(res)` **已替换为** `res.call(none, [])`
6. `IObjectFactory.create_behavior()` 和 `RuntimeObjectFactory.create_behavior()` 均新增 `execution_context` 参数
7. `expr_handler.visit_IbBehaviorExpr` 向 `create_behavior()` 传入 `execution_context`

**质量门控**：Step 2 完成后，446 个测试全部通过，代码中不再存在 `_execute_behavior` 调用路径。

---

### Step 3 ✅ COMPLETED（Step 3a 完成于本轮，Step 3b 完成于上轮）

**`ibci_ai` 职责拆分（Step 3a）+ 通用可调用类型公理化（Step 3b）**

#### Step 3a（本轮完成）

`ibci_ai` 职责已完整拆分：

| 当前职责 | 拆分后归属 |
|---------|-----------|
| LLM API 调用（OpenAI/Ollama 等的 HTTP 请求） | 注入到 `KernelRegistry.llm_executor`（Step 1 完成后自然实现） |
| LLM 配置 API（`set_retry`、`set_context`、`set_model`）| 保留在 `ibci_ai` 插件，通过 `import ai` 显式使用 |
| `IbStatefulPlugin` 断点保存/恢复（LLM 配置状态） | 保留在 `ibci_ai` 插件 |

**关键改动**：
- `LLMExecutorImpl.llm_callback` 属性中**删除旧的 `interop.get_package("ai")` 回退路径**；
  现在 Provider 的唯一来源是 `capability_registry.get("llm_provider")`，
  由 `ibci_ai.setup(capabilities)` 在加载时通过 `capabilities.expose("llm_provider", self)` 注册。
- `execute_behavior_expression` 中**删除 `ai_module = self.interop.get_package("ai")` 直接访问**；
  `auto_intent_injection` 配置和 `_retry_hint` 回退均改为经由已注册的 `self.llm_callback` 读取。

**拆分后**：
- `ibci_ai` 的 IBCI 接口（`ai.set_retry()` 等）继续正常工作
- `@~...~` 的执行不再路由经过 `ibci_ai` 模块名，而是 100% 通过 `KernelRegistry.get_llm_executor()` 执行
- `ibci_ai.setup(capabilities)` 是向内核注册具体 LLM provider 的唯一注册入口

#### Step 3b（上轮完成，见前次修订）

已完成内容：
- `CallableAxiom` 替代 `DynamicAxiom("callable")`，`is_dynamic()=False`
- `DeferredAxiom`、`DeferredSpec`、`IbDeferred` 通用延迟表达式完整落地
- `is_compatible()` 方向 Bug 修复

---

### Step 4a ✅ COMPLETED（本 PR）

**`IbLLMFunction` 公理化补完 + `visit_IbBehaviorInstance` 清理**

#### 背景：Step 3a 完成后暴露的残余问题

Step 3a 将 `llm_callback` 单源化到 `capability_registry.get("llm_provider")` 后，`IbLLMFunction`（命名 LLM 函数 `llm f(...) -> str: ...`）成为整个 LLM 执行链中**唯一尚未公理化的组件**，存在三个严重问题：

1. **构造器持有 `llm_executor` 引用**：`IbLLMFunction.__init__` 接受并存储 `llm_executor` 参数，与 `IbBehavior` 已完成的改造（Step 2）不一致。若 executor 在对象创建后被替换，持有的是旧引用。
2. **`call()` 返回 `LLMResult` 而非 `IbObject`**：`execute_llm_function` 返回 `LLMResult`，但 `call()` 签名是 `-> IbObject`——类型合约被违反。调用者（如 `visit_IbCall`）会拿到 `LLMResult` 对象而非 `IbObject`。
3. **`set_last_llm_result` 从未被调用**：`llmexcept` 的不确定性检查对命名 LLM 函数调用**完全失效**——`llmexcept` 保护不会触发。

另外，`visit_IbBehaviorInstance`（`(Type) @~...~` 废弃语法路径）仍直接访问 `service_context.llm_executor` 而非 `registry.get_llm_executor()`，与 Step 3a 的单源化原则冲突。

#### 已完成内容

**`IILLMExecutor` 接口扩展**：
- 新增 `invoke_llm_function(func, context) -> Any`，与 `invoke_behavior` 对称，是 `IbLLMFunction.call()` 的唯一执行分发点
- 位于 `core/base/interfaces.py`

**`LLMExecutorImpl.invoke_llm_function()` 实现**：
- 从 `func._pending_call_intent` 提取呼叫级意图（由 `IbLLMFunction.call()` 在调用前解析并暂存）
- 委托给 `execute_llm_function` 完成 LLM 推理
- 调用 `execution_context.runtime_context.set_last_llm_result(result)` 回写，修复 `llmexcept` 失效问题
- 返回 `result.value`（`IbObject`），类型合约完整

**`IbLLMFunction` 公理化重构**（与 `IbBehavior` Step 2 同构）：
- `__init__` 移除 `llm_executor` 参数，不再持有 executor 引用
- `call()` 通过 `self.ib_class.registry.get_llm_executor()` 获取执行器
- 解析呼叫级意图后暂存到 `self._pending_call_intent`，finally 块清除
- 调用 `executor.invoke_llm_function(self, self.context)` 完成自主执行
- 添加 executor 为 None 时的明确 RuntimeError 提示

**调用方更新**（移除旧的 `llm_executor` 参数传递）：
- `stmt_handler.visit_IbLLMFunctionDef`：`IbLLMFunction(node_uid, self.execution_context, ...)` 不再传 executor
- `interpreter.py` STAGE 5 预水化：同上

**`visit_IbBehaviorInstance` 清理**：
- 改为 `executor = self.registry.get_llm_executor()` + `executor.execute_behavior_expression(...)`
- executor 为 None 时静默返回 `get_none()`，不崩溃

**质量门控**：484 个测试全部通过（含 `TestE2ELLMFunctions.test_llm_function_call`、`TestE2ELLMExcept` 等）。

---

### Step 4b（独立 PR，中期目标）

**`ibci_ihost` 和 `ibci_idbg` 的重构分析与执行**

#### 当前结构

**`ibci_ihost`**：
- 继承 `IbPlugin`，通过 `capabilities.service_context.host_service` 访问 `HostService`
- IBCI 接口：`ihost.run_isolated(path, policy)` 等
- 问题：通过 `IbPlugin` 特权访问内核服务，而非通过公开接口

**`ibci_idbg`**：
- 继承 `IbPlugin`，通过 `capabilities.stack_inspector`、`capabilities.state_reader`、`capabilities.llm_executor` 访问内核状态
- IBCI 接口：`idbg.dump_stack()`、`idbg.inspect()`、`idbg.trace()` 等
- 问题：深度依赖 `ExtensionCapabilities` 中的内核内部结构

#### 重构目标

| 目标 | 说明 |
|------|------|
| 保留 IBCI 显式 import 接口 | `import ihost`/`import idbg` 继续作为用户代码的显式入口 |
| 去除 `IbPlugin` 内核特权访问 | 改为通过 `KernelRegistry` 的稳定钩子接口访问服务 |
| `HostService` 通过 `KernelRegistry` 暴露 | 在 `KernelRegistry` 中增加 `get_host_service()` 钩子 |
| 调试器能力通过协议接口暴露 | 定义 `IStackInspector`、`IStateReader` 为 kernel 层接口 |

**重构后**：`ibci_ihost` 和 `ibci_idbg` 降级为"标准插件"，不再需要 `IbPlugin` 特权层级，通过与非侵入式插件一致的 setup 机制获取所需接口。但它们的 IBCI 接口（用户可见的方法）保持不变。

**注意**：此步骤依赖 Step 1（`KernelRegistry` 的服务注册机制建立），因此在 Step 1 完成后才可开展。

---

### Step 5（长期，全局架构工作）

**`IbFunction.call()` 去除 `context` 参数依赖**

将解释器环境的获取方式改为通过 `ib_class.registry` 拿到 `KernelRegistry`，再由 `KernelRegistry` 提供"当前执行上下文"钩子。

**⚠️ 此步骤的线程本地存储方案记录于第六章，属于高风险设计，需要单独讨论后推进。**

---

### Step 6（长期）

**万物皆对象完整化**

- ~~`BehaviorSpec(return_type_name=...)` 编译期返回类型推断（详见 §6.4）~~ ✅ COMPLETED（本 PR）
- `Intent` 完整公理化（`IntentAxiom`，详见 §6.2）
- 消除 `ServiceContext` 中所有游离于对象体系之外的"隐式依赖"

---

## 五、已完成的修复记录

| 修复 | 优先级 | 文件 | PR |
|------|--------|------|----|
| `_bind_llm_except` 递归进入嵌套控制流块（IbFor/IbIf/IbWhile/IbTry/IbSwitch） | P0 | `core/compiler/semantic/passes/semantic_analyzer.py` | copilot/check-ibc-inter-design-docs |
| `SpecRegistry.is_behavior(spec)` 方法，消除 `"behavior"` 硬编码字符串比较 | P1 | `core/kernel/spec/registry.py` | copilot/check-ibc-inter-design-docs |
| `visit_IbCall` behavior 检测改为通过 `spec_reg.is_behavior()` 路由 | P1 | `core/runtime/interpreter/handlers/expr_handler.py` | copilot/check-ibc-inter-design-docs |
| `semantic_analyzer.py visit_IbFor` 中 `"behavior"` 硬编码改为 `is_behavior()` | P1 | `core/compiler/semantic/passes/semantic_analyzer.py` | 当前 PR |
| `IBCI_SPEC.md`：删除废弃 `callable` 类型，补充 `lambda`/`snapshot` 语法，修正废弃示例 | 文档 | `IBCI_SPEC.md` | 当前 PR |
| `PENDING_TASKS.md §11.7`：标注为 COMPLETED | 文档 | `docs/PENDING_TASKS.md` | 当前 PR |
| **`IILLMExecutor` 接口定义**（Step 1） | 架构 | `core/base/interfaces.py` | copilot/ibc-inter-design-review |
| **`KernelRegistry.register_llm_executor()` / `get_llm_executor()`**（Step 1） | 架构 | `core/kernel/registry.py` | copilot/ibc-inter-design-review |
| **`LLMExecutorImpl.invoke_behavior()`**（Step 1） | 架构 | `core/runtime/interpreter/llm_executor.py` | copilot/ibc-inter-design-review |
| **`engine._prepare_interpreter()` 注入 executor**（Step 1） | 架构 | `core/engine.py` | copilot/ibc-inter-design-review |
| **`BehaviorAxiom` + `BehaviorCallCapability`**（Step 2） | 架构 | `core/kernel/axioms/primitives.py` | copilot/ibc-inter-design-review |
| **`IbBehavior.call()` 自主执行 + `execution_context` 捕获**（Step 2） | 架构 | `core/runtime/objects/builtins.py` | copilot/ibc-inter-design-review |
| **`_execute_behavior()` 从 `BaseHandler` 彻底删除**（Step 2） | 架构 | `core/runtime/interpreter/handlers/base_handler.py` | copilot/ibc-inter-design-review |
| **`visit_IbCall` `is_behavior()` 特殊路由删除**（Step 2） | 架构 | `core/runtime/interpreter/handlers/expr_handler.py` | copilot/ibc-inter-design-review |
| **`visit_IbExprStmt` 改为 `res.call()`**（Step 2） | 架构 | `core/runtime/interpreter/handlers/stmt_handler.py` | copilot/ibc-inter-design-review |
| **`create_behavior()` 新增 `execution_context` 参数**（Step 2） | 架构 | `core/runtime/factory.py`、`core/runtime/interfaces.py` | copilot/ibc-inter-design-review |
| **`CallableAxiom` 替代 `DynamicAxiom("callable")`**（Step 3b） | 架构 | `core/kernel/axioms/primitives.py` | copilot/review-docs-and-code |
| **`DeferredAxiom` + `DeferredSpec` + `IbDeferred` 通用延迟表达式**（Step 3b） | 架构 | `core/kernel/`, `core/runtime/objects/builtins.py` | copilot/review-docs-and-code |
| **`is_compatible()` 方向 Bug 修复**：父类型不再反向向下兼容子类型 | P0 | `core/kernel/axioms/primitives.py` | copilot/review-docs-and-code |
| **`BoundMethodAxiom.is_compatible("callable")` 补充**：bound_method IS-A callable | P0 | `core/kernel/axioms/primitives.py` | copilot/review-docs-and-code |
| **`VoidAxiom` 替代 `DynamicAxiom("void")`**：is_dynamic=False，无任何能力，is_compatible 仅 "void" | P0 | `core/kernel/axioms/primitives.py` | copilot/review-docs-and-code |
| **Step 3a：`LLMExecutorImpl.llm_callback` 删除 `interop.get_package("ai")` 回退路径** | 架构 | `core/runtime/interpreter/llm_executor.py` | copilot/check-architecture-and-documentation |
| **Step 3a：`execute_behavior_expression` 删除直接 `ai_module` 访问，改为 `self.llm_callback`** | 架构 | `core/runtime/interpreter/llm_executor.py` | copilot/check-architecture-and-documentation |
| **文档修正：`DESIGN_TASKS.md §1.1` 标记为 ✅ DONE** | 文档 | `DESIGN_TASKS.md` | copilot/check-architecture-and-documentation |
| **文档修正：`DESIGN_TASKS.md §4.3` Intent 描述更正**（无 `DynamicAxiom("intent")` 占位符） | 文档 | `DESIGN_TASKS.md` | copilot/check-architecture-and-documentation |
| **Step 4a：`IILLMExecutor` 新增 `invoke_llm_function()` 接口** | 架构 | `core/base/interfaces.py` | 本 PR |
| **Step 4a：`LLMExecutorImpl.invoke_llm_function()` 实现**（修复 llmexcept 失效 + 返回 IbObject） | 架构 | `core/runtime/interpreter/llm_executor.py` | 本 PR |
| **Step 4a：`IbLLMFunction` 移除 `llm_executor` 参数，`call()` 改为 `registry.get_llm_executor()`** | 架构 | `core/runtime/objects/kernel.py` | 本 PR |
| **Step 4a：`visit_IbLLMFunctionDef` 移除 `llm_executor` 传参** | 架构 | `core/runtime/interpreter/handlers/stmt_handler.py` | 本 PR |
| **Step 4a：`interpreter.py` STAGE 5 预水化移除 `llm_executor` 传参** | 架构 | `core/runtime/interpreter/interpreter.py` | 本 PR |
| **Step 4a：`visit_IbBehaviorInstance` 改为 `registry.get_llm_executor()` 访问** | 架构 | `core/runtime/interpreter/handlers/expr_handler.py` | 本 PR |
| **`BehaviorSpec(DeferredSpec)` 新增**：`get_base_name()` 返回 `"behavior"`，携带 `value_type_name`（§6.4） | 架构 | `core/kernel/spec/specs.py` | copilot/check-architecture-and-documentation |
| **`SpecFactory.create_behavior(value_type_name, deferred_mode)`**：类型化 BehaviorSpec 工厂方法 | 架构 | `core/kernel/spec/registry.py` | copilot/check-architecture-and-documentation |
| **`SpecRegistry.resolve_return()` DeferredSpec/BehaviorSpec 分支**：有 value_type_name 时编译期推断返回类型 | 架构 | `core/kernel/spec/registry.py` | copilot/check-architecture-and-documentation |
| **`semantic_analyzer.py` deferred_mode + 具体类型 → 创建 BehaviorSpec/DeferredSpec**（替代通用占位符） | 架构 | `core/compiler/semantic/passes/semantic_analyzer.py` | copilot/check-architecture-and-documentation |
| **`serializer.py` 持久化 `value_type_name` + `deferred_mode`** | 架构 | `core/compiler/serialization/serializer.py` | copilot/check-architecture-and-documentation |
| **`artifact_rehydrator.py` 重建 BehaviorSpec/DeferredSpec 正确子类**（修复运行时 RUN_002 赋值错误） | 架构 | `core/runtime/loader/artifact_rehydrator.py` | copilot/check-architecture-and-documentation |

---

## 六、远期高风险任务记录（待未来 PR 推进）

### 6.1 `IbFunction.call()` 线程本地存储方案

**问题**：`IbFunction.call(context, args)` 中的 `context`（`IExecutionContext`）是同一类问题——函数执行需要解释器环境。当前通过外部传入，与公理化"对象自洽执行"原则冲突。

**潜在方案**：将"当前活跃的 `IExecutionContext`"注入到 `KernelRegistry` 作为线程本地（Thread-Local）状态，`IbFunction.call()` 通过 `registry.get_current_context()` 获取。

**风险评估**：
- ⚠️ **高风险**：未来如果需要支持并发解释器或协程式执行，线程本地存储会产生严重复杂度
- ⚠️ 需要专门讨论"解释器并发模型"后才能做此决策
- ✅ 当前 `IbFunction` 的运行是正确的，`context` 外部传入只是架构不优雅，不是功能 Bug

**结论**：暂不实现，记录此处供未来参考。在推进 Step 5 之前，必须先明确解释器的并发模型设计。

---

### 6.2 Intent 公理化

**当前状态**：Intent 是通过 `Bootstrapper.initialize()` 注册的内置 `ClassSpec`（与 `IbModule`、`IntentStack` 同级）。它**不是** `DynamicAxiom("intent")` 占位符——内核的 `AxiomRegistry` 中不存在 intent 专属的 Axiom。

**目前的正确描述**：
- `Intent` 类通过 `factory.create_class("Intent")` 注册为 ClassSpec
- `IbIntent` 是运行时对象，直接由 RuntimeContext 和 factory 管理
- `IntentStack` 是独立的内置类型，已有完整的 `push`/`pop`/`remove`/`clear` 原生方法注册

**完整公理化目标（Step 6 长期）**：
- 为 Intent 定义专用 `IntentAxiom`（`is_class()=True`，完整的 vtable）
- 将 Intent 的行为约束纳入公理体系，消除目前依赖运行时直接管理的隐式行为
- 工作量预估 3-5 人天，不阻塞当前功能

---

### 6.3 `callable` 内部占位符清理 ✅ COMPLETED

`DynamicAxiom("callable")` 已被 `CallableAxiom` 彻底替代。
`CallableAxiom` 的 `is_dynamic()=False`，`is_compatible()` 仅声明自身兼容性（不反向列出子类型）。
`BoundMethodAxiom.get_parent_axiom_name()` 仍返回 `"callable"`，且 `is_compatible("callable")` 已正确返回 True。

同时修复：`is_compatible()` 方向 Bug 已在本轮彻底修复——
所有父类型不再错误地向下兼容子类型，子类型通过自身 `is_compatible()` 声明向上兼容链。

---

### 6.4 `BehaviorSpec(return_type_name=...)` 编译期返回类型推断 ✅ COMPLETED（本 PR）

**问题描述（已解决）**：`BehaviorCallCapability.resolve_return_type_name()` 返回 `"auto"`（编译期延迟，运行期按 `expected_type` 解析），导致 `int result = compute()` 在调用处产生 SEM_003 类型不匹配错误。这不是运行时 Bug，而是编译期类型推断精度不足。

**已完成的实现**：

1. `BehaviorSpec(DeferredSpec)` 子类（`core/kernel/spec/specs.py`）：
   - `get_base_name()` 返回 `"behavior"`，axiom 查找路径不变
   - 携带 `value_type_name`（如 `"int"`、`"str"`）和 `deferred_mode`

2. `SpecFactory.create_behavior(value_type_name, deferred_mode)` 工厂方法（`core/kernel/spec/registry.py`）

3. `SpecRegistry.resolve_return()` 对 `DeferredSpec`/`BehaviorSpec` 的专用分支：
   - `value_type_name` 非 `"auto"`/`"any"` 时，直接返回声明的值类型
   - 编译期 `int result = f()` 正确推断 `f` 的返回类型为 `int`，不产生 SEM_003

4. `semantic_analyzer.py`：`deferred_mode` + 具体声明类型时，通过工厂创建带类型的 `BehaviorSpec`/`DeferredSpec`

5. `serializer.py`：持久化 `value_type_name` + `deferred_mode` 字段

6. `artifact_rehydrator.py`：重建正确的 `BehaviorSpec`/`DeferredSpec` Python 子类实例（修复运行时 `is_assignable()` 失败 → RUN_002 错误）

**质量门控**：497 个测试全部通过（含 13 个新增 `TestBehaviorSpecReturnTypeInference` 测试）。

运行时路径保持不变：`invoke_behavior()` → `push_expected_type(behavior.expected_type)` → LLM 结果被约束为 `expected_type` 对应类型。类型信息既有编译期精确推断，也有运行时强制约束，两层双重保障。

---

### 6.5 `llm_tasks.py` 异步任务系统（草稿状态，暂缓）

`core/runtime/async/llm_tasks.py` 目前是未完成的内部草稿。当前实现存在 `execution_context=None` 传入的必然 NPE 问题，且整个异步执行模型尚未在解释器层面设计完成。在并发执行模型讨论完成（Step 5 的先决条件）之前，此文件不应修改，也不应在任何用户接口中暴露。

---

## 七、一句话总结

> **LLM 执行链全面公理化 + 编译期类型推断完善 + OOP×Protocol 边界完整清理。Step 1-4a 均已落地，BehaviorSpec 编译期返回类型推断完成，OOP×Protocol 边界清理（PR-A）完成：`IIbObject.descriptor` 幽灵字段删除，`IbBehavior`/`IbIntent`/`AIPlugin` 多余 Protocol 继承全部去除，所有 Protocol isinstance 替换为具体类检查，`_get_llmoutput_hint` 死代码路径修复为正确 `meta_reg.resolve()` 实现，死 import 全部清理。497 个测试全部通过。下一里程碑是 Step 4b（ibci_ihost/idbg 重构），属中期目标。**

---

## 八、OOP × Protocol 边界清理（PR-A）✅ COMPLETED

### 8.1 根本问题诊断

**Python 3.12 `@runtime_checkable` Protocol 的行为**：在 Python 3.12+ 中，`isinstance(obj, SomeProtocol)` 会同时检查所有 `__protocol_attrs__`，包括数据属性（`@property`）和方法。因此：

- 如果 Protocol 声明了一个数据属性（如 `descriptor`），而实现类没有该属性，`isinstance` 检查将失败。
- 这迫使开发者为了让 `isinstance` 通过，而将 Protocol 加入实现类的显式继承列表——这是一种补丁式的架构穿透。

**根因**：`IIbObject` Protocol 中声明了 `@property def descriptor -> Any`，但 `IbObject.__slots__ = ('ib_class', 'fields')` 从未实现该属性。`descriptor` 是一个遗留的幽灵字段（从未有任何实现，也从无实际读取返回有效值）。

**连锁补丁链条**：

| 问题 | 当前补丁 | 应有的正确状态 |
|------|---------|-------------|
| `IIbObject.descriptor` 幽灵字段 | 存在于 Protocol 声明中 | 彻底删除 |
| `IbBehavior(IbObject, IIibBehavior)` | 显式 Protocol 继承 | `IbBehavior(IbObject)` 单继承 |
| `IbIntent(IbObject, IntentProtocol)` | 装饰性继承（无运行时效果） | `IbIntent(IbObject)` 单继承 |
| `AIPlugin(ILLMProvider, IbStatefulPlugin)` | 遗留历史绑定机制 | `AIPlugin(IbStatefulPlugin)` 单继承 |
| `isinstance(res, IIibBehavior)` × 3处 | Protocol isinstance | `isinstance(res, IbBehavior)` |
| `isinstance(pkg, IIibObject)` × 1处 | Protocol isinstance | `isinstance(pkg, IbObject)` |
| `isinstance(i, IIibIntent)` × 1处 | Protocol isinstance | `isinstance(i, IbIntent)` |
| `getattr(ib_class, 'descriptor', None)` | 永远返回 None 的死代码 | 修复为正确的 `meta_reg.resolve()` 实现 |
| `isinstance(context.llm_executor, ILLMExecutor)` | 旧兼容性保护性检查 | 直接赋值（无条件） |

### 8.2 完整变更清单（PR-A）

#### 根因清除

1. ✅ **`core/runtime/interfaces.py`**：删除 `IIbObject` 中的 `@property def descriptor -> Any`

#### 实现类继承清理

2. ✅ **`core/runtime/objects/builtins.py`**：`IbBehavior(IbObject, IIibBehavior)` → `IbBehavior(IbObject)`，删除 `IIibBehavior` import
3. ✅ **`core/runtime/objects/intent.py`**：`IbIntent(IbObject, IntentProtocol)` → `IbIntent(IbObject)`，删除 `IntentProtocol` import
4. ✅ **`ibci_modules/ibci_ai/core.py`**：`AIPlugin(ILLMProvider, IbStatefulPlugin)` → `AIPlugin(IbStatefulPlugin)`，删除 `ILLMProvider` import

#### isinstance 调用点替换

5. ✅ **`core/runtime/interpreter/handlers/stmt_handler.py`**：`isinstance(res, IIibBehavior)` → `isinstance(res, IbBehavior)`
6. ✅ **`core/runtime/interpreter/interpreter.py`**：`isinstance(obj, IIibBehavior)` → `isinstance(obj, IbBehavior)`；`isinstance(i, IIibIntent)` → `isinstance(i, IbIntent)`
7. ✅ **`core/runtime/host/service.py`**：`isinstance(pkg, IIibObject)` → `isinstance(pkg, IbObject)`
8. ✅ **`core/runtime/interpreter/llm_executor.py`**：`isinstance(behavior, IIibBehavior)` → `isinstance(behavior, IbBehavior)`

#### 死代码与兼容性残留清理

9. ✅ **`core/runtime/interpreter/llm_executor.py`**：修复 `_get_llmoutput_hint` 第二路径——将永远返回 None 的 `getattr(ib_class, 'descriptor', None)` 死代码，替换为与第一路径一致的 `meta_reg.resolve(type_name)` 正确实现
10. ✅ **`core/runtime/module_system/loader.py`**：删除 `isinstance(context.llm_executor, ILLMExecutor)` 保护性检查，改为直接赋值

#### import 悬挂清理

11. ✅ 全部悬挂死 import 清理：
    - `expr_handler.py`：删除 `IIibBehavior`
    - `base_handler.py`：删除 `IIibBehavior`
    - `runtime_context.py`：删除 `IIibIntent`
    - `ibci_idbg/core.py`：删除 `IIibObject` TYPE_CHECKING 块

**质量门控**：497 个测试全部通过。`IbObject` 现在完整结构满足 `IIibObject`（无需显式继承），`IbIntent` 完整结构满足 `IIibIntent`，所有 Python 3.12 runtime_checkable 断言均正确。

### 8.3 设计原则说明

- **`IIbBehavior`、`IIibObject`、`IIibIntent` 等 Protocol 声明继续保留**：它们作为编译期类型文档声明，供静态分析工具（mypy）使用。其 `isinstance` 调用点全部替换为具体实现类，消除对 Python 3.12 runtime_checkable 行为的隐式依赖。
- **`IbBehavior`、`IbObject`、`IbIntent` 作为具体类型守卫**：这些是实现类，`isinstance` 检查具体类既准确又高效，不依赖 Protocol 结构匹配。
- **单一继承原则**：所有 IbObject 子类应只继承 `IbObject`（或其子类），不应同时继承 Protocol 类。Protocol 声明的满足通过结构匹配（mypy 检查）实现，而非显式继承。

### 8.4 后续工作（PR-B，可选）

PR-B 将处理 Impl 类的声明性 Protocol 继承（`ExecutionContextImpl(IExecutionContext, IStackInspector)`、`RuntimeContextImpl(RuntimeContext, IStateReader, IStateProvider)` 等），这些是约定性文档声明，无 Bug 风险，工程量小，可在 PR-A 完成后作为独立整洁化工作进行。
