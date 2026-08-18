# 临时设计文档：装饰壳体系 + llm 可调用类（体系化调研/可行性/规划）

> **性质**：临时任务控制文档（设计阶段）。落地后按 `tasks_docs/GOVERNANCE.md` 收敛到 `docs/`，
> 本文件删除（git 承载历史）。**本任务不是代码编写任务**——本阶段交付"调研分析 + 可行性确认 +
> 执行规划"。

---

## 〇、任务定位

用户（2026-08-18）提出两大体系化设想的调研/可行性/规划请求：

1. **装饰壳体系**：把"协议/impl（trait 机制）"从"类型级"扩展到"函数实例级"——对 fn 实例进行
   包装，使任意可调用实例能被嵌入行为描述语句 / 意图注释等 IBCI 核心机制，不再局限于
   `__prompt__` 协议族。参考 Rust 的 trait + impl + 泛型 bound。
2. **llm 可调用类替代 llm 函数**：彻底抛弃 `llm ... llmend` 语法，构建"可调用的 llm 类"
   （类似 Python 可调用类 `__call__`），并让 retry / 意图处理高阶化。

本文件为**事实调查 + 割裂点映射 + 可行性确认 + 设计骨架 + 执行规划**。

---

## 一、现状事实（全部经代码实证 / 探针验证）

### 1.1 协议体系：地基已经存在

- **用户协议语法已落地**（`docs/syntax/06_oop.md` §6.8，KNOWN_LIMITS §26）：
  `protocol P:` / `class C implements P` / `impl P for T:`（可带方法体补充缺失方法）。
- **泛型 bound 已实现且编译期生效**（实证 `T: Greeter` 拦截不满足类型）。
- **协议注册表**（`core/kernel/protocol.py`）：`ProtocolRegistry` + 内置协议
  `callable/iterable/subscriptable/operator/attribute/converter/parser/to_prompt/
  from_prompt/validate_prompt/output_hint/payload_prompt/snapshotable`；
  `SpecRegistry.satisfies_protocol` 为唯一判定入口。
- **impl 限制（关键边界）**：① 目标须为本模块用户类（跨模块不支持）；② **泛型类目标不支持**；
  ③ **内置类型目标不支持**（实证：`impl Describable for fn_callable` →
  `SEM_TYPE_MISMATCH: impl target 'fn_callable' is not a known class`）；④ 方法名冲突报错。
  → **用户无法直接为"函数实例类型"声明壳。**

### 1.2 LLM 调用链：统一消息体已经相当好

- `LLMCallRequest`（`core/base/llm_protocol/llm_call.py`）：`user_prompt` +
  `prompt_slots`（`PromptSlot` 语义槽 kind）+ `intents`（`IntentBlock` 三层）+ `output_contract`
  （`OutputContract`）+ `target_model` + `message_history` + `thinking_mode`。
  供应商无关，**不**含任何供应商专有字段。
- `LLMProvider` 契约：`call/stream/get_retry/is_auto_intent_injection_enabled/
  get_current_call_info/probe`；推荐 provider（`recommended.py`）把语义槽组装为系统提示词，
  可被自定义 provider 覆盖（F4 已支持 `ai.set_provider` 宿主绑定注册）。
- **内核与 provider 已解耦**：内核只产结构化语义槽，拼装形态归 provider。

### 1.3 函数与 LLM 函数：运行时已统一

- 普通函数与 LLM 函数共用 `IbUserFunction` + `_vm_call_function`（`callable_kind` 区分），
  无独立 `IbLLMFunction` 类。
- LLM 函数已是第一等函数值（T09-N3 实证：`fn f = 问数; f()` 可用）。
- 类内 LLM 方法（N7）、impl 内 LLM 方法（N1）实证可用。
- 用户可调用类 `__call__` 协议已支持（`_UserCallDrive` CPS 驱动，深递归恒定）。

### 1.4 割裂点（全部实证）

