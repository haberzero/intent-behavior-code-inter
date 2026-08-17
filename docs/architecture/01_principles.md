# IBC-Inter 架构原则与设计理念

> 本文档是 IBC-Inter 项目的核心架构参考文档，包含设计理念、层级架构、设计原则等关键内容。
> 供未来参与 IBC-Inter 项目的开发者进行架构对齐使用。

---

## 一、设计理念与愿景

### 1.1 核心定位

IBC-Inter (Intent Behavior Code - Interactive) 是一种**混合编程语言**，旨在连接：
- **确定性程序逻辑**（Code）
- **非确定性自然语言推理模型**（LLM）

### 1.2 设计目标

| 目标 | 说明 |
|------|------|
| **高效** | 直接从编程语言层级切入 |
| **可控** | 提供充分可靠的调试工具和监控工具 |
| **可复用** | 不依赖于具体大模型 |
| **易用** | 让普通人也能无痛构建属于自己的最简 Agent |
| **普惠** | 小尺寸开源模型也能参与严肃工作 |

### 1.3 核心理念

| 概念 | 作用 |
|------|------|
| **Code** | 确定性的骨架。负责数据结构定义、状态维护、文件交互、流程控制 |
| **Behavior** | 交互的桥梁。由 LLM 在运行时动态推理执行，并无缝接入代码逻辑 |
| **Intent** | 非确定性的上下文。作为环境的"背景信息栈"动态注入至提示词 |
| **Interactive** | 解释运行。LLM 调用开销使解释器专注于高级交互功能而非运行效率 |

### 1.4 IBC-Inter 建议的 LLM 边界

| LLM 擅长 | LLM 不擅长（应由代码完成） |
|----------|---------------------------|
| 常规自然语言处理 | 精确计算 |
| - | 长期流程控制和动态规划 |
| - | 从冗长上下文中提取 tools/skills |

---

## 二、层级架构定义

### 2.1 层级概览

```
base/ (最底层 - 原子概念，可迁移到任何语言)
    │
    ├── source/source_atomic.py  → Location, Severity
    ├── diagnostics/codes.py     → 错误码常量
    │
    ▼ 依赖
kernel/ (核心层 - IBC-Inter核心语言概念)
    │
    ├── axioms/                 → 公理系统（类型行为规范）
    ├── spec/                   → 统一类型描述系统（IbSpec / SpecRegistry）
    ├── symbols.py              → 符号系统（Symbol.spec 唯一字段）
    └── issue.py               → Diagnostic, 各种Error类
    │
    ▼ 依赖
compiler/ (只上不下，输出不可变JSON)
    │
    ├── diagnostics/            → IssueTracker
    └── serialization/          → FlatSerializer输出扁平JSON
    │
    ▼ 输出
runtime/ (只下不上，通过artifact_rehydrator还原)
    │
    └── extension/ (SDK层 - 只出不进)
```

### 2.2 各层职责

| 层级 | 职责 | 关键文件 |
|------|------|----------|
| **base** | 原子概念：位置信息、严重级别、调试基础设施、LLM 供应商无关契约 | source_atomic.py, llm_protocol/ |
| **kernel** | 核心语言概念：AST、符号、统一类型描述系统、公理、异常 | symbols.py, spec/, axioms/ |
| **compiler** | 编译：词法分析、语法分析、语义分析、序列化 | lexer/, parser/, semantic/, serialization/ |
| **runtime** | 解释执行：解释器、宿主服务、插件执行 | interpreter/, host/, objects/ |
| **extension** | 插件SDK：接口定义、能力注入 | ibcext.py, capabilities.py |

---

## 三、核心设计原则

### 3.1 编译器-解释器严格分离

| 原则 | 说明 |
|------|------|
| 编译器输出不可变JSON | 包含完整UID/类型/依赖关系 |
| 解释器只能读取JSON | 通过hydrator还原运行时 |
| 解释器禁止修改原始JSON | 只允许独立运行时管理 |
| 不可变JSON是DynamicHost断点基础 | 保存/恢复/回溯断点的前提 |

### 3.2 公理化基底独立于Python

- `kernel/axioms/` 定义 IBC-Inter 类型行为规范
- `base/source_atomics.py` 定义位置/严重级别等原子概念
- 公理化基底与 Python 宿主解耦：同一规范可迁移到 C++ 或任何其他语言

