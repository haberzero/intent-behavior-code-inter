# IBC-Inter 待实现任务清单

> 记录中长期未来工作。近期任务见 `docs/NEXT_STEPS.md`，已完成工作见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-05-06（G3 / H5 / H6 / H7 / OI-4 已完成项归档至 COMPLETED.md；新增 §3.9 类型窄化任务；TypeRef §13 标注为高优先级；llmexcept vs try/except 设计说明补充至 §十）

---

## 一、动态宿主（DynamicHost）相关

### 1.1 子解释器插件注册 [PENDING]
**任务**：允许子解释器独立注册自己的插件。

**搁置原因**：当前阶段不允许子解释器独立注册插件，所有插件应从主解释器继承。

**未来方案**：定义插件注册接口、实现运行时插件加载机制、添加隔离策略配置项。

---

### 1.2 HOST 插件 breakpoint 接口 [PENDING]
**任务**：为 HOST 插件添加 breakpoint 相关接口（现场保存/恢复/回溯，非 GDB 式断点）。

**搁置原因**：DynamicHost 当前最小目标不含断点功能，需先完成内核稳定工作。

---

## 二、公理化相关


### 2.2 Intent Stack 不可变性约束 [PENDING]
**任务**：实现 Intent Stack 不可变性约束。

**搁置原因**：依赖 Intent 公理化完成；Intent Stack 语义尚有待澄清的设计要点。

---

### 2.3 符号同步深拷贝 [PENDING]
**任务**：修复 `_sync_variables_from()` 直接传递 symbol 引用的问题。

**搁置原因**：变量继承已禁用（`inherit_variables=False`），当前不触发。**位置**：`interpreter.py:93-99`

---

### 2.4 ParserCapability LLM 提示词片段扩展 [PENDING]
**任务**：扩展 `ParserCapability` 接口，添加 `get_llm_prompt_fragment()` 方法，替代 `ibci_ai` 中硬编码的 `_return_type_prompts`，使每个 Axiom 能自主声明其对应的 LLM 输出格式提示词。

**涉及文件**：`core/kernel/axioms/protocols.py`、`core/kernel/axioms/primitives.py`、`core/runtime/interpreter/llm_executor.py`

---

### 2.5 Axiom Capability 内部委托对象模式重构 [FUTURE / INDEPENDENT]

**任务**：将 `primitives.py` 中所有 Axiom 类从"自身实现 Capability Protocol"的多继承模式，改为"持有内部 Capability 委托对象"的委托模式（`DeferredCallCapability` / `BehaviorCallCapability` 已采用此独立类模式）。

**目标模式**：
```python
class _IntOperatorCapability:           # 独立私有类
    def resolve_operation_type_name(self, op, other): ...

class IntAxiom(BaseAxiom):              # 只继承 BaseAxiom，无 Protocol 多继承
    _op_cap = _IntOperatorCapability()
    def get_operator_capability(self): return self._op_cap
```

**完成效果**：所有 14 个 Axiom 类 MRO 退化为单继承；`primitives.py` 中 48 处 Protocol 多继承链条全部消除；对外 API 零破坏（调用方通过 `get_xxx_capability()` 访问）。

**工程量**：需新增约 40-50 个私有 Capability 类，约为 Impl 类 Protocol 清理工作的 3-4 倍。需同步拆分 `primitives.py`（届时约 2000+ 行）。

**搁置原因**：无对应 Bug；Capability Protocol 均无 `@runtime_checkable` 修饰，不存在 Python 3.12 isinstance 风险；为纯架构美观性改进，现阶段无触发必要性。

**建议触发时机**：`primitives.py` 因内容增加需强制拆分文件时，或 Capability 逻辑出现跨 Axiom 复用需求时。

**涉及文件**：`core/kernel/axioms/primitives.py`

---

## 三、类型系统

### 3.1 禁止 auto 向明确类型隐式赋值 [PENDING]
**任务**：实现 auto 类型约束机制，禁止 auto 向明确类型隐式赋值。

**搁置原因**：最低优先级，允许当前瑕疵存在。**方向**：在语义分析器的类型检查阶段加强约束。

---

### 3.2 ib_type_mapping 完善 [PENDING]
**任务**：完善 `runtime/objects/ib_type_mapping.py` 的类型映射实现（当前 `_IB_TYPE_TO_CLASS` 为空字典）。

