# 临时设计文档：五大地基改造调研与总路线规划

> **性质**：临时任务控制文档（设计阶段）。落地后按 `tasks_docs/GOVERNANCE.md` 收敛到
> `docs/`，本文件删除（git 承载历史）。**本任务不是代码编写任务**——交付"交接清单
> 深挖调研 + 五大地基现状评估 + 总路线设计"。
>
> **承接关系**：本文件承接 `tasks_docs/_llm_callable_redesign.md`（llm 可调用类 +
> 总统一性主线调研基准）的 §6bis.3「仍待下个 session 深挖的补充调研点（交接清单）」，
> 将其 6 项调研点**全部完成**，并进一步扩展为五大地基（函数式编程 / 类型类体系 /
> 类型理论 / 高阶函数 / 协议化）的完整改造路线。用户 2026-08-18 定方向。

---

## 〇、任务定位与调研方法

用户（2026-08-18 延续）提出的最终目标：**规划并设计一条路线，把 IBCI 完成彻底的
函数式编程、类型类体系、类型理论地基、高阶函数理论地基、协议化体系地基的完整改造**。
本 session 任务 = ① 完成交接清单 6 项补充调研（此前仅完成可行性，未落到机制形态）；
② 五大地基现状评估（对照现代主流语言）；③ 总路线设计（分阶段 + 验证门 + 破坏面）。

**调研方法**：全部结论经代码实证（文件 + 行号 + 关键片段）；关键判定（如
`satisfies_protocol(int,'to_prompt')` 探针）经 `core.kernel.factory.create_default_registry()`
实跑验证。部分深挖委托 subagent（同步模式，本环境后台 subagent 不稳定已弃用），
产出已核验。

---

## 一、六项补充调研结论（交接清单 §6bis.3 全部完成）

### 1. 内置类型协议方法表的机制形态（交接点 1）

**现状**：
- 编译期 `impl` 目标三道拦截全在
  `core/compiler/semantic/passes/_declaration_visitors.py::visit_IbImplDef`（70-153 行）：
  ① kind 非 CLASS → `SEM_TYPE_MISMATCH` "impl target '...' is not a known class"（内置
  int/str/list 是 PRIMITIVE）；② provenance 非 USER_DEFINED/EXTERNAL_MODULE → "must be
  a user-defined or host-bound class"（内置是 KERNEL_NATIVE）；③ type_params 非空 → "is
  generic"。
- 运行期 `core/runtime/interpreter/interpreter.py::_hydrate_user_classes`（846-881）已有
  "impl 方法注册到 target vtable" 逻辑，`registry.get_class("int")` 可命中内置类——
  `target.register_method('__to_prompt__', IbUserFunction(...))` 在封印前执行，技术路径**已通**。
- 内置类型 prompt 渲染不依赖协议注册表：文本走 `PromptRenderer.to_prompt_str` →
  `val.receive('__to_prompt__')` → vtable 原生方法（`primitive_initializer.py` 显式注册
  int L397/str L421/list L453 等）；`satisfies_protocol(int,'to_prompt') == False`（探针实证），
  `to_prompt` 协议条目**零消费者**（半接通/死条目）。

**落地机制形态（三选一，需定稿）**：
- **A. spec.members 注入 + vtable 覆写**（最小改动）：impl 对内置类型放行后，编译期把方法
  注入内置 spec.members + 运行期水化注册 vtable。问题：内置 spec 由公理
  `_bootstrap_axiom_methods` 固定生成、不随 artifact 序列化，需水化端增量注入，有
  "编译期可见、运行期失忆"风险（须单点落水化）。
- **B. per-IbClass 协议方法表**（符合 LANGUAGE_DESIGN_EVOLUTION L139 "运行期协议方法表"方向）：
  `IbClass` 增协议方法表（当前 `__slots__` 只有 `methods` vtable，无协议表），`receive` 的
  协议分支前置查询。改动面大但系统性强，与协议一等公民方向一致。
- **C. `_dispatch_<dunder>` Python 钩子**（现成模式）：`IbFnCallable`/`IbBehavior` 已用
  `_dispatch_to_prompt` 拦截（`callables.py` L174/L410）。缺点：钩子按 Python 实现类定义，
  数值/容器类无此钩子，需逐类扩展，且是能力探测式分派（D5）。

**关键障碍**：`satisfies_protocol` 读 `spec.members`（编译期静态），`receive` 读
`IbClass.methods`（运行期 vtable）——**双表不同步**。内置类型 impl 必须在两处同时落地才闭环。

### 2. lambda/snapshot 捕获策略参数化落点（交接点 2）

**结论先行**：`capture_mode` 在**值层已完全参数化**（`IbFnCallable`/`IbBehavior` 构造器即收
`capture_mode` 参数，`RuntimeObjectFactory.create_fn_callable` L45-47），**类型层完全隐形**
（`CALLABLE_INSTANCE` spec 不含它，`core/kernel/spec/registry/factory.py` L276-279 有意为之）。