### 3.3 插件系统三大职责边界

| 插件 | 职责 | 设计理念 |
|------|------|----------|
| **AI** | LLM调用接口 | 提供真正的LLM调用能力 |
| **IDBG** | 运行时信息输出 | 意图栈查看/内存分析/栈监控/运行时状态检查，**不影响主逻辑** |
| **HOST** | 环境保存/恢复/跳转 | 断点保存/恢复/回溯，**不是GDB式断点** |

### 3.4 DynamicHost 架构定位

DynamicHost 是**插件接口层**，不是解释器管理层。

| 组件 | 职责 | 说明 |
|------|------|------|
| **DynamicHost** | 接口层 | 暴露 `run_isolated`/`spawn_isolated`/`collect`/`save_state`/`load_state` 给 IBCI 脚本，不持有解释器实例，纯委托 |
| **HostService** | 服务实现层 | 协调子解释器创建，委托 Engine 执行 |
| **Engine** | 解释器管理层 | 唯一持有 Interpreter 实例，负责 spawn_interpreter() |
| **Interpreter** | 执行层 | 单个解释器的执行上下文 |

**调用链**：
```
IBCI脚本 → DynamicHost → HostService → Engine.spawn_interpreter() → Interpreter
```

**重要**：子解释器和主解释器**地位平等**，都是 Interpreter 实例，区别仅在于创建方式。

### 3.5 DynamicHost "断点" ≠ GDB断点

| 概念 | DynamicHost "断点" | GDB 断点 |
|------|-------------------|----------|
| **目的** | 现场保存/恢复/回溯 | 单步调试/内存观察 |
| **触发方式** | 主动保存或环境退出 | 运行到指定位置 |
| **恢复能力** | 可恢复到之前保存的状态 | 仅能从当前位置继续 |

### 3.6 DynamicHost 最小目标

1. **能够启动全隔离的运行环境**
2. **能够继承所有来自主解释器的插件/类型公理体系**
3. **不做额外的权限控制管理**
4. **运行之后不会干扰主解释器的任何内容**
5. **可以让主解释器正确返回到跳出点的位置**

**信息交互方式**：通过显式的 file 读写进行，不做隐式内存交互。

---

### 3.7 LLM 调用层插件化（供应商无关中间层）

IBC-Inter 把 LLM 当作一个可调用的"表达式/函数"来对待：内核只关心**调用 LLM
这个抽象动作**，不关心任何具体供应商（OpenAI / Anthropic / Ollama / LM Studio /
本地自定义格式）的请求格式、配置书写方式或思考模式字段。

为实现这一边界，内核与外部 LLM 调用服务（AI 插件）之间有一个**供应商无关的
中间层** `core/base/llm_protocol/`（base 层，只出不进）：

| 契约 | 内容 | 方向 |
|------|------|------|
| `LLMCallRequest` | 一次完整 LLM 调用的结构化请求：意图栈（active/global/merged 原始三层）、输出契约（期望类型 / `__outputhint_prompt__` 产物）、提示词语义槽、user 内容、目标模型、重试历史 | 内核 → provider |
| `LLMCallResult` | 供应商无关的响应：`content` / 结构化 `reasoning` / `thinking_detected` / `provider_meta`（含实际发送的 `sys_prompt`） | provider → 内核 |
| `LLMProvider` | 抽象调用协议：`call(request)` / `stream(request)` / `get_retry` / `probe` | 内核调 provider |
| `ModelSpec` / `LLMConnectionConfig` / `ConfigSourceAdapter` | 供应商无关逻辑配置 + 可插拔配置源适配器（api_config.json 书写格式） | 配置层 |
| `recommended` 模块 | **推荐**系统提示词组装模板（把语义槽拼为提示词） | provider 可选用/覆盖 |

**设计立场**：

- 内核不拼装系统提示词、不触碰供应商 SDK/字段、不规定 api_config.json 的书写
  格式——只产出结构化 `LLMCallRequest` 委托给 provider。
- provider（AI 插件）负责：把 `LLMCallRequest` 组装成所属供应商 payload、把
  供应商响应解析为 `LLMCallResult`、思考模式/探测的供应商字段映射。