**搁置原因**：不影响核心功能，优先级低。

---

### 3.3 BooleanCapability 接口 [PENDING]
**任务**：在语义分析器的条件驱动 for 循环类型校验中（`semantic_analyzer.py` 约第 853 行），引入 `BooleanCapability` 接口，替代现有的 `is_dynamic() or is_behavior() or iter_type.name == "bool"` 特例判断。

**当前状态**：该分支逻辑直接 `pass`，无实质约束；现有条件足以覆盖已知场景。

**搁置原因**：不影响当前功能正确性；需要在 `core/kernel/axioms/protocols.py` 中新增 `BooleanCapability` 协议并在所有布尔类型 Axiom 中实现。

---

### 3.4 泛型参数传播（下标访问类型推断）✅ **已完成（2026-05-02 G3）**

`resolve_member` 已特化 `list[T].__getitem__→T`；`resolve_subscript` 对 `ListSpec`/`DictSpec` 直接读取 `element_type_name`/`value_type_name`。详见 `docs/COMPLETED.md §23.3`。

---

### 3.5 泛型协变规则 ✅ **已完成（2026-05-02 G3）**

`SpecRegistry.is_assignable` 中 `list[T]` isa `list` 的协变逻辑已落地（通过 `get_base_name()` 统一能力查询路径）。详见 `docs/COMPLETED.md §23.3`。

---

### 3.6 嵌套泛型推断 ✅ **已完成（2026-05-02 G3）**

`resolve_specialization` 改用 `a.name`（完整名称）修复 `list[list[int]]` 缓存键计算错误。详见 `docs/COMPLETED.md §23.3`。

---

### 3.7 泛型特化 axiom 自动引导 ✅ **已完成（2026-05-02 G1/G3，OI-4 关闭）**

`resolve_specialization` 加入 early-cache hit 逻辑；G3 修复 `candidate_key` 计算。详见 `docs/COMPLETED.md §23.3`，`docs/OPEN_ISSUES.md OI-4`。

---

### 3.9 `except X as e:` 类型窄化 [PENDING]

**任务**：在语义分析器 `visit_IbExceptHandler` 中，将 `except X as e:` 捕获变量 `e` 的编译期类型从固定的 `Exception` 窄化为 `X`（捕获类型）。

**当前状态**：`e` 始终被声明为 `Exception` 类型，访问 `X` 专属字段需通过 `(X)e` 显式强转（详见 `KNOWN_LIMITS.md §二`）。

**实现方向**：
1. `visit_IbExceptHandler` 中 `self.visit(node.type)` 已返回解析后的 spec；当前该返回值被丢弃，直接使用 `Exception` spec。
2. 修复：将 `self.visit(node.type)` 的返回值作为 `exc_type`，回退到 `Exception` 仅当 `node.type is None`（裸 `except:`）。
3. 复杂情形：`except (A, B) as e:` 中 `e` 类型为公共父类（通常是 `Exception` 或 `LLMError`），需检测 tuple 类型并回退为最近公共祖先 spec。

**影响文件**：`core/compiler/semantic/passes/semantic_analyzer.py`（`visit_IbExceptHandler`，约 1398 行）。

**工程量**：小（核心修改约 5 行），tuple-except 的公共父类推导略复杂（可先支持单类型，tuple 类型保持 `Exception` 回退）。

---

**任务**：考虑支持 `tuple[T1, T2, ...]` 语法，为固定结构的多值返回提供类型安全。当前元组元素访问始终返回 `any`。详见 `docs/KNOWN_LIMITS.md §16.5`。

---

## 四、语法功能

### 4.1 (str n) @~ ... ~ 语法完善 [PENDING]
**任务**：验证并完善 callable 闭包参数传递语法，明确其设计语义。

**搁置原因**：手册描述的语法需确认完整实现，闭包参数传递机制需更明确的设计。

---

### 4.2 llmretry 后缀语法澄清 [PENDING]
**任务**：明确 llmretry 后缀的当前实现状态与文档描述是否一致。

**搁置原因**：当前实现为声明式 llmexcept + retry，手册描述的单行后缀语法已被重构。

---


### 4.4 fn/callable 类型系统后续改进 [PENDING]