**改造面集中在运行时闭包机制三处**：
- `core/runtime/vm/handlers/llm_behavior.py::vm_handle_IbLambdaExpr`（L159-243）：定义时按
  capture_mode 构建 closure（lambda→`ScopeImpl.promote_to_cell` 共享 IbCell；snapshot→
  `try_deep_clone` 深克隆种子）+ 意图 fork 决策（L212-216）。
- `core/runtime/vm/handlers/_shared.py::_vm_call_fn_callable`（L235-311）：每次调用按模式绑定
  （lambda→`cell.get()` 读最新；snapshot→种子再深克隆注入子作用域，L257-274）。
- `core/runtime/objects/primitives/callables.py::bind_behavior_closure`（L183-224）：行为路径
  已共享绑定器（snapshot 再克隆 L197-201）——**统一绑定器的现成基准**。

**割裂点**：
- 两个关键字/token（`tokens.py` L17-18 `LAMBDA`/`SNAPSHOT`）。
- 运行时闭包构建/调用绑定按 capture_mode 双分支（同一机制的两种实现路径，非参数化分派）；
  `_vm_call_fn_callable` 内联绑定 vs `bind_behavior_closure` 是**双份同构实现**（消双写落点）。
- **意图快照只对行为体执行**：`vm_handle_IbLambdaExpr` 仅在 `body_is_behavior` 时 fork 意图
  （L212），`IbFnCallable` 无 `captured_intents` 字段——纯 snapshot lambda（非行为体）意图栈
  实际是"调用点 live"而非冻结。**与文档不符**（`docs/architecture/03_type_system.md` L461、
  `docs/subsystems/01_intent_system.md` L519 均称 snapshot 定义时 fork 意图栈）。
- `IbBehaviorExpr.is_callable_instance`/`IbBehaviorInstance.is_callable_instance`（`ast.py`
  L566/L581）**死字段**：裸 `@~...~` 永不成为可调用值（vm_handle_IbBehaviorExpr 的
  is_callable_instance 分支实际是死代码——唯一活着的 IbBehavior 构造路径是"lambda/snapshot
  的 body 是行为表达式"）。
- `IbAssign.capture_mode`（`ast.py` L250）vestigial 死字段。
- 类型/运行期双工厂同名不同签名（spec 工厂 `create_fn_callable` vs 运行期工厂
  `create_fn_callable`）；`IbFnCallable`/`IbBehavior` 五字段（capture_mode/params_uids/
  closure/param_types/return_type）双份声明。

### 3. retry 协议化边界（交接点 3）

**现状**：
- `LLMExceptFrame`（`core/runtime/interpreter/llm_except_frame.py`）：帧持有 `saved_vars`
  （深克隆变量快照）、`saved_intent_ctx`（意图 fork）、`saved_loop_context`、`retry_hint`、
  `attempt_history`（失败尝试历史，多轮对话用）、`should_retry`。用户协议优先（`__snapshot__`
  /`__restore__`），深克隆兜底。
- 重试循环 `_retry_llm_uncertain`（`core/runtime/vm/handlers/_shared.py` L620-721）：
  save_llm_except_state 建帧 → 循环内 restore_snapshot → 重求值被保护表达式 → 执行 handler
  body（`retry` 语句设 should_retry/retry_hint）→ verify_snapshot_integrity（写保护校验，
  RUN_LLMEXCEPT_SNAPSHOT_VIOLATION 告警）→ record_uncertain_attempt → increment_retry →
  耗尽抛 `LLMRetryExhaustedError`。**这是 VM 级状态快照机制，与 CPS 执行模型强耦合**。
- `_llm_function.py`：`__llmretry__` 块 → `PromptSlot(kind="retry")`；`attempt_history` →
  `build_retry_message_history_from_attempts` 多轮消息回喂。`_behavior.py` 同构
  （`_build_retry_message_history`）。
- `LLMProvider.get_retry`（`core/base/llm_protocol/provider.py`）：provider 侧重试能力。

**边界结论**：
- **llmexcept 快照隔离/编译期写保护是 VM 级执行机制，不能也不应收敛为"高阶包装"**——它保护
  的是"被保护语句执行窗口内的变量/意图/循环状态一致性"，依赖 CPS 帧栈。高阶包装（retry 作为
  对可调用实例的包装）可以**声明快照策略**（复用 `__snapshot__`/`__restore__`/深克隆），但
  执行基质仍是帧机制。
- **收敛边界（推荐）**：保留 LLMExceptFrame 帧机制作为 retry 执行基质；把 `retry`/`llmretry`
  语法收敛为"对可调用实例的高阶包装语法糖"（声明需要的壳：快照策略 + 重试策略 + hint），
  llm 派生类可自定 retry（协议方法），行为语句默认 retry 由帧机制提供。**即"帧机制保留、
  语法与策略高阶化"**——与 `_llm_callable_redesign.md` §三.4 的 retry 高阶化方向一致。
