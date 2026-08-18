# 临时设计文档：五大地基改造 · P1 设计定稿

> **性质**：临时任务控制文档（设计阶段，`code-workflow` P2 交付物）。P1 是**设计定稿**
> （非代码编写）。落地后按 `tasks_docs/GOVERNANCE.md` 收敛到 `docs/`，本文件删除
> （git 承载历史）。
>
> **承接关系**：本文件是 `tasks_docs/_five_foundation_redesign.md`（唯一调研与决策权威）
> 与 `tasks_docs/_llm_callable_redesign.md`（方法族草案）的 **P1 设计深化与定稿**。
> 承接其 §六「下一 session 交接（P1 设计定稿开工输入）」7 项，逐项定稿。本文件**不**
> 改写已拍板决策正文（以 `_five_foundation_redesign.md` §五 为权威），只做深化落地。

---

## 〇、P1 范围与设计准绳

**P1 = 设计定稿（Phase 0-2），不写实现代码。** 产出可被 P2-P6 直接实现的设计规格。

**设计准绳**（承接 `_llm_callable_redesign.md` §6bis.2）：
- 凡新设计，先问"它是否是一个**可调用实例 + 一个协议**"；
- 凡机制，先问"它的**捕获策略 / 包装策略**能否参数化"。

**用户 2026-08-18 追加裁定（本 session 澄清，最高约束）**：
> `llm ... llmend` 语法**彻底删除**，且**与 llm 函数语法相关的旧机制一并彻底删除**。
> **不保留、不考虑历史兼容、不考虑历史包袱。**
>
> 含义：不是"语法糖映射"，不是"旧语法兼容通道"，不是"过渡期双轨"。凡 llm 函数语法
> （`llm ... llmend` / `__sys__` / `__user__` / `__llmretry__` / `llmretry` 顶层语法糖）
> 对应的语言级语法、parser/lexer token、AST 节点、semantic 分支、运行时注册载体
> （`callable_kind="llm_function"`）、执行路径（`_LLMFunctionMixin`）、provider 专用槽
> （`user_sys`）一律**删除**；其语义由统一的 LLMCallable 协议覆盖。

---

## 一、决策输入复核（引用权威，不重复决策正文）

| 决策 | 内容 | 权威出处 |
|------|------|---------|
| 1 | 内置类型协议方法表选 **B**（per-IbClass 协议方法表，系统化重构） | `_five_foundation_redesign.md` §五.决策1 |
| 2 | 内置类型行为改写 = **临时覆层机制**（默认不生效、flag 启用、作用域化） | §五.决策2 |
| 3 | snapshot 意图冻结**按文档补齐**（纯 snapshot lambda 也冻结意图） | §五.决策3 |
| 4 | `llm ... llmend` 语法**彻底删除**（本 session 再追加：旧机制一并删、不兼容不包袱） | §五.决策4 + 本文件 §〇 |
| 5 | retry **帧机制保留 + 语法/策略高阶化** | §五.决策5 |
| 6 | P1-P6 本主线，P7/P8 远期（已登记 VISION-4/VISION-5） | §五.决策6 |

---

## 二、P1-输入①：`LLMCallable` 协议方法族定稿

> 统一"可被 LLM 行为/意图/run_batch/stream 消费的可调用实例"的能力载体。
> 行为值（IbBehavior）、llm 可调用类实例、匿名 lambda 行为实例，全部经此协议统一消费。

### 2.1 协议定位与消费关系

**唯一消费端**：`LLMExecutor` 的**统一 worker**（`_call_llm` + `_parse_result`，已存在），
由一条统一装配路径 `assemble_llm_callable_request_cps` 按协议方法产 `LLMCallRequest`。

**协议身份**：注册为内置协议 `LLMCallable`（新条目进 `core/kernel/protocol.py::BUILTIN_PROTOCOLS`），
方法族见下。`SpecRegistry.satisfies_protocol(..., "llm_callable")` 成为"能否被 LLM 消费"的
**唯一判定**。

### 2.2 协议方法族（定稿）