以下项目是 `fn` / callable / lambda 类型系统在 fn 类型系统重设计落地后的已知后续工作。详细设计背景见 `docs/FUNC_DESIGN_NOTES.md`，当前限制见 `docs/KNOWN_LIMITS.md §三`。

#### 4.4.1 `func[sig]` 泛型类型标注

支持带签名约束的 `func` 类型（参数签名编译期验证）：
```ibci
func apply_typed(func[int -> int] fn, int x) -> int:
    return fn(x)
```

#### 4.4.2 轻量泛型 `<T>`

支持泛型高阶函数类型传播，使 `fn` 签名能在调用链中真正传递类型。

#### 4.4.3 高阶函数编译期类型推断

引入泛型参数使 `auto` 返回类型能通过 `func` 型参数传递（当前退化为 `any`）。

#### 4.4.4 lambda / snapshot 剩余语义缺陷

- **类型签名传播弱**：`fn f = lambda(int x): EXPR` 中 `f` 的类型推断不传播参数/返回签名
- **递归 lambda 不支持**：lambda 无法引用自身
- **`snapshot` 线程安全**：snapshot 首次调用后缓存，多解释器并发引入后存在潜在竞态，目前依赖使用约定

---

## 五、intent_context 完整 OOP 化（已记录，待跟进）

> MVP 已落地（2026-04-19）：`intent_context` 可实例化，支持 `push/pop/fork/resolve/merge/clear` 方法。以下为用户明确要求的、尚未实现的完整功能。

### 5.1 将 intent_context 实例作为函数调用参数传递 [PARTIAL ✅ / PENDING]

**已实现（2026-04-19）**：用户可以将 `intent_context` 实例作为**普通参数**传递给函数，然后在函数内部调用 `intent_context.use(ctx)` 将其设置为当前作用域的意图上下文：

```ibci
func process_with_custom_ctx(intent_context ctx):
    intent_context.use(ctx)    # 用传入的上下文替换当前作用域（fork 拷贝，不共享引用）
    str r = @~ MOCK ~          # 只见 ctx 中的意图
    return r

intent_context my_ctx = intent_context()
my_ctx.push("简洁明了")
str result = process_with_custom_ctx(my_ctx)
```

**待实现（未来工作）**：
- **隐式绑定语法**：函数声明中以特殊方式声明 `intent_context` 参数，运行时自动将其绑定到当前帧的 `_intent_ctx`（而非用户手动调用 `use(ctx)`）
- **语法糖**：调用方 `my_func(@ctx my_ctx_var)` 使 `my_ctx_var` 自动成为函数作用域的意图上下文（无需函数体内显式 `use()`）
- **运行时绑定路径**：若有显式 `intent_context` 实参，则替换为该实参所包装的 `IbIntentContext`，而非 fork 调用者上下文

**搁置原因**：需要编译器和语义分析器支持意图上下文参数的自动绑定；当前通过 `intent_context.use(ctx)` 已可手动实现等效效果，此任务为语法层的简化。

---


### 5.3 intent_context 作为函数参数类型 [PENDING]

**需求**：函数可以声明 `intent_context` 类型的参数，允许调用者传入自定义意图上下文对象，函数内直接操作该对象（push/pop/etc.），影响此次调用下的 LLM 行为。

```ibci
func generate_text(intent_context ctx, str prompt) -> str:
    ctx.push("保持简洁")
    str result = @~ $prompt ~
    return result
```

**搁置原因**：需要语义分析器对 intent_context 参数的特殊处理：绑定参数到当前帧的 `_intent_ctx`；与 5.1 协同设计。

---

### 5.4 intent_context 显式作为函数作用域默认上下文 [PENDING]

**需求**：在函数体内可以显式声明一个 `intent_context` 变量作为"本函数的意图上下文"，所有 `@+`/`@-` 操作作用在该变量上，而非隐式的 `rt_context._intent_ctx`。

```ibci
func process():
    intent_context my_ctx = intent_context()
    # 以下 @+ 操作作用在 my_ctx 上（而非隐式上下文）
    @+ "格式要求"  # → my_ctx.push(...)
    str r = @~ MOCK:test ~
```

**搁置原因**：这需要对意图操作的作用目标（隐式 vs 显式）进行语法区分，属于较大的语言设计变更。