| # | 割裂 | 实证 |
|---|------|------|
| G1 | 函数实例插值行为语句 → 只渲染占位符 `<FnCallable(lambda) node_...>` | 探针 t1 |
| G2 | 函数实例放入意图注释 → 无有意义嵌入（$fn 段未求值渲染） | 探针 t2/t5/t8/t9（意图栈存 AST 节点对象） |
| G3 | llm 函数仍用 `__sys__`/`__user__` 段 → 语言层直接要求底层请求格式，与 LLMCallRequest 语义槽模型割裂 | `_llm_function.py` 实证（`user_sys` 槽 + `user_prompt`） |
| G4 | `ai.stream_call/stream_channel` 仍吃 `(sys_prompt, user_prompt)` 字符串 → 同一割裂 | `ai/core.py` 实证 |
| G5 | 意图栈本质是字符串栈（`IbIntent.content: str`），不是一等值栈 → 用户对象/函数实例不能作为意图值 | `intent.py` 实证 |
| G6 | `__prompt__` 协议族是"魔法 dunder"，散落多层手工实现（`PromptRenderer` 已统一文本侧，但协议判定仍靠方法名字符串） | LANGUAGE_DESIGN_EVOLUTION §1.2 |
| G7 | 能力公理 `has_*_cap` 仍是封闭 flag 集合（用户不能声明新能力） | `axioms/protocols.py` |

### 1.5 既有体系化演进评估（前身文档）

`docs/LANGUAGE_DESIGN_EVOLUTION.md` 已系统性评估：把协议作为内核一等公民、能力公理→协议满足
关系、Prompt 协议接口化（`PromptContributor`/`PromptPart`）、泛型约束与泛型函数、意图正交化
（字符串栈→Promptable 值栈）、函数实例与意图/LLM 上下文一等交互、模块协议化。与用户设想
**高度一致**，且 Phase 0-2（协议注册表/用户协议/泛型 bound）已基本落地。本文档承接其 Phase 3。

---

## 二、设想拆解与可行性确认

### 2.1 装饰壳体系

**设想**：装饰器不是定义时使用，而是作用于函数实例上包装 fn 实例；高阶函数（行为语句/意图注释
等）声明自己需要的"壳"（impl）；运行时/编译时根据 fn 实例具备的壳确认是否允许传入 + 确定调用时
的外壳包装；从而任意可调用实例可嵌入 ibci 核心机制，不再局限于 `__prompt__`。

**本质**：这正是 Rust 的 trait + impl + 泛型 bound 机制在 IBCI 的落位：
- "壳" = 协议（trait）；
- "函数实例具备的壳" = 该实例类型满足的协议集合；
- "高阶函数声明需要的壳" = 泛型 bound（`T: SomeProtocol`）——**已实现**；
- "传入后的外壳包装" = 编译期/运行期按协议分派到 impl 提供的方法。

**可行性**：✅ **高。** 协议/impl/泛型 bound 全部已有，T09 零回归验证。真正的缺口是**三个**
（均非设计障碍，属实现扩展）：
1. **impl 目标范围**：扩展到"可调用实例类型 / 内置类型 / 实例级壳声明"（当前受限本模块用户类）；
2. **函数实例的 prompt 呈现**：为 fn_callable/behavior/LLM 函数提供有意义的默认 `__to_prompt__`
   并允许协议化自定义（LANGUAGE_DESIGN_EVOLUTION §3.6 已给出方向）；
3. **行为语句/意图注释消费协议化**：从"只认 `__to_prompt__`/`__payload_prompt__` 魔法方法名"
   改为"按协议查询 + 按协议分派包装"。

### 2.2 llm 可调用类替代 llm 函数

**设想**：抛弃 llm 函数，构建可调用的 llm 类（类似 Python `__call__` 类），实现可调用类协议 +
内核机制；用户实现哪些方法；不再区分 sys/user prompt（更抽象）；用户派生类可改写意图注释处理、
改写 retry（llmretry 变成高阶函数/类型类函数的语法糖包装而非独立机制）；llm 类应有更完善设计。