| 协议方法 | 形态 | 签名约定（不含 self） | 返回类型 | 作用 / 对应旧机制 |
|---------|------|---------------------|---------|------------------|
| `__llm_call__` | **必需**，实例方法 | `(装配上下文) -> LLMCallRequest` | `LLMCallRequest`（内核对象，非语言类型） | 承载一次 LLM 调用请求的装配。**取代** llm 函数的 `__sys__`+`__user__` 段装配 |
| `__intent__` | 可选，实例方法 | `(IntentBlock) -> IntentBlock` | `IntentBlock` | 改写进入本次调用的意图（消解/增删/重排）。行为实例默认透传 |
| `__retry__` | 可选，实例方法 | `(retry 策略参数) -> ...` | 策略声明 | 高阶化 retry：声明快照策略 + 重试策略 + hint（见 §七） |
| `__to_prompt__` | **继承既有** prompt 协议族 | `() -> str` | `str` | 实例的提示呈现（已有，非新增） |

**协议方法必需/可选语义（self-grill 产出，务必定稿）**：
- **`__llm_call__` 为必需（required）方法**：参与 `satisfies_protocol(..., "llm_callable")`
  的**强制判定**（缺失 → 不满足 LLMCallable）。
- **`__intent__` / `__retry__` 为可选（optional）能力**：**不**参与 satisfies 的强制判定
  （缺失仍满足 LLMCallable）；仅在存在时经 `receive` 协议分派发现/调用。实现此语义须
  在 `ProtocolDef` 区分 required vs optional（P5/P6 落地：协议条目 methods 分两组）。
  缺省时内核提供默认行为——意图原样透传、retry 用帧默认策略。
- 保留 `__to_prompt__` 为 prompt 协议族既有的呈现通道（非 LLMCallable 新增方法），
  不新增重复的呈现接口（避免与 `PromptContributor` 重复）。

**`__llm_call__` 的装配上下文形态（定稿澄清）**：
- `LLMCallRequest` 是底层 dataclass（`core/base/llm_protocol/llm_call.py`），**不是语言
  对象**。用户可调用类 `__llm_call__` 如何构造它——P1 定稿：协议方法签名以"装配上下文"
  为参数（内核对象 `IbLLMCallAssemblyContext`，封装意图/输出契约/目标模型/retry 历史）。
  **语言层用户方法返回该上下文可消费的形态**；上下文到 `LLMCallRequest` 的映射由内核
  包装（`__llm_call__` 返回 IbObject，内核 `assemble_llm_callable_request_cps` 将其解析
  为底层 LLMCallRequest）。**行为值（IbBehavior）的 `__llm_call__` 是内核原生实现**，
  直接产出 LLMCallRequest（brief：cps 装配，见 §2.4）。

### 2.3 与 `LLMCallRequest` 的承载关系（单一权威）

`__llm_call__` **返回** `LLMCallRequest`（`core/base/llm_protocol/llm_call.py`，供应商无关
唯一契约）。装配上下文提供装配所需的内核级原始信息：意图栈（意图消解结果）、
输出契约（返回类型/格式化 hint）、目标模型 tag、retry 历史。**请求装配逻辑下沉到
协议实现**（行为值/llm 类各自实现 `__llm_call__`），内核只做"协议查询 → 调 `__llm_call__`
取请求 → 统一 worker 执行"。

**设计取舍（self-grill 自查）**：
- 为何请求装配下沉到协议而非内核统一？——因为行为值（语义槽模型）与 llm 可调用类
  （用户自定义槽）的**装配输入不同**，统一到一个内核函数里会重新引入 G3/D11 的
  `if 能力标志位` 过程式分派。协议方法承载装配 = 机制同构（design-philosophy §四），
  每条装配路径是其类型自身的 `__llm_call__`。
- 为何 LLMCallRequest 仍由内核 dataclass 承载而非语言类型？——LLMCallRequest 已是
  底层基础契约（`core/base`，可迁移到任何语言），保持纯数据 dataclass（不 DbObject 化），
  由 `__llm_call__` 实现方构造/返回。这是**契约层**，不是**语言对象层**，二者分层清晰。

### 2.4 消费路径统一（P4 落点，此处定设计）

```
[可调用实例] ── has LLMCallable ──► __llm_call__(装配上下文) ──► LLMCallRequest
                                        │
                                        ▼
                          _call_and_parse（统一 worker：_call_llm + _parse_result）
```