---

### 5.5 更复杂的意图上下文操作 [VISION]

**需求（远期）**：
- intent_context 实例之间的合并策略（`merge_with_priority()`, `intersect()`, `diff()`）
- intent_context 的序列化 / 反序列化（JSON 快照，用于跨进程/持久化场景）
- intent_context 的"冻结"（freeze）模式：创建后不可修改，适合在多个函数间共享

---

## 六、其他功能

### 6.1 LLM 输出持久化 [PENDING]
**任务**：AI 插件支持将 LLM 输出保存到文件。

**搁置原因**：与 IssueTracker 持久化机制配合，属于扩展性功能。

---

### 6.2 子解释器变量深拷贝隔离 [PENDING]
**任务**：实现 `RuntimeContext.inject_variable()` 方法（变量继承已禁用，当前不触发）。

---

## 七、明确排除的设计

| 排除项 | 理由 |
|--------|------|
| 进程级隔离 | 实例级隔离已足够 |
| 核心级 IPC | 通过外部 file 插件实现 |
| GDB 式断点 | DynamicHost 断点是现场保存/恢复/回溯 |
| hot_reload_pools | 违反解释器不修改代码原则 |
| generate_and_run | 动态生成 IBCI 应由显式 IBCI 生成器完成 |
| `LLMExecutorImpl` 作为可替换插件 | 它是语言语义的一部分；provider 可配置，执行接口不可替换 |

---

## 八、架构与基础设施

### 8.1 ImmutableArtifact `__deepcopy__` [PENDING]
**任务**：添加 `__deepcopy__` 方法（不可变对象，深拷贝返回自身）。

**搁置原因**：当前行为可接受，不影响核心功能。

---

### 8.2 MetadataRegistry 双轨统一 [PENDING]
**任务**：解决 `Engine.__init__()` 初始化的 MetadataRegistry（轨 A，内置类型公理）与 `HostInterface` 各自创建的实例（轨 B，插件元数据）并行问题。

**搁置原因**：两轨各有各的查询路径，当前不影响功能。

---

## 九、插件系统

### 插件显式引入完整实现

**任务**：严格实现"必须显式 import 才能使用"原则（基础实现已完成：`kind` 字段区分 `method_module`/`type_module`；`Engine._ensure_plugins_discovered()` 懒加载，首次 `compile()`/`check()` 时执行一次插件发现）。

**待实现**：
- 明确区分"方法模块"（提供函数调用）和"类型模块"（提供原生类型），完善 `kind` 字段语义规范。
- Scheduler 符号注入逻辑，标记外部模块符号（区分内置符号与 import 注入符号）。

**文件**：`core/engine.py`（`_ensure_plugins_discovered`）、`core/compiler/semantic/passes/prelude.py`、所有插件 `_spec.py`

---

### 9.2 模块符号去重机制 [PENDING]
**任务**：解决外部模块符号（`import ai` 注入 MODULE 符号 `"ai"`）与用户定义符号（`class ai`）的命名冲突问题。

**根因**：`import ai` 在 Pass 1 之前注入 MODULE 符号，与用户 `class ai` 在 Pass 1 中收集的 CLASS 符号冲突。

---

## 十、llmexcept / retry 机制后续

### 10.0 llmexcept 与 try/except 的设计区别（架构说明）

**`llmexcept`（影子执行驱动模式）**：
- **不是异常驱动**：LLM 不确定性通过 `last_llm_result` 信号通道（`LLMResult.is_uncertain` 标志位）传递，不抛出任何 Python 异常。
- **快照-恢复模型**：`LLMExceptFrame` 在进入保护块时保存变量/意图栈/循环上下文快照，每次 retry 前自动 `restore_snapshot()`，保证 LLM 看到一致的输入状态。
- **重试循环**：`should_continue_retrying()` 驱动 while 循环；`retry "hint"` 语句设置 `frame.should_retry = True`；重试耗尽时抛出 `ThrownException(LLMRetryExhaustedError)`。
- **设计用途**：专为 LLM 模糊性（输出解析失败）设计，提供状态回滚 + 提示词优化 + 有限重试的完整语义。