**现状契合度**：
- LLMCallRequest 已是语义槽模型（无 sys/user 概念，由 provider 组装）→ **统一消息体方向正确**；
- llm 函数语法（`__sys__`/`__user__`/`__llmretry__`）反而是**直接要求底层请求格式的旧形态**
  ——用户指出的尴尬 1 成立；
- 运行时已统一（`IbUserFunction` + `callable_kind`）→ 语法层收敛的成本低于实现层。

**可行性**：✅ **高。** 需要设计：
1. "可调用的 llm 类"的协议方法族（承载 LLM 调用意图，替代 `__sys__`/`__user__` 段）；
2. retry 高阶化：`retry`/`llmretry` 从"独立语法+独立帧机制"收敛为"高阶函数/类型类函数的语法糖
   包装"（llm 派生类在实现时定义自己的 llmretry 体系）；
3. 意图改写：llm 派生类可自定义"如何对待意图注释内容"；
4. 类实例可被 `@~`/意图/fn/run_batch/stream 统一消费。

---

## 三、设计骨架（初步）

### 3.1 协议新增（壳）

| 协议 | 方法族（草案） | 用途 |
|------|---------------|------|
| `LLMCallable` | `__llm_call__`（或方法族） | 标记/包装"可被行为语句/意图消费的可调用实例" |
| `IntentValue` | 呈现意图的一等值 | 意图栈从字符串栈升级为可渲染值栈 |
| `PromptContributor` | 统一 prompt 贡献 | 收敛 `__to_prompt__`/`__payload_prompt__`/意图/retry hint |

### 3.2 行为语句 / 意图注释消费路径改造

- 行为语句：经协议查询确认"可调用实例具备 LLMCallable 壳"后，按协议分派包装为一次
  LLMCallRequest（不再硬编码占位符渲染）。
- 意图注释：`@+ $fn` 这类段改为**求值 + 按协议渲染**（当前存 AST 节点对象是缺陷，须修复）。

### 3.3 llm 可调用类（草案形态）

```text
class MyLLM:
    # 用户实现的方法族（草案，待细化）
    func __llm_call__(self, 参数...) -> llm_request: ...
    func __intent__(self, 意图块) -> ...: ...      # 改写意图处理（可选）
    func __retry__(self, ...) -> ...: ...          # 改写 retry（可选，高阶化）
```

- 实例可被 `fn f = MyLLM(...)` 承载、被 `@~` 消费、被意图嵌入、被 run_batch/stream 消费。
- `llm ... llmend` 语法 → 迁移为"语法糖包装到 llm 可调用类"（工作模式定论：真设计，非 compat shim）。

### 3.4 retry 高阶化

- `retry`/`llmretry`/`llmexcept` 从"独立语法 + LLMExceptFrame 独立机制"收敛为"对可调用实例的
  高阶包装"（与装饰壳体系同一机制：retry 是高阶函数，声明需要的壳，包装后返回新可调用实例）。

---

## 四、破坏面评估

| 层 | 影响 |
|----|------|
| 语言级 | llm 函数语法保留/迁移策略（用户裁定项）；可能新增协议关键字用法（无需新关键字，复用 protocol） |
| 类型系统 | 新增内置协议（LLMCallable/IntentValue/PromptContributor）；impl 目标范围扩展；能力公理→协议满足关系收敛 |
| 编译器 | 泛型 bound 已支持（扩展实参判定）；impl 目标放宽；行为语句段消费的语义检查 |
| 运行时 | 意图值栈升级（字符串栈→可渲染值栈）；行为语句/意图注释消费路径改造；llm 可调用类内核机制 |
| 契约 | LLMCallRequest 扩展（意图改写/retry 高阶化的承载字段）；stream_call 签名收敛 |
| 文档/测试 | docs/ 同步（KNOWN_LIMITS/syntax/architecture/subsystems）；全量 pytest 零回归 + 试用回归 |

---