行为语句语法（`@~ ... ~`）降级为"匿名 llm 可调用类实例"的语法糖；llm 函数
（`llm ... llmend`）迁移为"具名 llm 可调用类实例"。二者最终都是实现 `LLMCallable` 的
可调用实例。**run_batch / stream 也统一消费"LLMCallable 实例"**（当前 `ai.run_batch`
只收 `behavior` 值且 `isinstance(behavior, IbValue) and name=="behavior"` 校验，见
`_llm_callable_redesign.md` §三.1/`_five_foundation_redesign.md` §一.4）——P1 定稿
`run_batch/stream` 签名改为"接受任何 LLMCallable 实例"。

---

## 三、P1-输入②：`llm ... llmend` 语法彻底删除 + 旧机制删除 + 全量迁移

> 用户裁定最高约束：**彻底删除，不保留、不兼容、不包袱**。本输入定稿删除范围 +
> 语义迁移映射 + 全量迁移清单。

### 3.1 删除范围（语言级 + 运行时，全部删除）

| 层 | 现落点（实证） | 处置 |
|----|--------------|------|
| lexer token | `core/compiler/lexer/core_scanner.py` L55-60（`llm`→LLM_DEF / `llmend`→LLM_END / `llmretry`→LLM_RETRY / `__sys__`→LLM_SYS / `__user__`→LLM_USER / `__llmretry__`→LLM_RETRY_HINT） | **删除**相关 token 与关键字 |
| lexer 块扫描 | `core/compiler/lexer/llm_scanner.py`（LLM 块内扫描器，整块） | **删除**整个块扫描器 |
| parser | `core/compiler/parser/components/declaration.py` L270-563（`llm_function_declaration` + LLM 块解析）+ `statement.py` L83-91（顶层 `llmretry` 语法糖） | **删除** LLM 函数声明语法解析 + llmretry 顶层语法糖 |
| AST | `core/kernel/ast.py` `IbLLMFunctionDef`（L198，`IbFunctionDef` 子类）+ 其 `sys_prompt/user_prompt/retry_hint` 字段 | **删除** `IbLLMFunctionDef`；`IbLLMExceptionalStmt` 保留（`llmexcept` 非 llm 函数语法，决策 5 保留帧机制的载体） |
| semantic | `symbol_collection_pass.py` L395-440 / `symbol_resolution_pass.py` L309 / `type_resolution_pass.py` L191 / `_declaration_visitors.py` L686 + 各 pass 内 `is_llm`/`isinstance(..., IbLLMFunctionDef)` 分支 | **删除** `IbLLMFunctionDef` 相关分支（`is_llm` 分支） |
| 运行时载体 | `IbUserFunction(callable_kind="llm_function")`：`user_functions.py` L25/L83-84、`interpreter.py` L791-799/L867-875、`vm/handlers/declarations.py` L181-192、`vm/handlers/_shared.py` `_vm_invoke_llm_function` L461、`dispatch.py` `IbLLMFunctionDef` 分派 | **删除** `callable_kind="llm_function"` 分支与 `_vm_invoke_llm_function` |
| 执行 mixin | `_LLMFunctionMixin`（`llm_executor/_llm_function.py` 整文件）+ `LLMFunctionCallSpec` | **删除**；装配并入 `__llm_call__` 协议实现 |
| provider 专用槽 | `core/base/llm_protocol/recommended.py` L116（`user_sys` 槽前置） | **删除** `user_sys` 槽特殊处理；llm 类经 `__llm_call__` 自定义槽 |
| 迁移映射 | `_behavior.py` 同构 `__llmretry__`/`_build_retry_message_history` | llm 类经 `__retry__` 协议高阶化（§七） |

### 3.2 语义迁移映射（旧段 → LLMCallable 协议方法）

| 旧语言段 | 旧语义 | 迁移到 |
|---------|--------|-------|
| `__sys__`（块内文本段） | 用户自设系统提示文本（作 `user_sys` PromptSlot） | `__llm_call__` 内以 `prompt_slots` 装配自定义槽（kind 自定义，user 自定义） |
| `__user__`（块内文本段） | 用户提示文本（作 `LLMCallRequest.user_prompt`） | `__llm_call__` 内填 `user_prompt` |
| `__llmretry__`（块内重试提示段） | 重试提示（作 `retry` PromptSlot） | `__retry__` 协议声明重试策略/hint；默认由帧机制提供 |
| `llmretry "hint"` 顶层语法糖 | 标记重试提示 | `__retry__` 更高阶的包装语法（§七） |

### 3.3 全量迁移清单（examples / trials / tests）

> 破坏面全量评估在 P4 实现前复核实跑；此处先列出**已知迁移点**（grep 实证的载体 +
> 用户可能使用的 `llm ... llmend` 写法）。