- 割裂点：retry 目前是独立语法（`retry "..."` 语句）+ 独立帧机制，与函数/行为/意图机制
  不共享"重试策略"声明；`__llmretry__` 是魔法段名而非协议。

### 4. 行为语句匿名可调用实例 vs 用户 llm 可调用类实例统一点（交接点 4）

**现状（两条执行路径已高度收敛到 LLMCallRequest）**：
- 行为语句：`vm_handle_IbBehaviorExpr`（llm_behavior.py L104-156）→ 若 is_callable_instance
  构造 IbBehavior；否则 `execute_behavior_expression_cps` → `_prepare_behavior_call_cps`
  （段求值 + 意图消解 + output hint + retry）→ **LLMCallRequest** → `_call_and_parse`（worker
  线程 `_call_llm` + `_parse_result`）。
- LLM 函数：`IbUserFunction(callable_kind="llm_function")` → `_vm_invoke_llm_function` →
  `execute_llm_function_cps` → `_prepare_llm_function_call_cps` → **LLMCallRequest**（把
  `__sys__` 作为 `PromptSlot(kind="user_sys")`，`__user__` 作 user_prompt）→ `_call_and_parse_llm_function`。
- 两条路径**共享同一 LLMCallRequest 契约 + 同一 `_call_llm`/`_parse_result` worker 执行**，
  差异仅在请求装配（行为=语义槽，llm 函数=sys/user 字符串段）——即 **G3/G4 割裂已收窄到
  "请求装配的输入形态"**。
- 可调用类 `__call__`：`_UserCallDrive`（`ib_class.py` L81）+ `_dispatch_call`（L166-168），
  仅承载确定性调用，**无 LLM 语义**。

**统一点（推荐）**：引入统一 "LLMCallable" 协议（`_llm_callable_redesign.md` §三.1 草案），
一切可被行为语句/意图/run_batch/stream 消费的实体（行为值、llm 可调用类实例、匿名 lambda
行为实例）都实现它。消费路径合并为：**协议查询（确认 LLMCallable）→ 请求装配（按协议方法
产 LLMCallRequest）→ `_call_and_parse` 统一 worker**。行为语句语法（`@~...~`）降级为匿名
llm 可调用类实例的语法糖。llm 函数（`llm ... llmend`）迁移为具名 llm 可调用类实例的语法糖
（真设计，废除 `__sys__`/`__user__` 段）。`ai.run_batch`/`stream` 消费统一到"LLMCallable
实例"（当前 run_batch 只收 `behavior` 值，`isinstance(behavior, IbValue) and name=="behavior"`
校验 L386）。

### 5. 能力公理 → 协议满足关系收敛（交接点 5，G7）

**现状**：
- `TypeAxiom`（`core/kernel/axioms/protocols.py` L42-107）10 个能力布尔（has_call_cap/
  has_iter_cap/has_subscript_cap/has_operator_cap/has_converter_cap/has_parser_cap/
  has_from_prompt_cap/has_output_hint_cap/has_payload_prompt_cap/has_llm_call_cap）为**声明值**；
  能力字段名与协议的映射单点在协议条目（`protocol.py` 的 `axiom_cap` 字段）。
- `SpecRegistry.satisfies_protocol`（`spec/registry/_protocol.py` L74-120）数据驱动判定：
  动态类型→True；PROTOCOL kind→False；callable 专用路径；kind 特判集 → axiom_cap →
  structural_methods。消费端经 `_capabilities.get_*_cap(spec, 协议名)` 经协议条目解析字段名，
  不直读。
- 用户协议注册：`protocol P:` → `register_from_spec` 派生 methods；`class C implements P` →
  符号收集记 implements + `_check_class_implements` 校验；`impl P for T` → spec.implements.append。

**收敛层次建议（三层划分）**：
- **类型层**（kind / is_compatible / is_class / is_module / is_dynamic）：不是"能力"，是类型
  元属性，**不收敛进协议满足关系**，保留 axiom 元属性方法。
- **行为层**（call/iter/subscript/operator/converter/parser/from_prompt/output_hint/
  payload_prompt）：可收敛为协议满足关系——已基本收敛（协议条目 + satisfies_protocol），
  残留是 `has_llm_call_cap`（LLM 可调用，将并入 LLMCallable 协议）与 `to_prompt`/`validate_prompt`
  死条目（见交接点 6）。
- **编译期推断专用**（resolve_return_type_name/get_element_type_name/resolve_item_type_name/
  resolve_operation_type_name/can_convert_from/parse_value）：是类型推断服务，非能力声明，
  保留 axiom 方法（签名仍走字符串边界），**不映射用户协议**。
- 用户可声明新能力 = 声明新协议（语法已支持）；能力公理封闭 flag 集合最终只保留"内核内置
  行为实现载体"角色，能力查询全部经协议条目。

### 6. prompt 协议族类型类化（交接点 6）

