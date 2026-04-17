# 公理体系 / 万物皆对象 — 架构分析与下一步迭代路线

> 本文件记录 2026-04-17 对话中的架构分析结论，供下一次 PR 迭代使用。
> 对应代码修改：PR `copilot/check-ibc-inter-design-docs`（P0/P1/behavior-call-path 三项修复）。

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
| IbFunction / IbLLMFunction | ✅ | 部分（FuncSpec） | ✅ | ⚠️ 依赖外部 context |

### 尚未完整公理化的类型

| 类型 | 问题描述 |
|------|---------|
| **behavior** | `DynamicAxiom("behavior")` 注册，`CallCapability` 为 None，`IbBehavior.call()` 直接抛 `RuntimeError`。调用必须绕道走 handler 层的 `_execute_behavior()`。 |
| **callable** | 仅作为 `DynamicAxiom("callable")` 存在，是历史遗留的占位符，无真正语义。 |
| **IbFunction** | `call()` 需要外部传入 `context`（`IExecutionContext`），不能自主执行。 |

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

## 三、关于核心服务插件化的建议：明确放弃部分设计

### 初衷回顾

允许高级用户通过同名插件覆盖核心插件，包括：
- 自定义 LLM API 提供商 / API 协议
- 自定义解释器行为（元操作）

### 建议：三层切割，"配置化"替代"插件化"

```
┌─────────────────────────────────────────────────────────┐
│  第一层：KernelServices（永远不可替换）                    │
│  - LLMExecutor：调用语义固定，provider 可配置              │
│  - KernelRegistry：类型体系和对象注册表                    │
│  - AxiomRegistry：公理体系                                │
│  → 硬编码进解释器，IbBehavior.call() 可安全持有弱引用       │
├─────────────────────────────────────────────────────────┤
│  第二层：HostServices（可配置，接口固定）                   │
│  - LLM provider 配置（哪个 API/model）                    │
│  - HostService（run_isolated 等）                         │
│  → 用配置文件/参数控制，不走插件体系，接口是稳定合约          │
├─────────────────────────────────────────────────────────┤
│  第三层：ExtensionPlugins（真正的用户插件）                 │
│  - ibci_math / net / json / time / schema 等              │
│  - 高级用户自定义扩展                                      │
│  → 走完整 IbPlugin 体系，无法接触内核状态                   │
└─────────────────────────────────────────────────────────┘
```

**明确放弃的设计**：
- ❌ 允许用户插件替换解释器运行逻辑（元操作）
  - 理由：与公理化方向对立。一旦解释器行为可被任意替换，所有公理定义都退化为"当前插件下的公理"，语言丧失确定性语义。
- ❌ `LLMExecutor` 作为插件（可被同名插件覆盖）
  - 理由：它是语言语义的一部分，不是外部扩展。

**保留的设计**：
- ✅ 允许配置 LLM provider（哪个 API key、哪个 model）—— 这是配置化，不是插件化
- ✅ 允许扩展标准库（math/net/json 等）—— 这是真正的插件化
- ✅ 允许用户定义类、函数、enum —— 这是语言的核心能力

---

## 四、下一次迭代的路线图

### Step 1（阻塞性前置，优先级最高）

**确立 `LLMExecutor` 为第一层内核服务**

1. 在 `KernelRegistry` 增加 `register_llm_executor(executor, token)` / `get_llm_executor()` 接口，要求内核令牌。
2. `ServiceContext` 仍然持有 `llm_executor` 引用，但同时将其注入到 `KernelRegistry`。
3. 调整 `BuiltinInitializer` 在 bootstrap 阶段完成注入。

**预期收益**：`IbBehavior.call()` 可以通过 `self.ib_class.registry.get_llm_executor()` 安全获取执行器，不再需要外部传入。

### Step 2（Step 1 完成后，可在同一 PR 完成）

**给 `behavior` 类型声明真正的 `BehaviorAxiom` + `CallCapability`**

1. 新建 `BehaviorAxiom(BaseAxiom)` 替换 `DynamicAxiom("behavior")`。
2. 声明 `get_call_capability()` 返回 `BehaviorCallCapability`，其 `resolve_return_type_name()` 返回 `"any"`。
3. 实现 `IbBehavior.call(registry, args)` —— 内部调用 `registry.get_llm_executor().execute_behavior_expression(...)`。
4. 删除 `_execute_behavior()` 中的意图栈切换代码，将其移入 `IbBehavior.call()`。
5. `visit_IbCall` 中的 `is_behavior()` 检测也可随之删除——`hasattr(func, 'call')` 分支自然处理。

### Step 3（中期，可独立 PR）

**`IbFunction.call()` 去除 `context` 参数依赖**

将解释器环境的获取方式改为：通过 `ib_class.registry` 拿到 `KernelRegistry`，再由 `KernelRegistry` 提供"当前执行上下文"钩子（类似线程本地存储语义）。这需要更大的重构，单独立项。

### Step 4（长期，全局架构工作）

**万物皆对象完整化**

- `IbLLMFunction` 自洽执行（类似 Step 2，依赖 `LLMExecutor` 内核化）
- `ibci_ihost` / `ibci_idbg` 去除 `IbPlugin` 特权，改为通过 `KernelRegistry` 钩子访问宿主服务
- 消除 `ServiceContext` 中所有游离于对象体系之外的"隐式依赖"

---

## 五、本次 PR 已完成的修复（供记录）

| 修复 | 优先级 | 文件 |
|------|--------|------|
| `_bind_llm_except` 递归进入嵌套控制流块（IbFor/IbIf/IbWhile/IbTry/IbSwitch） | P0 | `core/compiler/semantic/passes/semantic_analyzer.py` |
| `SpecRegistry.is_behavior(spec)` 方法，消除 `"behavior"` 硬编码字符串比较 | P1 | `core/kernel/spec/registry.py` |
| `visit_IbCall` behavior 检测改为通过 `spec_reg.is_behavior()` 路由 | 代价可控关键一步 | `core/runtime/interpreter/handlers/expr_handler.py` |

---

## 六、一句话总结

> **万物公理化的真正障碍不是"公理怎么写"，而是"核心服务层边界不清导致对象无法自洽"。最近的首要任务是将 `LLMExecutor` 确立为第一层内核服务（注入 `KernelRegistry`），一旦完成，`BehaviorAxiom + CallCapability` 可在一个 PR 内完成，`behavior` 类型彻底公理化，`_execute_behavior()` 旁路可删除。**