- `examples/`：含 `llm` 函数/`llmend` 的示例 → 迁移为 llm 可调用类写法（P4 逐个核对）。
- `trials/`：`trials/_toolkit/` 试用资产中含 llm 函数写法的 T 系列（如 N3 类 LLM 函数用例）
  → 迁移。
- `tests/`：`IbLLMFunctionDef`/`llm_function`/`__sys__`/`__user__`/`__llmretry__`/`llmend`
  相关测试 → **重写为新语义**（llm 可调用类）。**不为规避删除重构测试**（user-principles
  §三唯一底线：缺陷触发用例保留；语义随修复演进重构为新语义）。

---

## 四、P1-输入③：内置类型临时覆层机制形态定稿（决策 2）

> 最关键新设计约束。覆写内置类型相关协议是**临时的、用户特定优化/覆写目标**，
> 默认不生效、flag 启用、作用域化。

### 4.1 数据形态（与决策 1 B 结合）

覆层 = per-IbClass 协议方法表（§六）上的**影子/备用条目**：
- **默认态**：覆层条目**不参与分派**（`receive`/协议查询跳过影子条目），内置类型按
  原生默认行为运行。
- **启用态**：作用域内显式启用后，覆层条目成为分派候选，**优先级高于原生 vtable 方法**。

**与 D6 天然互补**：内置 spec 不可持久化（`_bootstrap_axiom_methods` 固定生成、不随
artifact 序列化），而覆层**默认不注入**、运行期按需注册——规避"编译期注入、运行期失忆"
问题。

### 4.2 声明语法（P2 落地，P1 定形态）

```text
# 声明一个针对内置类型某协议方法的临时覆层（P2 语法落点，形态草案）
impl Overlay for int:
    func __to_prompt__(self) -> str: ...
```

- 覆层仍走 `impl` 声明（`visit_IbImplDef` 对内置类型放行 → 记入影子表而非原生 vtable）。
- 与普通 `impl P for T` 的区别：普通 impl 立即生效（注册到方法表并参与分派）；
  覆层**仅登记影子条目，默认不生效**。

### 4.3 启用 flag 的作用域语义

- **作用域化**：覆层只在显式声明启用的作用域内生效（非全局永久覆写；区别于 Rust 全局
  trait impl）。
- **启用形态**（P2 定，P1 给候选）：作用域级 flag / 调用点声明。候选：
  - `with overlay(int.__to_prompt__): ...`（作用域块，推荐——与"作用域化"语义最强一致）；
  - 或模块级 `enable_overlay` 声明（作用域 = 本模块后续代码段）。
- **P1 推荐**：**作用域块**形态（显式进入/退出，语义清晰，天然作用域化，不泄漏到
  后续代码段），并支持模块级默认覆盖取消（若需）。

### 4.4 告警设计

基于"覆层存在/启用状态"：
- **存在但未启用**：声明了覆层但当前作用域未启用 → 提示性告警（"覆层已声明但未启用，
  内置类型按默认行为运行"），属可观测性信息，不阻断。
- **启用并生效**：作用域内启用覆层 → 记录行为告警（"int.__to_prompt__ 已被用户覆层
  改写"），供可观测性跟踪。

---

## 五、P1-输入④：per-IbClass 协议方法表全局数据形态定稿（决策 1 B）

> P2/P5/P6 的共享地基。P1 先定数据形态，P6 落地实现。

### 5.1 数据结构（IbClass 扩展）

`IbClass.__slots__` 当前只有 `methods`（vtable）。决策 1 B 新增**协议方法表**：

```text
# IbClass 新增（__slots__ 增加）：
protocol_vtable: Dict[str, IbFunction]   # 协议名 → 该协议的可调用方法载体的映射
                                            # （per-class 协议分派表；received 协议分支前置查表）
```

**命名注意（design-philosophy §八）**：新增字段名 `protocol_vtable`，与既有 `methods`
（vtable）区分。`methods` 保持为**原始方法名 → IbFunction** 的传统 vtable；
`protocol_vtable` 为**协议名 → 方法**的协议分派表（决策 1 B 的"per-IbClass 协议方法表"）。

### 5.2 `receive` 协议分支前置查表

`IbObject.receive`（`base.py` L41-65 附近）当前协议分支用 `_dispatch_<dunder>`（getattr
能力探测，D5）。决策 1 B：**协议分派前置查询 `protocol_vtable`**：