**现状（双权威 + 死条目 + 字符串分派）**：
- **双注册表（D1 双写真相）**：`core/kernel/axioms/prompt_protocol.py::PROMPT_PROTOCOL_SPECS`
  （仅 4 方法 `__to_prompt__`/`__from_prompt__`/`__outputhint_prompt__`/`__validate_prompt__`，
  **无 `__payload_prompt__`**）vs `core/kernel/protocol.py::BUILTIN_PROTOCOLS`（13 协议含
  payload_prompt）。同一概念两处定义、精度不一致。
- **`to_prompt` 协议零消费者（D2）**：全仓无 `satisfies_protocol(...,'to_prompt')` 调用；
  内置 int 不满足（探针）。类型级"满足"与运行期 vtable 渲染完全脱节。
- **分派方式混用**：`receive('__to_prompt__')` 字符串方法查找（PromptRenderer.to_prompt_str
  L42）为主；`satisfies_protocol` 协议查询仅作 payload_prompt/output_hint/from_prompt 的
  "判定前置"；`_dispatch_<dunder>` 按 Python 类钩子。
- `str` 缺 `has_output_hint_cap`（D4）：`satisfies_protocol(str,'output_hint')==False`，与
  int/list 不一致。

**类型类化方案**：把 5 个 prompt 协议方法收敛为**内建类型类方法族**，统一进
`PROMPT_PROTOCOL_SPECS`（补 `__payload_prompt__`），`BUILTIN_PROTOCOLS` 的 prompt 相关条目
改为引用同一权威；`PromptRenderer.to_prompt_str` 增加 `satisfies_protocol` 前置判定；内置
类型经"内置类型协议方法表"（交接点 1）允许用户 `impl` 改写；编译期
`PROMPT_PROTOCOL_SIGNATURE_FREE` 与运行期 `_dispatch_<dunder>` 收敛为同一协议方法分派。

---

## 二、五大地基现状评估

> 评分 0-5（0=无，5=现代主流语言水准）。对照 Haskell/Rust/Swift/TS/ML。

### 2.1 函数式编程地基 — 评分 3/5

| 能力 | 现状 | 证据 |
|---|---|---|
| 一等函数值 | ✅ `fn f = myFunc`、函数引用可传参/返回 | `docs/syntax/05_functions.md` §5.5 |
| 闭包 | ✅ lambda（cell 引用捕获）/snapshot（值捕获）、嵌套函数自动 cell 捕获 | `docs/architecture/03_type_system.md` §7.4 |
| 高阶函数签名 | ✅ `fn[(...)->(...)]` 结构约束（参数数量+类型+返回） | §5.6 |
| 泛型函数 | ✅ `func identity[T](T x) -> T` / `func first[T: Proto](...)`（编译期 bound 检查） | `parser/components/declaration.py` L231-261 |
| 生成器/惰性 | ✅ `yield`/`yield from`（阶段 5 下一主线已实现） | §5.8-5.9 |
| 可调用类实例 | ✅ `__call__` 协议 + `_UserCallDrive` CPS | KNOWN_LIMITS §一 |
| 组合子（map/filter/reduce/fold） | ❌ 无（builtin_modules/prelude 零注册） | grep 实证 |
| 部分应用/柯里化 | ❌ 无 | — |
| 不可变数据结构 | ❌ 可变优先（list/dict 引用语义） | KNOWN_LIMITS §五 |
| 纯函数标注 | ❌ 无 | — |
| 模式匹配/ADT | ❌ enum 是底层值非 ADT；无 match | KNOWN_LIMITS §二 |

**结论**：一等函数/闭包/高阶签名/泛型函数地基已好；缺组合子、部分应用、ADT/模式匹配、
不可变与纯函数标注。**函数式改造优先补"协议化的高阶组合子"与"ADT/模式匹配"**（后者依赖
类型理论地基）。

### 2.2 类型类体系地基 — 评分 3/5

| 能力 | 现状 | 证据 |
|---|---|---|
| 协议声明/继承 | ✅ `protocol P:` / `protocol Child(Parent):` | `docs/syntax/06_oop.md` §6.8 |
| implements | ✅ `class C implements P`（缺失/签名不兼容编译期报错） | §6.8 |
| retroactive impl | ✅ `impl P for T`（可带方法体补缺失方法） | §6.8 |
| 泛型 bound | ✅ `class Box[T: Greeter]` / `func call[T: Greeter](T x)` | §6.8 + KNOWN_LIMITS §26 |
| 协议作为类型约束 | ✅ 泛型 bound 编译期生效 | T09 实证 |
| **impl 目标范围** | ❌ 限本模块用户类；内置/泛型/跨模块不支持 | KNOWN_LIMITS §26 |
| 关联类型 | ⚠️ 泛型协议 `protocol Container[T]` 有类型参数，但无"关联类型成员"概念 | — |
| 默认实现 | ⚠️ impl 可带方法体，但无协议内默认实现 | — |
| 实例一致性规则 | ⚠️ 有 SEM_REDEFINITION 冲突检查，无连贯性/孤儿实例规则 | — |
| 运行时协议方法表 | ❌ 无（IbClass 只有 vtable） | 交接点 1 |

