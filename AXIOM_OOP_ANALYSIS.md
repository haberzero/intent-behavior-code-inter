# 公理体系 / 万物皆对象 — 架构分析与迭代路线

> 本文件记录 IBC-Inter 公理化/面向对象重构的架构分析结论与设计决策，供未来 PR 迭代使用。
>
> **最后更新**：2026-04-17（第三次修订：Step 1 + Step 2 已于本轮完整落地）
>
> 当前已完成的修复见第五章，正在进行中的工作见第四章，未来远期高风险任务见第六章。

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
| **behavior** | ✅ | ✅（`BehaviorAxiom`） | ✅ | ✅（`IbBehavior.call()` 自主执行） |
| IbFunction / IbLLMFunction | ✅ | 部分（FuncSpec） | ✅ | ⚠️ 依赖外部 context |

### 尚未完整公理化的类型

| 类型 | 问题描述 |
|------|---------|
| **callable** | 仅作为 `DynamicAxiom("callable")` 存在，是历史遗留的占位符，无真正语义。用户层已废弃（见 `lambda`/`snapshot`）。 |
| **IbFunction** | `call()` 需要外部传入 `context`（`IExecutionContext`），不能自主执行。 |
| **Intent** | `DynamicAxiom("intent")` 占位符，完整公理化依赖 behavior 先行。 |

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

### 3.4 BehaviorCallCapability 的返回类型：使用 expected_type，不允许 "any" 妥协

**已确认**：`behavior` 类型在编译期已有明确的类型检查结果。`IbBehavior.expected_type` 字段保存了 LHS 类型标注（如 `int`、`str`）。

`BehaviorCallCapability.resolve_return_type_name()` **必须从 `IbBehavior.expected_type` 读取**，不允许硬返回 `"any"` 作为妥协：

```python
class BehaviorCallCapability(CallCapability):
    def resolve_return_type_name(self, receiver: IbObject, args: List[IbObject]) -> str:
        # receiver 是 IbBehavior 实例
        if hasattr(receiver, 'expected_type') and receiver.expected_type:
            return receiver.expected_type
        return "str"  # 无 LHS 类型时默认 str，与即时执行行为一致
```

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

### Step 3（独立 PR，中期目标）

**`ibci_ai` 职责拆分**

当前 `ibci_ai` 承担了两个不同职责，必须拆分：

| 当前职责 | 拆分后归属 |
|---------|-----------|
| LLM API 调用（OpenAI/Ollama 等的 HTTP 请求） | 注入到 `KernelRegistry.llm_executor`（Step 1 完成后自然实现） |
| LLM 配置 API（`set_retry`、`set_context`、`set_model`）| 保留在 `ibci_ai` 插件，通过 `import ai` 显式使用 |
| `IbStatefulPlugin` 断点保存/恢复（LLM 配置状态） | 保留在 `ibci_ai` 插件 |

**拆分后**：
- `ibci_ai` 的 IBCI 接口（`ai.set_retry()` 等）继续正常工作
- `@~...~` 的执行不再路由经过 `ibci_ai`，而是通过 `KernelRegistry.get_llm_executor()` 直接执行
- `ibci_ai.setup(capabilities)` 负责将自己注册的 provider 注入到 `KernelRegistry`

---

### Step 4（独立 PR，中期目标）

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

- `IbLLMFunction` 自洽执行（类似 Step 2，依赖 `LLMExecutor` 内核化）
- `Intent` 完整公理化（`IntentAxiom` 替换 `DynamicAxiom("intent")`）
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

### 6.2 Intent 完整公理化

**状态**：`DynamicAxiom("intent")` 占位符，工作量预估 5-9 人天。依赖 `BehaviorAxiom`（Step 2）先行完成。不影响当前核心功能。

---

### 6.3 `callable` 内部占位符清理

当前 `DynamicAxiom("callable")` 仍然存在（内部类型系统使用）。`BoundMethodAxiom.get_parent_axiom_name()` 返回 `"callable"`。

在 Step 2 完成后，需要评估：
- `callable` 内部占位符是否还有实际语义需求
- 若无，则完全从 `AxiomRegistry` 中移除，彻底清理历史遗留

---

## 七、一句话总结

> **万物公理化的最后阻塞点已突破。Step 1（IILLMExecutor 接口 + KernelRegistry 注入）和 Step 2（BehaviorAxiom + IbBehavior.call() 自主执行 + _execute_behavior() 彻底删除）已在同一 PR 中完整落地，446 个测试全部通过，代码中不再存在任何 behavior 类型相关的架构旁路。下一个重要里程碑是 Step 3（ibci_ai 职责拆分）和 Step 4（ibci_ihost/idbg 重构），均属中期目标，不阻塞当前功能。**