```text
receive(message, args):
    if message 是协议方法名:
        proto = 由 message 反查所属协议
        handler = protocol_vtable.get(proto)   # per-class 协议方法表（含继承/影子条目）
        if handler: return 分派
    # 否则走既有 vtable / _dispatch_* 路径
```

- **一举解决 D3**（`spec.members` vs `IbClass.methods` 双表不同步）与 **D5**（能力探测式
  getattr 分派）。与"协议一等公民"方向一致。
- 继承：`protocol_vtable` 沿 `parent` 链查找（与 `lookup_method` 同样式，机制同构）。

### 5.3 影子条目（覆层机制挂载点，见 §四）

`protocol_vtable` 每个协议条目可含：
- **原生条目**（vtable 原生实现，默认参与分派）；
- **影子/备用条目**（覆层声明，默认不参与分派，作用域启用后优先级高于原生）。

数据形态：`protocol_vtable: Dict[str, ProtocolSlot]`，其中 `ProtocolSlot` 含
`native: Optional[IbFunction]` + `overlay: Optional[IbFunction]`（+ 启用状态）。
P1 定形态，P6 落地为 `ProtocolSlot`（或等价结构）。

### 5.4 与既有协议判定（satisfies_protocol）的衔接

`SpecRegistry.satisfies_protocol`（编译期静态，读 `spec.members`）是**类型级判定**；
`receive` 前置查 `protocol_vtable`（运行期动态）是**值级分派**。二者职责不同：
- `satisfies_protocol`：编译期问"该类型是否满足协议"（类型检查/泛型 bound）；
- `receive` 前置查表：运行期问"该值如何分派某协议方法"。

决策 1 B 的 `protocol_vtable` 是**运行期分派表**；`satisfies_protocol` 仍是编译期
权威判定入口。**P6 落地时两者须收敛到单一权威**（协议条目承载判定 + 分派，
见 §五.5 / `_five_foundation_redesign.md` 交接点 5 三层划分）。

### 5.5 prompt 协议族类型类化（P5 衔接）

`core/kernel/axioms/prompt_protocol.py::PROMPT_PROTOCOL_SPECS` 现只有 4 方法
（无 `__payload_prompt__`，D1 双写真相）。P5 收敛：补 `__payload_prompt__`，与
`core/kernel/protocol.py::BUILTIN_PROTOCOLS` 的 `payload_prompt` 协议条目引用
**同一权威**；`PromptRenderer.to_prompt_str` 增 `satisfies_protocol` 前置判定；内置类型
经 `protocol_vtable` 影子条目允许用户覆层改写。P1 定稿确认该收敛方向（P5 落地）。

---

## 六、P1-输入⑤：snapshot 意图冻结补齐语义定稿（决策 3）

> 决策 3：认可以下原初语义——lambda = 引用捕获（不保证时不变/无状态）；
> snapshot = 冻结（保证时不变/无状态/可重入）。纯 snapshot lambda 也冻结意图。

### 6.1 现缺陷（D8，实证）

`vm_handle_IbLambdaExpr`（`llm_behavior.py` L159-243）仅在 `body_is_behavior` 时
`fork_intent_snapshot()`（L212-216）；`IbFnCallable` 无 `captured_intents` 字段——
**纯 snapshot lambda（非行为体）意图栈实际是"调用点 live"而非冻结**。与文档不符
（`docs/architecture/03_type_system.md` L461、`docs/subsystems/01_intent_system.md` L519）。

### 6.2 定稿语义：意图冻结=snapshot 值捕获策略的一部分

把"意图冻结"并入 snapshot 的"值捕获"策略：
- **snapshot 模式**：定义时对自由变量深克隆（值捕获）**并同时 fork 意图栈快照**
  （无论 body 是否行为体）。调用时意图栈用定义时刻快照（冻结），不随调用点 live 意图漂移。
- **lambda 模式**：不 fork 意图（引用捕获，调用点读当前意图栈——原初设计）。

### 6.3 捕获策略参数化的统一（交接点 2 结论）

`capture_mode` 值层已参数化（`IbFnCallable`/`IbBehavior` 构造器收 `capture_mode`）；
类型层完全隐形。P1 定稿：
- **意图冻结并入 capture_mode**：`snapshot` 携带"变量值冻结 + 意图冻结"双冻结；
  `lambda` 携带"变量引用 + 意图 live"双 live。
