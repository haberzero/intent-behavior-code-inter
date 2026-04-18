# 公理体系 / 万物皆对象 — 架构分析与迭代路线

> 本文件记录 IBC-Inter 公理化/面向对象重构的架构分析结论与设计决策，供未来 PR 迭代使用。
>
> **最后更新**：2026-04-18（Steps 1-3 完整落地；callable + deferred + behavior 公理化全面完成）
>
> 已完成工作见 `docs/COMPLETED.md`，未来步骤（Step 4-6）见第四章，远期高风险任务见第五章。

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
| IbFunction / IbLLMFunction | ✅ | 部分（FuncSpec） | ✅ | ⚠️ 依赖外部 context |

### 尚未完整公理化的类型

| 类型 | 问题描述 |
|------|---------|
| **IbFunction** | `call()` 需要外部传入 `context`（`IExecutionContext`），不能自主执行。 |
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

**当前已知限制（P2 目标）**：
- 编译器中 `is_assignable(auto, int)` = False，导致 `int result = compute()` 在调用处产生 SEM_003 类型不匹配错误。这不是运行时 Bug，而是编译期类型推断精度不足。
- **正确方向**：引入 `BehaviorSpec(return_type_name="int")` 使编译器在已知 lambda/snapshot 定义的 expected_type 时，调用处可推断为具体类型。这属于 Step 2 的延伸，不影响当前核心功能。

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

## 四、迭代路线图

### Steps 1–3 ✅ COMPLETED

| Step | 内容 | 详情 |
|------|------|------|
| Step 1 | `IILLMExecutor` 接口 + `KernelRegistry` 注入 | `core/base/interfaces.py`、`core/kernel/registry.py`、`core/engine.py` |
| Step 2 | `BehaviorAxiom` + `IbBehavior.call()` 自主执行，`_execute_behavior()` 旁路彻底删除 | `core/kernel/axioms/primitives.py`、`core/runtime/objects/builtins.py` |
| Step 3a | `ibci_ai` 职责拆分：`llm_callback` 唯一来源为 `capability_registry.get("llm_provider")` | `core/runtime/interpreter/llm_executor.py`、`ibci_modules/ibci_ai/core.py` |
| Step 3b | `CallableAxiom` + `DeferredAxiom` + `DeferredSpec` + `IbDeferred`，`is_compatible()` 方向 Bug 修复 | `core/kernel/axioms/primitives.py`、`core/kernel/spec/specs.py`、`core/runtime/objects/builtins.py` |
| Step 4a | `IbLLMFunction` 自主执行（`invoke_llm_function`） | `core/runtime/objects/kernel.py`、`core/base/interfaces.py` |

完整实现细节见 `docs/COMPLETED.md` §一 和 `docs/ARCH_DETAILS.md` 第六章。

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

**重构后**：`ibci_ihost` 和 `ibci_idbg` 降级为"标准插件"，不再需要 `IbPlugin` 特权层级，通过与非侵入式插件一致的 setup 机制获取所需接口。IBCI 接口保持不变。

---

### Step 5（长期，全局架构工作）

**`IbFunction.call()` 去除 `context` 参数依赖**

将解释器环境的获取方式改为通过 `ib_class.registry` 拿到 `KernelRegistry`，再由 `KernelRegistry` 提供"当前执行上下文"钩子。

**⚠️ 此步骤的线程本地存储方案属于高风险设计，需要单独讨论解释器并发模型后推进。见第五章。**

---

### Step 6（长期）

**万物皆对象完整化**

- `Intent` 完整公理化（`IntentAxiom` 替换当前 ClassSpec 占位）
- 消除 `ServiceContext` 中所有游离于对象体系之外的"隐式依赖"

---

## 五、远期高风险任务记录

### 5.1 `IbFunction.call()` 线程本地存储方案

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

### 5.2 Intent 公理化

**当前状态**：Intent 通过 `Bootstrapper.initialize()` 注册为内置 `ClassSpec`；`IbIntent` 是运行时对象，直接由 RuntimeContext 和 factory 管理；`IntentStack` 已有完整的原生方法注册（`push`/`pop`/`remove`/`clear`）。`AxiomRegistry` 中**不存在** Intent 专属 Axiom。

**完整公理化目标（Step 6 长期）**：
- 为 Intent 定义专用 `IntentAxiom`（`is_class()=True`，完整的 vtable）
- 将 Intent 的行为约束纳入公理体系，消除依赖运行时直接管理的隐式行为
- 工作量预估 3-5 人天，不阻塞当前功能

---

## 六、一句话总结

> **可调用类型体系（callable → deferred → behavior）已全面公理化。Steps 1-3（IILLMExecutor 接口、BehaviorAxiom 自主执行、ibci_ai 拆分、CallableAxiom/DeferredAxiom/IbDeferred、IbLLMFunction 自主执行）均完整落地，全部测试通过。`is_compatible()` 方向 Bug 已修复。下一个里程碑是 Step 4（ibci_ihost/idbg 标准化重构）和 Step 5/6（IbFunction 去除 context 依赖、Intent 公理化），均属中长期目标。**