- 系统提供"推荐 provider"（OpenAI/LM Studio + Qwen 思考抑制适配）与"推荐
  api_config.json 适配器"；用户可自写 `LLMProvider` / `ConfigSourceAdapter`
  实现自定义请求格式、提示词组装与配置书写方式（**推荐格式可被覆盖，非定死**）。
- 内省/调试（`get_current_call_info` / idbg）暴露 `LLMCallRequest.as_dict()` 全量
  + provider 回填的实际 `sys_prompt` / `response`。

**自定义已统一（F4）**：LLM 调用经 `llm_provider` 能力接入——内核 LLM 执行器每次
调用从能力注册表读当前激活 provider，再调 `call()`/`stream()`。内置默认 provider 为
`ibci_modules/ibci_ai/provider_impl.py` 的 `RecommendedProvider`（无自定义时生效）。

- **用户自定义 LLM 底层**（正式通道，F4）：写实现 `LLMProvider` 契约的 Python 类，
  经宿主绑定 `import python "my_provider" as lib: bind provider` 声明，并
  `ai.set_provider(lib.provider)` 注册为激活 provider（HIGH 优先级覆盖默认）。
  无需修改任何内核/内置文件。操作指南见 `docs/howto/modify_llm_provider.md`。
- **`provider_impl.py` 不手动改**：它仅是内置默认实现；用户面自定义走宿主绑定 +
  `set_provider`（能力表优先级单选 primary，不并存双通道）。
- 配置源适配器 `config_source_adapter.py` 仍可整文件替换（用户自写 `ConfigSourceAdapter`）。
- `core.py` 宿主（IBCI 胶水）保持内置不变。

---

### 4.1 核心依赖原则

**核心原则**：kernel → base（单向依赖），compiler → kernel，runtime → kernel

| 依赖方向 | 是否允许 | 说明 |
|----------|----------|------|
| kernel → base | 允许 | kernel 可使用 base 的原子概念 |
| compiler → kernel | 允许 | 编译器依赖核心语言概念 |
| runtime → kernel | 允许 | 运行时依赖核心语言概念 |
| kernel → runtime | 禁止 | 架构穿透严格禁止 |
| runtime → compiler | 禁止 | 运行时不应依赖编译器 |

### 4.2 架构穿透严格禁止

- kernel 层禁止依赖 runtime 层具体实现
- IExecutionContext 应按职责拆分：
  - **纯数据部分**：可序列化，可存在于任何层
  - **访问接口部分**：定义为 kernel 层的抽象接口

---

## 五、公理体系设计

### 5.1 公理系统架构

公理体系直接与 `core/kernel/spec/` 统一类型描述系统集成（详见 5.4 节）。

| 组件 | 职责 | 文件位置 |
|------|------|----------|
| **TypeAxiom** | 核心公理接口（capability 协议） | `axioms/protocols.py` |
| **BaseAxiom** | 公理基类，提供默认实现 | `axioms/primitives/`（包） |
| **IntAxiom/StrAxiom...** | 具体类型公理 | `axioms/primitives/`（包） |
| **AxiomRegistry** | 公理注册表，按类型名索引公理实例 | `axioms/registry.py` |

### 5.2 公理与类型系统集成

- IbSpec（`core/kernel/spec/`）是唯一的类型描述符系统
- 公理通过 `AxiomRegistry` 查询，各类型能力通过公理的 `has_*_cap` 类属性声明，统一由 `TypeAxiom` 接口实现
- 所有类型引用在公理层能力方法均以**纯字符串类型名**传递，消除公理层对 spec 层查询/解析逻辑的依赖（axiom 可 import spec 的原子数据结构构造器 `TypeRef`/`MethodMemberSpec`，不得依赖注册表解析）
- `SpecRegistry` 负责将公理返回的类型名字符串解析为对应的 `IbSpec` 对象

### 5.3 Fallback 策略原则（重要）

IBC-Inter 公理体系中的 fallback 分为两类，必须严格区分：

#### 允许的 Fallback：职责分离型

**设计原则**：公理层声明"行为规范"，spec 层持有"具体类型信息"