**结论**：类型类（协议）语法/编译期约束已落地；核心缺口 = **impl 目标扩展（内置/泛型/跨模块）+
运行时协议方法表 + 关联类型/默认实现等类型类完整语义**。

### 2.3 类型理论地基 — 评分 3/5

| 能力 | 现状 | 证据 |
|---|---|---|
| 三层类型表示 | ✅ TypeRef/TypeDef/TypeAxiom，结构化/可哈希/可序列化 | `docs/architecture/03_type_system.md` |
| 名义 vs 结构化 | ⚠️ 用户类名义 + 容器结构化 + fn[...] 结构匹配 | §3 |
| Optional 空安全 | ✅ `Optional[T]` 统一值模型 | §8 |
| 泛型（类/函数/bound） | ✅ 特化（reified）+ substitute | §6.3 |
| 类型推断 | ⚠️ `auto` 首次赋值锁定 + 轻量约束检查，**非 HM 约束求解** | KNOWN_LIMITS §七（HM 为非目标） |
| 子类型/变体 | ⚠️ assignability（含 Optional/继承链/协变返回），无形式化变体规则文档 | — |
| 联合类型/ADT | ❌ enum 是底层值；无 union/Result/Either | — |
| 模式匹配 | ❌ 无 match | — |
| 泛型特化身份 | ✅ reified 物化特化类（C#/Kotlin 同族） | `03_type_system.md` §3.4ter |

**结论**：地基认真（三层分离 + 结构化类型引用 + reified 特化），但推断停留在轻量检查、
无 ADT/union/模式匹配。**类型理论改造优先级 = ADT/枚举实例化 + 模式匹配 + 推断扩展（轻量
约束收集，非完整 HM）**。

### 2.4 高阶函数理论地基 — 评分 3.5/5

| 能力 | 现状 | 证据 |
|---|---|---|
| fn[...] 签名约束 | ✅ CALLABLE_SIG + 结构匹配 | `docs/architecture/03_type_system.md` §7.3 |
| 裸 fn"任意可调用" | ✅ 参数/返回位置强制可调用 | §7.2 |
| callable 内省 | ✅ `type(f)` 签名形态 / `f.__return_type__()` | §5.7 |
| 高阶消费（行为/意图） | ⚠️ 行为语句只能经 lambda 包成可调用值；裸 `@~` 非可调用值（死字段） | 交接点 4 |
| 函数组合/柯里化 | ❌ 无 | — |
| 高阶与 LLM 融合 | ⚠️ 行为 = 匿名可调用实例；llm 函数 = 独立语法 | 交接点 4 |

**结论**：签名约束/内省好；缺组合子、部分应用；核心割裂是"可调用实例消费"未统一（交接点 4）。

### 2.5 协议化体系地基 — 评分 3.5/5

| 能力 | 现状 | 证据 |
|---|---|---|
| 协议注册表 | ✅ ProtocolDef/Registry + satisfies_protocol 唯一判定 | `core/kernel/protocol.py` |
| 内置协议 | ✅ 13 个（callable/iterable/subscriptable/operator/converter/parser/to_prompt/from_prompt/validate_prompt/output_hint/payload_prompt/snapshotable/attribute） | protocol.py |
| 运行时分派 | ✅ receive + vtable + `_dispatch_<dunder>` | base.py L41-65 |
| prompt 协议族 | ⚠️ 双权威 + to_prompt 死条目 + 字符串分派 | 交接点 6 |
| 能力公理 | ⚠️ 10 flag 封闭集合（映射已在协议条目，但仍是封闭） | 交接点 5 |
| 内置类型协议表 | ❌ 无 | 交接点 1 |
| 模块协议化 | ❌ 内置模块 TypeDef 字面量不声明协议；宿主绑定走 bind | 交接点 1/6 |
| retry 协议化 | ❌ 独立语法 + 独立帧 | 交接点 3 |

**结论**：协议化地基最接近目标（Phase 0-2 已落地）；剩余缺口集中在内置类型协议表、prompt
协议族类型类化、能力公理收尾、retry/llm 调用协议化——即本主线 P1-P5。

---

## 三、割裂点总账（跨全部调研汇总）