**`try/except`（异常驱动模式）**：
- **标准异常捕获**：`ThrownException`（包装 IBCI 异常对象）通过 generator `try/except` 在 `vm_handle_IbTry` 中捕获。
- **无快照、无重试**：body 执行一次；匹配的 `except` handler 接管；没有状态回滚机制。
- **设计用途**：用于捕获明确语义的异常（包括 `LLMRetryExhaustedError`、`LLMParseError`、用户自定义异常、`raise` 显式抛出）；与 Python try/except 语义完全对齐。

**两者组合使用（典型模式）**：
```ibci
try:
    str r = @~ 生成摘要 ~ llmexcept "请输出纯文本":
        retry "格式要求: 不要使用 Markdown"
except LLMRetryExhaustedError as e:
    str r = "（摘要生成失败）"
```
- `llmexcept` 处理 LLM 不确定性（内层，有重试）
- `try/except` 捕获 retry 耗尽后的 `LLMRetryExhaustedError`（外层，最终兜底）

---

### 10.1 重试策略配置扩展 [PENDING]
**任务**：在固定次数重试（`ai.set_retry(n)`）基础上，支持指数退避（Exponential Backoff）和条件重试（基于错误类型）。

**文件**：`ibci_modules/ibci_ai/core.py`、`core/runtime/interpreter/handlers/stmt_handler.py`

---

### 10.2 LLMCallError 触发路径接入或裁剪 [PENDING]
**任务**：决策并落地 `LLMCallError` 的最终定位（详见 `OPEN_ISSUES.md OI-7`）。

**背景**：E1-E5（2026-04-30）注册了完整的 `LLMCallError` 公理 / spec / 工厂方法，含独立字段
`provider_error`，但 `llm_executor._call_llm()` 中并无任何代码路径调用 `make_llm_call_error()` 自动抛出。
所有 provider 层 Python 异常一律 `str(e)` 后转为 `error_msg`，进入"不确定 → llmexcept 重试"通道。
后果：永久性失败（如 401 认证、配额耗尽）会消耗完所有 retry 后以 `LLMRetryExhaustedError` 收尾，
而非语义更准确的 `LLMCallError`，且 `provider_error` 字段无机会被填充。

**两个候选方向**：
1. **接入触发路径**：在 `_call_llm` 中按 Python 异常类型分类——永久性错误直接
   `raise ThrownException(registry.make_llm_call_error(message=..., provider_error=...))` 跳过 retry；
   瞬时网络错误保持现有路径。需要建立"哪些异常视为永久性"的分类策略（按 provider SDK 异常类型 / HTTP 状态码）。
2. **裁剪为用户层类型**：保持 `LLMCallError` 仅供用户手动 raise，明确其语义为"业务层用于上报 provider 失败的预定义异常类型"。
   这种情况下，应在 `IBCI_SYNTAX_REFERENCE.md §4.6.1` 注释（已加注：当前 VM 不自动抛出）的基础上保留现状。

**文件**：
- `core/runtime/interpreter/llm_executor.py`（`_call_llm`，触发点）
- `core/kernel/registry.py`（`make_llm_call_error`，工厂已就位）
- `core/kernel/axioms/primitives.py`（`LLMCallErrorAxiom`，公理已就位）

---



## 十一、代码健康（审计遗留）

### 11.1 意图标签解析迁移到 Lexer
**问题**：`statement.py:278` 的 `#tag` 解析使用 inline `import re` + 正则表达式在 parser 层处理，属于词法层职责被推后到语法层。未来对 tag 做语义分析（如检查 `@- #tag` 中 tag 是否已定义）时会比较困难。

**文件**：`core/compiler/parser/components/statement.py`（约第 278-289 行）

---

### 11.2 engine.py / service.py "vibe" 妥协标注（部分已修复）
**问题**：多处被标注为"智能体快速 vibe 实现，未经严格审查"：
- ~~`engine.py:136`：强制向 service_context 回写 orchestrator（双向引用注入）~~ **[已修复]**：改用 `ServiceContextImpl.set_orchestrator()` 标准注入方法（见 COMPLETED.md §4.16）
- ~~`interpreter.py:229`：`kwargs.get('orchestrator', ...)` 却没有 `**kwargs` 参数~~ **[已修复]**（见 COMPLETED.md §4.16）
- `service.py:173`：`host_run()` 返回值简化为布尔值，隐藏实际结果（等待多返回值语法完善后修复，见 §11.3）
- `rt_scheduler.py:40-44`：`_resolve_builtin_path()` 使用 `ibci_modules.__file__` 动态发现路径（合理但可用常量替代，低优先级）
- `scheduler.py:81`：`compile_to_artifact_dict()` 方法设计合理性存疑