- **一致性**：行为值（IbBehavior）与纯函数值（IbFnCallable）对 snapshot 的意图语义
  一致（统一捕获策略参数化，修复 D8 文档漂移）。

### 6.4 落地形态

- `IbFnCallable` 增加 `captured_intents` 字段（与 `IbBehavior` 同构，消 D10 双类字段
  重复）——P1 定字段形态，P3 落地（意图一等值 + snapshot 冻结补齐）。
- `vm_handle_IbLambdaExpr` 移除 `body_is_behavior` 分支的意图 fork 特判 → 改为
  **按 capture_mode 统一决定**（snapshot 恒 fork，lambda 恒不 fork）。
- 移除死字段 `IbBehaviorExpr.is_callable_instance`/`IbBehaviorInstance.is_callable_instance`
  （`ast.py` L566/L581）与 `IbAssign.capture_mode` vestigial 死字段（`ast.py` L250，D9）——
  一并清理（P3 顺带）。

---

## 七、P1-输入⑥：retry 高阶化边界定稿（决策 5）

> 决策 5：帧机制保留 + 语法/策略高阶化（推荐 a）。

### 7.1 边界结论（承接交接点 3）

- **llmexcept 快照隔离/编译期写保护是 VM 级执行机制，不能也不应收敛为"高阶包装"**——
  它保护"被保护语句执行窗口内变量/意图/循环状态一致性"，依赖 CPS 帧栈
  （`LLMExceptFrame` + `_retry_llm_uncertain`，实证已读）。
- **收敛边界**：保留 `LLMExceptFrame` 帧机制作为 retry 执行基质；把 `retry`/`llmretry`
  语法收敛为"对可调用实例的高阶包装语法糖"（声明所需壳：快照策略 + 重试策略 + hint）。

### 7.2 高阶化后的形态

- **llm 可调用类可自定 retry**：实现 `__retry__` 协议方法（§2.2），声明快照策略
  （复用 `__snapshot__`/`__restore__`/深克隆）与重试策略。
- **行为语句默认 retry**：由帧机制提供默认策略（用户不写 `__retry__` 时行为实例走
  内置默认）。
- **retry 从"独立语法"收敛为"对可调用实例的高阶包装"**：`retry` 成为高阶函数，声明
  需要的壳（LLMCallable + 重试策略），包装后返回新可调用实例（与装饰壳体系同一机制，
  `_llm_callable_redesign.md` §3.4）。

### 7.3 执行基质不变（决策 5 保留）

`LLMExceptFrame`（`llm_except_frame.py`，388 行）与 `_retry_llm_uncertain`
（`_shared.py` L620-721）**保留作为执行机制**。P4 只把**语言级语法**（`retry` 语句、
顶层 `llmretry` 语法糖）收敛为高阶包装，帧机制作为其执行后盾不动。

---

## 八、P1-输入⑦：破坏面评估 + P2-P6 分阶段迁移路径

### 8.1 破坏面评估（分层总账）

| 层 | 影响 | 处置阶段 |
|----|------|---------|
| 语言级 | llm 函数语法/旧机制**彻底删除**（§三）；`run_batch/stream` 签名收敛为 LLMCallable 实例 | P2（impl/覆层基座）/ P4（语法删除+迁移） |
| 类型系统 | 新增 `LLMCallable` 内置协议；`callable_kind="llm_function"` 删除；`IbLLMFunctionDef` 删除；`protocol_vtable` 落点 | P1 定稿/P4/P6 |
| 编译器 | impl 目标放宽（内置/泛型/跨模块评估）；`visit_IbImplDef` 放行路径；`IbLLMFunctionDef` 语义分支删除；行为语句/意图段消费语义检查 | P2/P3/P4 |
| 运行时 | 意图值栈升级（G5）；行为语句/意图注释消费协议化（G1/G2）；`_vm_call_fn_callable` 与 `bind_behavior_closure` 合并（消双写）；`_LLMFunctionMixin` 删除；retry 高阶化 | P3/P4 |
| 契约 | LLMCallRequest 扩展（意图改写/retry 高阶承载）；`stream_call` 签名收敛；provider `user_sys` 槽删除 | P4/P5 |
| 数据 | `protocol_vtable`（决策1 B 基础设施）；snapshot `captured_intents` 字段 | P6/P3 |
| 文档/测试 | docs/ 同步（KNOWN_LIMITS/syntax/architecture/subsystems）；全量 pytest + 试用回归 | P9/各阶段 |