| # | 割裂 | 来源 | 定性 |
|---|------|------|------|
| G1 | 函数实例插值行为语句 → 只渲染占位符 | 交接文档 | 消费路径缺协议化 |
| G2 | 函数实例放入意图注释 → 无有意义嵌入（意图栈存 AST 节点对象） | 交接文档 | 意图未一等值化 |
| G3 | llm 函数仍用 `__sys__`/`__user__` 段 → 直接要求底层请求格式 | 交接文档 + 本调研 | 语言级割裂 |
| G4 | `ai.stream_call/stream_channel` 仍吃 `(sys_prompt, user_prompt)` 字符串 | 交接文档 | 同上 |
| G5 | 意图栈本质是字符串栈（`IbIntent.content: str`） | 交接文档 + intent.py L45 | 非一等值栈 |
| G6 | `__prompt__` 协议族是魔法 dunder，散落多层手工实现 | 交接文档 | 未类型类化 |
| G7 | 能力公理 has_*_cap 是封闭 flag 集合 | 交接文档 + protocols.py | 未完全协议化 |
| D1 | prompt 协议双注册表（PROMPT_PROTOCOL_SPECS vs BUILTIN_PROTOCOLS） | 本调研（prompt 子报告） | 双写真相 |
| D2 | to_prompt 协议零消费者 + 内置不满足（死条目） | 本调研 | 半接通 |
| D3 | satisfies_protocol 读 spec.members vs receive 读 IbClass.methods 双表不同步 | 本调研 | 双通道 |
| D4 | str 缺 output_hint 能力（与 int/list 不一致） | 本调研 | 同族不一致 |
| D5 | receive 协议分支 getattr 探测 `_dispatch_<name>`（能力探测变体） | 本调研 | 反射/探测 |
| D6 | 内置 spec 不可持久化（编译期注入有运行期失忆风险） | 本调研 | 设计约束 |
| D7 | 内置 prompt 覆写语义未定（静默覆盖 vs 显式声明） | 本调研 | 语义待决 |
| D8 | 意图快照只对行为体执行（纯 snapshot lambda 不冻结意图，与文档不符） | 本调研（lambda 子报告） | 文档漂移 |
| D9 | 裸 `@~...~` 永不成为可调用值（is_callable_instance 死字段） | 本调研 | 死代码 |
| D10 | 双工厂同名不同签名（spec vs 运行期 create_fn_callable）+ 双类字段重复 | 本调研 | 设计语言割裂 |
| D11 | llm 函数 vs 行为两条装配路径（sys/user 段 vs 语义槽）并存 | 本调研 | 双通道 |
| D12 | 意图可调用类仅确定性 `__call__`，无 LLM 语义通道 | 本调研 | 缺 LLMCallable 协议 |

---

## 四、总路线设计（把五大地基完整改造）

> **设计准绳**（承接 `_llm_callable_redesign.md` §6bis.2）：凡新设计，先问"它是否是一个
> 可调用实例 + 一个协议"；凡机制，先问"它的捕获策略/包装策略能否参数化"。
> 每阶段守全量 `python -m pytest tests/` 零回归 + 本地 commit + 禁 push（除非用户授权）；
> 大范围破坏性重构走独立分支，零风险改进经复核直接合并 unsafe-vibe-dev。
> 同一时刻只主推一个 P0。

| 阶段 | 主题 | 目标（五大地基归属） | 关键改造点（精确） | 验证门 |
|------|------|---------------------|---------------------|--------|
| **P1** | llm 可调用类设计定稿（承接 `_llm_callable_redesign.md` P1） | 类型类 + 协议化 | 协议方法族 `LLMCallable`（`__llm_call__` 等）/意图改写 `__intent__`/retry 高阶化 `__retry__`；与 LLMCallRequest 承载；**llm 函数语法（`llm ... llmend`/`__sys__/__user__/__llmretry__`）彻底删除与迁移策略（决策 4）**；**内置类型临时覆层机制设计输入收敛（决策 2，见 §五）** | 设计质询 + 破坏面全量评估 |
| **P2** | 装饰壳体系地基 | 类型类 + 高阶函数 | `visit_IbImplDef` 目标放宽（内置/泛型放行路径评估 + 跨模块）；**内置类型临时覆层机制语法/AST/语义落点（决策 2：默认不生效、flag 启用、作用域化）**；函数实例默认 prompt 呈现协议化（`to_prompt` 死条目激活）；`_dispatch_<dunder>` 收敛 | 全量 pytest 零回归 |
| **P3** | 意图一等值化 + 行为语句/意图消费协议化 | 函数式 + 类型类 | 意图值栈升级（`IbIntent.content: str` → 可渲染值栈，`IntentValue` 协议）；**snapshot 意图冻结按文档语义补齐（决策 3：纯 snapshot lambda 也冻结意图）**；修复 G2/G5/G9（意图段求值渲染）；行为语句消费按协议分派（修复 G1） | 全量 pytest + 试用回归 |
| **P4** | llm 可调用类内核 + retry 高阶化 + llm 函数语法删除 | 协议化 + 高阶函数 | 统一 LLMCallable 消费路径（修复 D9/D11/D12）：行为值/llm 可调用类实例/匿名 lambda 行为实例统一；`_vm_call_fn_callable` 与 `bind_behavior_closure` 合并（消双写）；retry 高阶化（决策 5：保留帧机制、语法/策略协议化，交接点 3 结论）；**`llm ... llmend` 语法彻底删除 + 全量迁移示例/试用/测试（决策 4）** | 全量 pytest + T09 风格试用 |
| **P5** | prompt 协议族类型类化 + 能力公理收尾 | 类型理论 + 协议化 | 双注册表收敛（D1）；to_prompt/validate_prompt 条目补全（D2）；PromptRenderer 协议前置；str output_hint 补齐（D4）；能力公理三层划分落地（交接点 5 结论，G7） | 全量 pytest + 文档治理 |
| **P6** | 内置类型协议方法表 + 模块协议化 | 类型类 + 协议化 | **per-IbClass 协议方法表（决策 1：选 B，系统化重构）** + 临时覆层机制落地（决策 2：覆层作协议表影子条目，默认不参与分派，启用才生效）；spec.members 与 vtable 双表同步（D3/D6）；内置模块声明协议 | 全量 pytest + 内置改写 e2e |
| **P7** | 类型理论加固 | 类型理论 | **远期规划（决策 6）**：ADT（enum 升级为实例化成员）/联合类型可选；模式匹配 `match`（建立在协议+泛型上，LANGUAGE_DESIGN_EVOLUTION §3.7/Phase 4）；轻量约束收集推断扩展（非完整 HM，HM 仍非目标）；fn[...] 变体规则形式化 | 全量 pytest + 新语法 e2e |
| **P8** | 函数式地基补齐 | 函数式 | **远期规划（决策 6）**：协议化高阶组合子（map/filter/reduce/fold 经协议/impl）；部分应用/柯里化（可选）；不可变/纯函数标注（可选，评估价值） | 全量 pytest + 试用 |
| **P9** | 文档体系收敛 + 收尾 | 全局 | docs/ 单点真理（架构/语法/KNOWN_LIMITS/subsystems）；试用套件扩展；删除临时文档 | 全量 pytest + 文档治理扫描 |