## 五、执行规划（分阶段，同一时刻只主推一个 P0）

| 阶段 | 内容 | 验证门 | 产出 |
|------|------|--------|------|
| **P0（本阶段）** | 调研分析 + 可行性 + 规划（本文件） | 用户确认方向 | 本文件 + 汇报 |
| **P1** | **llm 可调用类设计定稿**：协议方法族/意图改写/retry 高阶化/与 LLMCallRequest 承载；llm 函数迁移策略（真设计，废除 `__sys__/__user__` 段） | 设计质询 + 破坏面全量评估 | 设计定稿（本文件 → docs/） |
| **P2** | 装饰壳体系地基：impl 目标扩展到可调用实例/内置类型 + 函数实例默认 prompt 呈现协议化 | 全量 pytest 零回归 | 协议/impl 扩展落地 |
| **P3** | 意图一等值化（字符串栈→可渲染值栈）+ 行为语句/意图注释消费协议化（修复 G1/G2/G5） | 全量 pytest 零回归 + 试用回归 | 割裂点修复 |
| **P4** | llm 可调用类内核机制实现 + retry 高阶化收敛 + llm 函数语法迁移 | 全量 pytest 零回归 + T09 风格试用 | 新主线闭环 |
| **P5** | 文档体系收敛（docs/ 单点真理）+ 试用套件扩展 + 收尾 | 全量 pytest + 文档治理扫描 | 交付 |

> 每阶段仍守全量 `python -m pytest tests/` 零回归 + 本地 commit + 禁 push（除非用户授权）。
> 大范围破坏性重构走独立分支；零风险改进可经复核后直接合并 unsafe-vibe-dev。

---

## 六、待决项（self-grill 产出，需用户拍板）

1. **llm 函数语法的最终去留**：彻底删除（破坏性，需评估迁移）+ 语法糖映射到 llm 可调用类？
   推荐后者（保用户迁移平滑，但按工作模式定论必须是"真设计"而非 compat shim）。
2. **装饰壳的"壳"粒度**：壳 = 协议（类型级，推荐，与现有机制一致）；还是需要**实例级壳声明**
   （对单个 fn 实例声明壳）？后者是 Rust impl 的实例级变体，需评估语法形态。
3. **retry 高阶化的边界**：`llmexcept` 块（含快照隔离/编译期写保护）是否全部收敛进"高阶包装"，
   还是保留帧机制、仅将 retry/llmretry 语法高阶化？
4. **意图一等值化的执行时机**：是否与 llm 可调用类同一阶段（P3/P4），还是提前独立修复 G2/G5？

---

## 六bis、用户补充（2026-08-18 第二时点）：最终体系化形态——总统一性主线

> 用户在初次设想基础上补充了**决定性的总统一性要求**，把整个设想的最终形态确定下来。
> 本阶段（P0 调研）需将下列补充**纳入设计基准**，后续 P1-P4 以本节的"总统一性"为准绳，
> 而非孤立的局部收敛。

### 6bis.1 三层总收敛（补充信息的本质）

1. **"LLM 相关一切"→ 协议（类型类）+ 可调用实例 这一对概念收敛**：
   行为描述语句 / 意图注释 / retry / llm 函数 / prompt 协议族 / lambda / snapshot
   ——全部不再各自为政，收敛为"可调用实例（唯一载体）+ 协议/impl（唯一能力声明与分派机制）"。
   高阶函数（行为语句/意图/retry）只按协议声明"需要的壳"、按协议包装。
2. **lambda 与 snapshot 的彻底统一**：二者本质都是 **llm 匿名可调用类的两种捕获模式语法糖**：
   - lambda = 引用捕获（共享 cell，调用时读当前意图栈/变量）；
   - snapshot = 值捕获（定义时深拷贝变量 + 意图快照）。
   与 Python 闭包 vs Rust `move` 闭包的对应同构；"捕获策略"只是可调用类的创建参数/派生差异，
   lambda/snapshot 从"两个语法"降级为"同一可调用类的两种构造形态"。