| 场景 | 说明 |
|------|------|
| **IbSpec 基类能力访问器** | 返回 None 表示"未知"，子类有义务重写 |
| **TypeDef 返回类型解析** | 公理优先，静态 TypeRef 签名作为编译期后备（双轨制） |
| **跨模块占位符** | 编译器 `scheduler` 预注册空 `ModuleMetadata`（`create_module`）占位，解析后替换为真实 spec |

#### 禁止的 Fallback：妥协性历史兼容

**设计原则**：公理为唯一真源，任何妥协性 fallback 都是技术债务

| 问题 | 说明 |
|------|------|
| **TypeCheckingPass 中残留的 `or self._any_desc`**（`_expression_visitors.py`、`_statement_visitors.py`、`_type_checking_base.py`） | 静默掩盖类型推断缺口。用户类型名解析经 TypeRefResolutionPass + SEM_UNRESOLVED_TYPE / ICE_TYPE_LEAK 校验；内建名防御和推断规则缺失仍保留为允许的职责分离型回退。未标注可调用（func/llm/lambda）报 `SEM_MISSING_RETURN_ANNOTATION` 编译错误；裸赋值采用 `auto` 推断锁定（不隐式 any）；多类型 `list[int,str]` 不支持（强制 `list[any]`）。`any` 仅保留为显式逃生阀，其值用于类型化上下文时运行时强制校验。 |
| **跨模块占位符异常情况** | 占位符号解析失败时应抛出错误（类型未注册）而非静默保留占位 |

**关于跨模块占位符的说明**：

跨模块未解析符号在编译期以 `scheduler` 预注册的空 `ModuleMetadata`（`create_module`）占位，解决编译期循环依赖：
- **正常情况**：解析成功后替换为真实 spec
- **异常情况**：`resolve()` 失败时理想应抛出错误（类型未注册），而非静默占位

**违反后果**：妥协性 fallback 会导致类型信息丢失、错误掩盖、难以调试等问题，必须在后续迭代中修复。

---

### 5.4 统一类型描述系统（core/kernel/spec/）

类型描述系统位于 `core/kernel/spec/`。

| 组件 | 职责 | 文件位置 |
|------|------|----------|
| **IbSpec** | 所有类型描述符的基类 | `kernel/spec/base.py` |
| **TypeDef** | 统一类型描述与 kind 分派入口 | `kernel/spec/specs.py`, `kernel/spec/base.py` |
| **SpecRegistry** | 类型注册、兼容性检查、Capability 查询 | `kernel/spec/registry/`（包） |
| **SpecFactory** | 内置类型工厂（create_list/create_tuple/create_dict 等） | `kernel/spec/registry/`（包） |
| **MemberSpec / MethodMemberSpec** | 模块成员描述符 | `kernel/spec/member.py` |

`Symbol` 只保留 `.spec` 字段（`IbSpec` 类型），不存在 `.descriptor` 属性或任何兼容 shim。

---

## 六、Intent/Behavior 系统

### 6.1 Intent（意图）系统

- Intent 是非确定性的上下文
- 作为环境的"背景信息栈"动态注入至提示词
- 支持 @/@+/@-/@! 修饰符

### 6.2 Behavior（行为）系统

- Behavior 通过 `@~ ... ~` 语法触发 LLM 调用
- Callable 类型支持延迟执行的 Behavior（闭包封装）

### 6.3 意图栈继承策略

- 意图栈的"继承"由 `IbIntentContext.fork()` 承担：每次函数调用创建子 context，从父 context 继承意图栈快照，后续修改互不影响（公理 IC-1，见 `05_vm_specification.md` §5.1）。
- 跨隔离边界（spawn）不继承意图：隔离子环境拥有独立 `RuntimeContextImpl`（公理 ISO-1），`IsolationPolicy` 不设意图继承字段（实际字段为 `inherit_plugins` / `collect_timeout`，见 `core/runtime/host/isolation_policy.py`）。

---

## 七、模块系统与宿主绑定

### 7.1 构造期注册（无插件搜索路径）

全部内置模块（内核原生 5 + 工具 5 + `file`）的 TypeDef 字面量集中于
`core/runtime/bootstrap/builtin_modules.py`，Engine 构造期经
`register_builtin_modules(host_interface)` 一次注册。不存在磁盘发现/嗅探通道：
无 `_spec.py` 契约文件、无 `plugin_paths`/`global_plugin` 配置、无
AutoDiscovery。用户侧扩展唯一通道是宿主绑定
（`import python "..." as lib: bind ...`，见
`docs/architecture/01_native_host_binding.md`）。