**阶段归属（用户 2026-08-18 拍板后）**：
- **P1-P6 = 当前主线**：P1-P4 为 llm 可调用类 + 总统一性贯通（llm 函数语法彻底删除、统一
  LLMCallable 消费、retry 高阶化、意图一等值、snapshot 意图冻结补齐）；P5-P6 为协议化体系
  地基收尾（prompt 协议族类型类化 + 能力公理收敛 + per-IbClass 协议方法表 + 临时覆层机制）。
- **P7-P8 = 远期规划（决策 6）**：类型理论加固与函数式组合子，登记 PENDING_TASKS，P1-P6
  稳定后重估。
- **P9 = 收尾**。

**阶段依赖**：P1（设计定稿）→ P2（impl 扩展 + 覆层机制，为 P4 llm 类提供壳）→ P3（意图
一等值 + snapshot 冻结补齐，为 P4 消费铺垫）→ P4（核心闭环）。P5/P6 依赖 P2 的 impl/覆层
路径。P7/P8 依赖 P5/P6（协议化地基稳定，远期）。

---

## 五、已决项（用户 2026-08-18 拍板，逐项落实）

> 本文件原 §五 待决项经用户逐项拍板后收敛为已决项。以下为**设计定稿（P1）必须遵守的
> 决策输入**，改动属用户裁定级，需用户拍板。

### 决策 1 —— 内置类型协议方法表落点：**选 B（per-IbClass 协议方法表，系统化重构）**

用户裁定（2026-08-18）：**以彻底且完整的系统化重构为目标，选择 B**。

- 落点：`IbClass` 增协议方法表，`receive` 协议分支前置查表；一举解决 D3（spec.members vs
  vtable 双表不同步）+ D5（能力探测式 getattr 分派）；与"协议一等公民"方向一致。
- 落实阶段：P6（核心落地），但 **P1 设计定稿必须把协议方法表作为全局设计地基之一先行
  定稿**（P2 的覆层机制 / P5 的 prompt 类型类化 / P6 的落地都依赖它的数据形态）。
- 风险控制：改动面大（IbClass 结构 + receive + 水化 + 序列化契约），P6 走独立分支原型验证。

### 决策 2 —— 内置类型行为覆写：**临时覆层机制（新设计约束，最关键）**

用户裁定（2026-08-18）：覆写内置类型相关协议应该是**临时的**，针对用户特定优化/覆写目标。
**如果直接全局覆写不可行，则设计"临时覆层机制"**：

1. **无覆层**：未实现覆写覆层 → 内置类型按默认（原生）行为；
2. **声明不启用**：书写了覆写覆层但**未启用相关 flag（不在相关用户作用域）** → 常规程序段
   仍按默认行为；
3. **启用才生效**：只有用户明确需要覆写行为的作用域启用用户自定义 impl → 覆层生效；
4. **告警**：基于"覆层存在/启用状态"设计告警（未启用时的存在提示、启用时的行为记录）。

**设计含义（P1 设计定稿须细化）**：
- 覆层是**作用域化/按需启用**的行为改写，不是全局永久覆写（区别于 Rust 全局 trait impl）。
- 数据形态（与决策 1 B 结合）：覆层作为 per-IbClass 协议方法表上的**影子/备用条目**，
  默认不参与分派，启用时才成为分派候选（优先级高于原生 vtable 方法）。