3. **内置类型协议改写**：`impl SomeProtocol for int:` 允许用户在用户代码层改写 `int` 等
   内置变量的 `__prompt__` 系列协议——impl 目标须从"本模块用户类"扩展至**内置类型**，
   需"内置类型协议方法表"允许用户补充（N1 已验证 `impl` 内 LLM 方法可行，是现成先例）。

### 6bis.2 由补充衍生的一致性推论（需在 P1 设计定稿中落实）

- **retry 同样进入协议化**：不仅 llmretry 是 impl 语法糖，**lambda 式行为描述语句的可调用实例
  也应允许通过书写 impl 实现 retry 包装**——retry 从"独立语法 + LLMExceptFrame 帧机制"收敛为
  "对可调用实例的高阶包装（高阶函数声明需要的壳）"。
- **意图注释彻底协议化**：整个意图注释体系接入类型理论/函数式地基（意图值栈→可渲染值栈）。
- **行为描述 lambda 实例与 llm 可调用类的实质彻底统一**：行为语句消费的"匿名可调用实例"与
  "用户显式 llm 可调用类实例"是同一机制，不再有双轨。
- **设计准绳**：凡新设计，先问"它是否是一个可调用实例 + 一个协议"；凡机制，先问"它的捕获策略 /
  包装策略能否参数化"。这对应 design-philosophy 的机制同构 + 设计语言统一。

### 6bis.3 仍待下个 session 深挖的补充调研点（交接清单）

1. **内置类型协议方法表的机制形态**：如何让 `impl SomeProtocol for int` 在不破坏既有内建
   `__to_prompt__` 分派的前提下补充/覆写（协议方法表 vs 现有 receive 分派；序列化/动态宿主隔离）。
2. **lambda/snapshot 捕获策略参数化的落点**：当前 `IbFnCallable.capture_mode` 已有"lambda/snapshot"
   两态（`core/runtime/objects/primitives/callables.py`）——评估将其提升为"可调用类构造参数/
   派生类"的语法与内核改造面。
3. **retry 协议化的边界**：`llmexcept` 块（快照隔离/编译期写保护，VM 级机制）全部收敛进
   "高阶包装"还是保留帧机制仅高阶化语法；llm 派生类自定 retry 与行为语句默认 retry 的协作。
4. **行为语句匿名可调用实例 vs 用户 llm 可调用类实例的统一点**：二者在协议判定、意图改写、
   retry 包装、run_batch/stream 消费路径上的合并/去重。
5. **能力公理 → 协议满足关系的最终收敛**（G7）：`has_*_cap` 封闭 flag 集合如何被协议注册表
   完全替代。
6. **prompt 协议族类型类化**：`__to_prompt__`/`__payload_prompt__`/`__from_prompt__`/
   `__outputhint_prompt__`/`__validate_prompt__` 收敛为类型类方法（含内置类型可改写），
   与现有 `PromptRenderer`/`satisfies_protocol` 的衔接。

---

## 附、事实核验记录

- 探针 t1：`fn f = lambda...; @~ $f ~` → `<FnCallable(lambda) node_...>`（占位符，G1）。
- 探针 t2/t5/t8/t9：意图 `@+ $fn`/`@+ $user_class` → 意图栈内容为 `IbName(...)` 或原样（G2/G5）；
  对照用户类 `__to_prompt__` 在行为语句中可正常渲染（`User(alice)`）。
- 探针 t3：`impl Describable for fn_callable` → `SEM_TYPE_MISMATCH: impl target 'fn_callable' is not a known class`。
- 探针 t4：`func call[T: Greeter](T x)` → 泛型 bound 编译期生效（Bar 不满足 Greeter 被拦截）。
- 代码实证：`_llm_function.py`（user_sys 槽 + user_prompt，G3）、`ai/core.py` stream_call（G4）、
  `intent.py`（字符串栈，G5）、`protocol.py`（协议注册表）、`_shared.py`（统一调用路径）。