### 7.2 内置模块接口规范

| 位置 | 职责 | 说明 |
|------|------|------|
| `builtin_modules.py` | 元数据 | 模块的 TypeDef 字面量（成员签名、`param_descriptors`、provenance/visibility） |
| `ibci_modules/<pkg>/core.py` | 具体逻辑实现 | 模块的 Python 实现类 |
| `ibci_modules/<pkg>/__init__.py` | 工厂模式入口 | 只负责导入和 `create_implementation()` 工厂函数 |

**两级模块架构**：

| 级别 | 说明 | 包含模块 |
|------|------|---------------|
| 内核原生（kernel-native）| 随内核发行，构造期注册，`KERNEL_NATIVE` + IMPORT_GATED；物理位于 `ibci_modules/`（`file` 为内核模块 `core/runtime/modules/file_impl.py`），受 HostInterface 覆盖保护 | `ai` / `file` / `ihost` / `idbg` / `isys` / `iruntime` |
| 内置工具 | 不继承 `IbPlugin`，通过 `setup(capabilities)` 接收浅层能力注入，实现类不导入 `core.*`；`USER_DEFINED` provenance | `math` / `json` / `time` / `net` / `schema`（实现包 `ibci_math` / `ibci_json` / `ibci_time` / `ibci_net` / `ibci_schema`） |
| 核心级 | 继承 `IbPlugin`，可访问 `ExtensionCapabilities`；有状态模块实现 `IbStatefulPlugin` | `ibci_ai` / `ibci_ihost` / `ibci_idbg` |

**示例（AI 模块）**：
- `ibci_modules/ibci_ai/__init__.py` → `from .core import AIPlugin; def create_implementation(): return AIPlugin()`
- `ibci_modules/ibci_ai/provider_impl.py` → `class RecommendedProvider(LLMProvider): ...`（纯 provider，kernel-free，可整文件替换）
- `ibci_modules/ibci_ai/core.py` → `class AIPlugin(RecommendedProvider, IbStatefulPlugin): ...`（IBCI 胶水宿主）
- `core/runtime/bootstrap/builtin_modules.py` `_SPEC_AI` → 成员签名与 `param_descriptors` 字面量

### 7.3 编译构建流程（静态类型检查保留）

**当前架构流程**：
```
Engine.__init__()
    ↓
register_builtin_modules() → HostInterface.metadata
    ↓
compiler/scheduler 使用 HostInterface.metadata 做静态类型检查
```

**关键保证**：
| 保证 | 说明 |
|------|------|
| **静态类型检查保留** | 编译器通过 `core/kernel/spec/` 中的 `TypeDef` / `TypeRef` 体系获取完整类型信息 |
| **扁平流生成保留** | FlatSerializer 依赖 `IbSpec.get_references()` / `TypeDef` 统一字段 |

---

## 八、信息交互原则

IBCI 采用显式的文件读写作为子环境与主环境之间的信息交互方式，子环境的 LLM 输出也直接通过硬盘保存。相比于隐式内存交互，这种方式使开发者可以绝对控制可被交互的信息，降低系统复杂度和维护成本。

**核心原则**：信息交互应通过显式的 file 读写进行，不做隐式内存交互。

---

## 九、自动注册机制

IBCI 在绝大多数情况下严格禁止硬编码。所有内置函数、内置关键字、语法糖以及内置模块均通过自动注册机制完成，且享有同等地位。

| 机制 | 位置 | 说明 |
|------|------|------|
| **内置模块构造期注册** | `runtime/bootstrap/builtin_modules.py` | 内置 11 模块 TypeDef 字面量集中定义，Engine 构造期一次注册 |
| **两阶段注册** | `kernel/spec/registry/`（包） | 占位阶段 + 填充阶段 + 公理注入 |

---

## 十、命名前缀规范