**文件**：`core/runtime/host/service.py`、`core/runtime/rt_scheduler.py`、`core/compiler/scheduler.py`

---

### 11.3 instance_id 默认值碰撞风险
**问题**：`interpreter.py:108` `instance_id: str = "main"` 默认值可能导致多解释器实例 ID 碰撞。当前有 `instance_id or f"inst_{id(self)}"` fallback 保护，但 `"main"` 作为默认值仍是潜在隐患。

**文件**：`core/runtime/interpreter/interpreter.py`

---

### 11.4 LLMExceptFrame 重试历史追踪
**问题**：`reset_for_retry()` 在每次重试时清除 `last_error`，目前重试历史不保留。若需要在 llmexcept body 内查询历次重试的错误摘要（用于更精细的提示词调整），需要给 `LLMExceptFrame` 添加 `error_history: List` 字段，并在 `reset_for_retry()` 中追加而非清除。

**文件**：`core/runtime/interpreter/llm_except_frame.py`（`reset_for_retry()` + `LLMExceptFrame`）

---

### 11.5 LLMExceptFrameStack 最大嵌套深度
**问题**：当前 `LLMExceptFrameStack` 无最大嵌套深度检查。深度嵌套的 llmexcept 块（如循环内多层 llmexcept）在极端情况下可能无界增长。通常不会触发，但防御性限制有益于可观测性。

**文件**：`core/runtime/interpreter/llm_except_frame.py`（`LLMExceptFrameStack.push()`）

---

### 11.6 ibci_idbg 暴露 side_table 接口
**问题**：`ibci_modules/ibci_idbg/core.py:267` 有 `# TODO: 需要内核暴露 side_table 接口后实现`，是 idbg 模块的能力缺口——调试器无法直接访问编译器侧表（`node_to_symbol`、`node_to_type` 等），限制了调试信息的精度。

**建议**：通过 `KernelRegistry` 或 `IExecutionContext` 新增 `get_side_table(key, uid)` 公共接口，使 idbg 无需持有内部 `execution_context` 引用即可访问。

**文件**：`ibci_modules/ibci_idbg/core.py`、`core/runtime/interfaces.py`（扩展接口）

---

### 11.7 SpecRegistry.resolve_specialization 无缓存 ✅ **已完成（2026-05-02 G1/G3，OI-4 关闭）**

详见 `docs/COMPLETED.md §23.3`，`docs/OPEN_ISSUES.md OI-4`。

---

### 11.8 ExpressionAnalyzer ghost class 清理 ✅ **已完成（2026-05-02 H5）**

`expression_analyzer.py` 及全部引用已删除。详见 `docs/COMPLETED.md §二十二（H5）`。

---

### 11.9 `_pending_intents` 动态属性信道形式化 ✅ **已完成（2026-05-02 H6）**

`_pending_intents` 幽灵管道已完全删除（`context.py / component.py / declaration.py`）。详见 `docs/COMPLETED.md §二十二（H6）`。

---

### 11.10 `SemanticAnalyzer.visit_IbAssign` 复杂度降低 ✅ **已完成（2026-05-02 H7）**

`visit_IbAssign` 已拆分为 10+ 职责单一私有子函数，主方法约 32 行。详见 `docs/COMPLETED.md §二十二（H7）`。

---

## 十二、远期架构目标

### 12.3 host.run_isolated() 返回值改进 [VISION]
**当前**：返回简化布尔值。**目标**：多返回值/元组解包语法完整实现后，改为 `tuple(exit_code: int, result: str|dict)`。

---

### 12.4 ReceiveMode 枚举演进 [VISION]
**当前**：`deferred_mode: str` 侧表（`'lambda'`/`'snapshot'`/`None`）。**目标**：迁移至 `ReceiveMode(IMMEDIATE / LAMBDA / SNAPSHOT)` 枚举，替代字符串，支持更严格的类型约束。

---