### 8.2 P2-P6 分阶段顺序与验证门

| 阶段 | 内容（承接 §四-§七 定稿） | 验证门 |
|------|--------------------------|--------|
| **P2** | 装饰壳体系地基：`visit_IbImplDef` 目标放宽（内置类型放行评估 + 跨模块）；**临时覆层机制语法/AST/语义落点**（决策 2：声明语法/作用域 flag/影子条目）；函数实例默认 prompt 呈现协议化（`to_prompt` 死条目激活）；`_dispatch_<dunder>` 收敛为 `protocol_vtable` 查表 | 全量 pytest 零回归 + 本地 commit |
| **P3** | 意图一等值化（`IbIntent.content: str` → 可渲染值栈，`IntentValue`）；**snapshot 意图冻结补齐**（决策 3：纯 snapshot lambda 也冻结，移除 `body_is_behavior` 特判）；行为语句/意图注释消费协议化（G1/G2/G5）；意图可调用类死字段清理（D9） | 全量 pytest + 试用回归 |
| **P4** | llm 可调用类内核 + retry 高阶化 + **`llm/llmend` 语法与旧机制彻底删除**（决策 4 最高约束 + §三 全量迁移）：统一 LLMCallable 消费路径（D9/D11/D12）、`_vm_call_fn_callable` 与 `bind_behavior_closure` 合并（消双写）、retry 高阶化（决策 5 + §七）、删除 `_LLMFunctionMixin`/`IbLLMFunctionDef`/`callable_kind="llm_function"`/provider `user_sys` 槽 | 全量 pytest + T09 风格试用 |
| **P5** | prompt 协议族类型类化（D1 双注册表收敛、补 `__payload_prompt__`）+ 能力公理收尾（G7 三层划分，交接点 5）；str output_hint 补齐（D4）；PromptRenderer 协议前置 | 全量 pytest + 文档治理 |
| **P6** | **per-IbClass 协议方法表落地**（决策 1 B，§五）：`protocol_vtable` + `receive` 前置查表 + 影子条目；spec.members 与 vtable 双表同步（D3/D6）；内置模块声明协议 | 全量 pytest + 内置改写 e2e |

**顺序依赖**：P2（impl 扩展 + 覆层机制，为 P4 llm 类提供壳）→ P3（意图一等值 + snapshot
冻结补齐，为 P4 消费铺垫）→ P4（核心闭环：llm 类 + llmend 删除 + retry 高阶化 + 统一消费）。
P5/P6 依赖 P2 的 impl/覆层路径（协议表为 P5 prompt 类型类化 + P6 落地的共享地基）。
P7/P8 远期（VISION-4/5，已登记）。

### 8.3 破坏性重构分支政策（本主线落地纪律）

- P1-P6 中**确认低风险/边界清晰**（全量 pytest 零回归 + 复核放行，无对外契约/架构级
  风险）的改进 → 直接 **merge** `unsafe-vibe-dev`（2026-08-18 合并细则）。
- P6（`protocol_vtable` 改 `IbClass.__slots__` + receive + 水化 + 序列化契约）改动面大，
  **走独立分支原型验证**（决策 1 B 风险控制），确认后合并。
- 全程本地 commit；**禁 push**（除非用户显式授权）。

---

## 九、待下 session 自主裁定（无需用户，仅记录决策依据）

P1 内机制形态细节、P2-P6 实现顺序微调、告警文案、测试补丁重构（如 `__retry__`
的具体参数形态、覆层声明的精确语法、`protocol_vtable` 序列化细节）——按
"自主推进偏好 + 工作模式定论"执行，详尽记录决策依据于 WORKLOG。

---

## 附、本文件待办（P1 定稿输出的自检）

- [x] `LLMCallable` 协议方法族 + `LLMCallRequest` 承载（§二）
- [x] llm 函数语法彻底删除 + 旧机制删除 + 全量迁移映射表（§三）
- [x] 临时覆层机制形态（决策 2，§四）
- [x] per-IbClass 协议方法表全局数据形态（决策 1 B，§五）
- [x] snapshot 意图冻结补齐（决策 3，§六）
- [x] retry 高阶化边界（决策 5，§七）
- [x] 破坏面评估 + P2-P6 分阶段迁移路径（§八）