| 层级 | 建议前缀 | 示例 |
|------|----------|------|
| base | 直接用描述性名称 | `source_atomics.py`, `debugger.py` |
| kernel | 无需前缀（kernel已经是限定词） | `axiom_hydrator.py`, `issue.py` |
| runtime | `rt_` 或 `runtime_` | `rt_artifact_rehydrator.py` |
| compiler | 无需前缀（compiler已经是限定词） | `issue_tracker.py`, `formatter.py` |
| extension | `ext_` 或 `extension_` | `extension_ibcext.py` |

---

## 十一、已明确的排除项

| 排除项 | 理由 |
|--------|------|
| 进程级隔离 | 实例级隔离已足够 |
| 核心级 IPC | 通过外部 file 插件实现 |
| GDB 式断点 | DynamicHost 断点是现场保存/恢复/回溯 |
| hot_reload_pools | 违反解释器不修改代码原则 |
| generate_and_run | 动态生成IBCI应由显式的IBCI生成器进行 |

---

## 附录：关键文件索引

> 以下模块为包结构（目录），路径以 `/` 结尾标注：
> `kernel/spec/registry/`、`kernel/axioms/primitives/`、`runtime/objects/{primitives,kernel}/`、
> `runtime/vm/handlers/`、`runtime/interpreter/llm_executor/`。

| 文件 | 重要性 | 说明 |
|------|--------|------|
| `core/engine.py` | 高 | IBCIEngine，解释器管理层，spawn_interpreter() |
| `core/kernel/registry.py` | 高 | KernelRegistry，运行时对象工厂 |
| `core/kernel/spec/registry/`（包） | 高 | SpecRegistry + SpecFactory，统一类型描述系统 |
| `core/kernel/spec/specs.py` | 高 | 具体 IbSpec 子类及内置类型原型常量 |
| `core/kernel/axioms/primitives/`（包） | 高 | 内置类型公理实现（register_core_axioms） |
| `core/kernel/symbols.py` | 中 | Symbol 系统（Symbol.spec 唯一类型字段） |
| `core/runtime/interpreter/execution_context.py` | 高 | ExecutionContextImpl |
| `core/runtime/interpreter/llm_executor/`（包） | 高 | LLMExecutorImpl，LLM 调用与结果解析 |
| `core/runtime/interpreter/llm_except_frame.py` | 高 | LLMExceptFrame，llmexcept 现场帧 |
| `core/runtime/vm/handlers/`（包） | 高 | CPS 语句/表达式节点处理（含各语句 handler 的 llmexcept 内联重试） |
| `core/runtime/host/service.py` | 高 | HostService，断点快照/恢复 |
| `core/kernel/host_interface.py` | 高 | HostInterface，宿主环境接口注册器 |
| `core/runtime/bootstrap/primitive_initializer.py` | 高 | 内置类型注册与装箱器 |
| `core/compiler/serialization/serializer.py` | 高 | FlatSerializer |
| `core/compiler/scheduler.py` | 高 | 编译调度器，import 注入 |
| `core/runtime/bootstrap/builtin_modules.py` | 高 | 内置 11 模块 TypeDef 字面量与构造期注册（register_builtin_modules） |
| `core/extension/ibcext.py` | 高 | IbPlugin / IbStatefulPlugin |
| `ibci_modules/ibci_ai/core.py` | 高 | AI 插件（IBCI 胶水宿主） |
| `ibci_modules/ibci_ai/provider_impl.py` | 高 | 推荐 LLM provider（纯 provider，kernel-free） |
| `ibci_modules/ibci_ihost/core.py` | 中 | HOST 插件实现（核心级） |
| `ibci_modules/ibci_idbg/core.py` | 中 | IDBG 调试插件实现 |
| `core/runtime/observability/`（包） | 中 | 观测体系（snapshot / events / diagnostics / config），详见 `09_observability.md` |

---

## 附录：HOST 模块双路暴露

`HostService`（核心层）和 `ibci_ihost`（内置模块）对同一宿主能力有双路暴露：

```
IBCI脚本 ──→ host_run() 内置函数 ──→ HostService
                (primitive_initializer) (实际执行)

IBCI脚本 ──→ import ihost ──→ ibci_ihost/core.py ──→ HostService
               (构造期注册)   (模块实现)
```
---

## 深入指引

- 类型系统设计：docs/architecture/03_type_system.md
- 运行时架构：docs/architecture/04_vm_interpreter.md
- 子系统设计：docs/SUBSYSTEM_DESIGN.md