*本文档记录中长期未来工作。近期任务见 `docs/NEXT_STEPS.md`，已完成工作见 `docs/COMPLETED.md`。*

---

## 十三、类型系统长期演进（TypeRef 重构）【高优先级】

### 13.1 类型系统现状分析 [VISION]

**背景**：当前 `IbSpec.name` 字段同时承担了两个职责：
1. **注册表键**（唯一标识，含泛型参数），如 `"list[int]"`、`"dict[str,int]"`
2. **语义分类标签**（类型族归属），如 `"list"`、`"dict"`

泛型出现后这两个职责产生冲突：`"list[int]".name == "list[int]"` 而非 `"list"`，导致所有直接比较 `.name` 的语义检查对泛型失效（典型案例：`in`/`not in` 运算符的容器类型检查）。

**近期补丁方案（已实施，方案 A）**：
- 所有语义分类检查统一使用 `spec.get_base_name()` 而非 `spec.name`
- 新增 `SpecRegistry.get_base_spec(spec)` 工具方法，将泛型专化 spec 解析回基础 spec
- 约定：`.name` 仅用于 registry key 和 error message；`.get_base_name()` 用于能力查询和语义分类；`isinstance(spec, ListSpec/DictSpec/...)` 用于结构性能力判断

**需要被修复的散布调用点**（已知）：
- `visit_IbCompare`：`.name not in ("str","list","dict","tuple","any")` → 已修复 → `get_base_name()`
- `visit_IbFor`：`iter_type.name != "bool"` → 已修复 → `get_base_name()`
- 其他 `.name` 比较：仅用于 error message 显示，可保留

### 13.2 长期目标：引入 TypeRef 统一类型引用 [VISION]

**设计目标**：实现以下所有"类型内容"的逻辑正交性和设计统一性：

| 类型维度 | 当前表示 | TypeRef 目标表示 |
|---------|---------|----------------|
| 变量本身的类型 | `sym.spec: IbSpec` | `sym.type_ref: TypeRef` |
| 函数返回值类型 | `FuncSpec.return_type_name: str` | `FuncSpec.return_type: TypeRef` |
| 泛型容器自身类型 | `ListSpec.name = "list[int]"` | `TypeRef(base="list", args=[TypeRef("int")])` |
| 泛型容器元素类型 | `ListSpec.element_type_name: str` | `TypeRef.args[0]` |
| 泛型容器嵌套类型 | 无法表达 | `TypeRef(args=[TypeRef(args=[...])])` |
| 泛型下标成员类型 | `resolve_subscript()` 返回字符串 | `TypeRef.args[0]` |
| 类成员类型 | `MemberSpec.type_name: str` | `MemberSpec.type_ref: TypeRef` |
| 迭代器元素类型 | `resolve_iter_element()` 返回字符串 | `TypeRef.args[0]` |
| 表达式类型 | side_table `node_to_type: IbSpec` | side_table `node_to_type: TypeRef` |

**建议的 TypeRef 设计**：
```python
@dataclass(frozen=True)
class TypeRef:
    base_name: str                          # "list", "dict", "int"
    args: Tuple["TypeRef", ...] = ()        # 泛型参数
    module: Optional[str] = None
    nullable: bool = False

    @property
    def canonical_name(self) -> str:        # 注册表键，兼容 IbSpec.name
        if self.args:
            return f"{self.base_name}[{','.join(a.canonical_name for a in self.args)}]"
        return self.base_name

    @property
    def family_name(self) -> str:           # 语义分类，等价于 get_base_name()
        return self.base_name
```

**实施前提**：
- 需与 VM/CPS 调度循环重构一并规划（架构层二）
- 需要修改所有 spec 字段（`FuncSpec`, `ListSpec`, `DictSpec`, `MemberSpec` 等）和序列化层
- 成本极高，应在下一代架构升级时引入，不宜打补丁式渐进

**当前状态**：方案 A（`get_base_name()` + `get_base_spec()`）已落地，为 TypeRef 重构保留接口兼容性。TypeRef 重构是下一代 VM 和类型系统主线的基础性工程，**优先级：高**（VM 完善 + 类型系统深化的主线前提）。

---

*本文档记录中长期未来工作。近期任务见 `docs/NEXT_STEPS.md`，已完成工作见 `docs/COMPLETED.md`。*