- 与 D6（内置 spec 不可持久化）天然互补：覆层默认不注入、运行期按需注册，规避"编译期
  注入、运行期失忆"问题。
- 语法/AST/语义落点（P2）：覆层如何声明（`impl P for int` 变体）、如何启用（作用域 flag /
  调用点声明）、如何作用域化、如何告警——P1 定稿给出形态，P2 落地。

### 决策 3 —— snapshot 意图快照文档漂移：**按文档语义补齐（方向 1）**

用户裁定（2026-08-18）：认可 lambda/snapshot 原初设计意图——**lambda = 引用捕获（不保证
时不变/无状态）；snapshot = 冻结（保证时不变/无状态/可重入）**；其余细节交我自主。

- 落实：P3——把"意图冻结"并入 snapshot 的"值捕获"策略，**纯 snapshot lambda 也冻结意图**
  （当前仅行为体 fork，D8）。属 IBCI 自身设计缺陷修复，自主推进 + 详尽记录变化前后。

### 决策 4 —— llm 函数语法（`llm ... llmend`）：**彻底删除，不保留语法糖**

用户裁定（2026-08-18）：**彻底删除 `llm ... llmend` 语法，彻底转向统一 llm 可调用类**。

- 落实：P1 定稿迁移策略（`__sys__/__user__/__llmretry__` 语义映射到 LLMCallable 协议方法族），
  P4 删除语法 + **全量迁移现有示例/试用/测试**（破坏性变更，属用户授权范围）。
- 注意：这是"真删除"，不是语法糖映射（推翻原 §五 推荐后者）。迁移后 `llm ... llmend` 语法
  不再存在，用户面统一为 llm 可调用类。

### 决策 5 —— retry 收敛边界：**帧机制保留 + 语法/策略高阶化（推荐 a）**

用户裁定（2026-08-18）：按推荐执行。

- 落实：P4——`LLMExceptFrame` 保留作重试执行基质；`retry`/`llmretry` 收敛为"对可调用实例的
  高阶包装语法糖"（声明快照策略 + 重试策略 + hint）；llm 派生类可自定 `__retry__` 协议方法；
  行为语句默认 retry 由帧机制提供。

### 决策 6 —— P7/P8 排期：**本主线 P1-P6，P7/P8 远期规划（推荐 b）**

用户裁定（2026-08-18）：按推荐执行。

- 落实：P7（类型理论加固）/P8（函数式组合子）登记 PENDING_TASKS 远期（与档 A 缓存/JIT/隔离/
  反射同等待遇），P1-P6 稳定后重估。五大地基"完整改造"最终目标包含它们，P1-P6 落地前不启动。

---

## 六、下一 session 交接（P1 设计定稿开工输入）

**开工起点**：`NEXT_STEPS.md` 下一步候选 #1（P1 设计定稿）。**本文件 §一-§五 为唯一调研与
决策权威**；`_llm_callable_redesign.md` 为方法族草案（§三.1 LLMCallable 协议方法族）承接。

> **P1 设计定稿已完成**：`tasks_docs/_five_foundation_P1_design.md`（§一-§九 定稿全部 7 项
> 开工输入 + 用户追加裁定：llm 函数语法/旧机制彻底删除、不兼容不包袱）。本文件 §一-§五
> 决策正文**不修改**（用户拍板权威）；P1 定稿在其基础上深化落地。后续 P2-P6 实现以
> `_five_foundation_P1_design.md` 为设计规格、本文件为决策/调研权威。

**P1 设计定稿必须覆盖的决策输入**（缺一不可）：
1. `LLMCallable` 协议方法族定稿（方法名/签名/与 LLMCallRequest 承载/意图改写 `__intent__`/
   retry `__retry__`）；
2. llm 函数语法（`llm ... llmend`）彻底删除的迁移映射表（`__sys__/__user__/__llmretry__` →
   LLMCallable 方法）+ 全量迁移清单（examples/trials/tests）；
3. **内置类型临时覆层机制形态定稿（决策 2）**：声明语法、启用 flag 的作用域语义、与
   per-IbClass 协议方法表（决策 1 B）的数据形态、告警设计；
4. per-IbClass 协议方法表的全局数据形态（决策 1 B）作为 P2/P5/P6 的共享地基；
5. snapshot 意图冻结补齐语义（决策 3）并入捕获策略参数化设计（交接点 2 结论）；
6. retry 高阶化边界（决策 5：帧机制保留 + 语法/策略高阶化）；
7. 破坏面评估 + 分阶段迁移路径（P2-P6 顺序与验证门，§四）。

**待下 session 自主裁定（无需用户）**：P1 内的机制形态细节、P2-P6 实现顺序、告警文案、
测试补丁——按"自主推进偏好 + 工作模式定论"执行，详尽记录决策依据。
