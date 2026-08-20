# 阶段 A1 · 主线架构债务落地 — 设计文档（临时）

> **性质**：临时任务控制设计文档（设计阶段先行，落地后删除，git 承载）。
> 依据：`tasks_docs/NEXT_STEPS.md` 阶段 A P0 候选 #1 + `tasks_docs/_planning_health_first.md` §二 A1。
> 目标：解除 2 项登记架构债——① G5 意图值栈全量重构；② 行为值深程统一装配入口收敛。
> 纪律：先设计→评估→落地，勿半接通；全量 pytest 零回归；工作模式定论全程适用。

---

## 一、债务 1：G5 意图值栈全量重构（意图栈 content:str → 可渲染一等值栈、按值匹配）

### 1.1 现状与问题定位（代码证据）

- `IbIntent`（`core/runtime/objects/intent.py`）同时持有 `content: str` 与 `segments: List[Any]` 双表示：
  - `content` = 解析期把 segments 扁平拼接的字符串（`statement.py:_parse_intent_info` 第 310 行
    `"".join([s if isinstance(s, str) else str(s) ...])`）。对**动态段**（`@+ $x`，运行时段为
    `node_<uid>` 引用串）而言，`content` 是退化产物（≈ "node_xxx..."），不可作内容、不可作匹配键。
  - `segments` 才是真实来源：运行时对 `node_` 段经 VM 求值（`resolve_content_cps` 的 `yield segment`）
    再用 `__to_prompt__` 渲染（P3 已保证可调用/行为值渲染为契约形态）。
- **双写真相**：同一意图的"内容"存在两处（content 退化串 + segments 求值渲染），且 `@-` 匹配
  （`intent_context._remove_by_content` / `runtime_context.remove_intent`）用的是退化 `content`——
  动态意图（`@+ $x` / `@- $x`）**匹配恒失效**（按值匹配无法工作）。
- 消费者散落：`_llm_callable.py:120-122`、`interpreter.py:101-102`、`execution_context.py:283-284`、
  `primitive_initializer._ic_resolve/_ic_to_prompt`、`intent_context.to_prompt`、`intent_resolver` 均直接
  读 `i.content`。

### 1.2 目标模型（值栈）

- **意图段在注释/栈操作执行点求值为一等值列表**（`IbIntent.values: List[IbObject]`），
  栈/涂抹/排他槽存**值**而非退化字符串或延迟段引用。
- 删除运行时 `content`/`segments` 双表示（单点真理 = 值列表）。
- 渲染：`render_text(context, ec)` = 各值 `__to_prompt__` 拼接（复用 `_intent_segment_to_prompt`）。
- 匹配（`@-`）：操作数求值为值 → 经 `__to_prompt__` 渲染为文本 → 与栈内意图渲染文本比较
  （"按内容移除"语义保留，但匹配键由**值**派生——修复动态意图匹配失效）。标签匹配不变。

### 1.3 语义决策：求值时机 = 注释执行点（eager 值捕获）

- 理由：① 债文本"值栈存原始值"的字面语义——`@+ $x` 压入的是**当时** x 的值，后续 x 重赋值不影响
  已压入意图（避免"意图随变量变化"的陷阱）；② 匹配确定（按压入时的值移除）；③ 消除"resolve 时重求值"
  的语义歧义。
- 现状为 resolve 时惰性求值（`@+ $x` 反映 LLM 调用时刻 x 的值）。改为 eager 属**语义演进**；
  现有测试套件全部意图用例均为静态字符串（无 `@+ $x` 后重赋值断言），零测试依赖惰性，故零回归风险
  （判别测试补齐 eager 语义）。
- 一次性意图（`@`/`@!`）同样 eager：注释处求值后安装，值捕获于语句窗口之前。

### 1.4 破坏面清单（改动文件与点）

| 文件 | 改动 |
|------|------|
| `core/runtime/objects/intent.py` | `IbIntent` 模型：`values: List[IbObject]` 取代 `content`/`segments`；`resolve_content(_cps)` 改为从值渲染；`get_content()` 返回渲染文本 |
| `core/runtime/vm/handlers/llm_behavior.py` | `vm_handle_IbIntentStackOperation` / `vm_handle_IbIntentAnnotation`：eager 求值段 → 值 → 构造；`@-` 按值匹配 |
| `core/runtime/vm/handlers/_shared.py` | `build_one_shot_intent_from_annotation`（sync）改 eager 求值；`_vm_execute_stmt_sequence` 相应调整 |
| `core/runtime/vm/vm_executor.py` | `run_body` 一次性意图构造同步 eager 求值 |
| `core/runtime/objects/intent_context.py` | `remove`/`_remove_by_content` → 按渲染文本匹配；`to_prompt` 从值渲染；`resolve_to_prompts(_cps)` 用值渲染 |
| `core/runtime/interpreter/runtime_context.py` | `remove_intent` 契约（content → 值渲染文本）；`get_resolved_prompt_intents(_cps)` 不变（委托 intent_context） |
| `core/runtime/interpreter/llm_executor/_llm_callable.py` | `_resolve_llm_callable_intents_cps` 从值渲染（去 `i.content`） |
| `core/runtime/interpreter/interpreter.py` / `execution_context.py` | `get_active_intents` 从值渲染 |
| `core/runtime/bootstrap/primitive_initializer.py` | `_ic_resolve`/`_ic_to_prompt` 从值渲染 |
| `core/runtime/serialization/runtime_serializer.py` | `_collect_intent`/反序列化：序列化值列表（经 `_process_value`/`_deserialize_value`） |
| `core/kernel/intent_resolver.py` | `resolve(_cps)` 调用 `render_text`（值渲染），去 `resolve_content` 语义依赖 |
| `core/runtime/factory.py` | `create_intent`/`create_intent_from_node` 签名适配（接值列表） |
| `tests/` | 判别测试：动态 `@+ $x`/`@- $x` 按值匹配、eager 值捕获、序列化 round-trip、渲染契约 |

### 1.5 求值辅助（sync/CPS 对，沿用既有模式）

- `_evaluate_intent_segments_cps(ec, segments) -> List[IbObject]`：生成器，`yield` 出 `node_` 段、
  `send` 回值；非 node_ 字符串段保留为 IbString（经 `registry.box`）。
- `_evaluate_intent_segments_sync(vm, ec, segments)`：同步薄包装（`vm.run(seg)` 重入，与现有
  `IbIntent.resolve_content` 同步路径同构），驱动 CPS 权威版。与既有
  `_prepare_behavior_call` / `_prepare_behavior_call_cps`（sync 薄包装 + CPS 权威）模式一致。

---

## 二、债务 2：行为值深程统一装配入口收敛

### 2.1 现状与问题定位（代码证据）

- 行为装配权威：`_prepare_behavior_call_cps`（`_behavior.py`）——行为值经语义槽装配，消费方：
  `dispatch_eager_cps` / `execute_behavior_expression_cps` / `_run_batch_cps` / `assemble_stream_request_cps`。
- LLM 可调用类装配权威：`assemble_llm_callable_request_cps`（`_llm_callable.py`）——用户 `__llm_call__`
  装配 dict，消费方：`invoke_llm_callable_cps` / `_invoke_llm_callable_batch_cps` / `assemble_stream_request_cps`。
- **分散的类型分派**：`run_batch` 自持 `if behavior / elif llm_callable` 双驱；`assemble_stream_request_cps`
  自持同类分派。两处各自判断值类型选入口——同一"装配决策"散落多处（设计思路割裂）。
- 既有评估："值自身差异承载（非双通道）"正确（行为→语义槽、llm 类→用户 dict 是本质差异，非同一决策双写）；
  但**分派入口应单一**（一处按值选装配策略），消费方不各自重复判断。

### 2.2 目标设计（单一装配入口）

- 新增统一装配入口 `assemble_llm_call_request_cps(target, ec, *, target_model="", captured_intents=None,
  item=None, call_args=None) -> (LLMCallRequest, type_hint, retry_policy)`：
  - behavior 值 → 经 `_prepare_behavior_call_cps`（语义槽装配，`retry_policy=None`）；
  - llm 可调用类 → 经 `assemble_llm_callable_request_cps`（含 `__intent__`/`__retry__`）；
  - 其它 → fail-fast `TypeError`。
- 消费方收敛：`run_batch` 双驱、`invoke`（行为/llm 类）、`assemble_stream_request_cps` 统一经该入口；
  删除各自重复的 `if behavior/elif llm_callable` 分派。
- 行为表达式路径（`dispatch_eager_cps` / `execute_behavior_expression_cps`，无值对象、按 node_uid 装配）
  保持 `_prepare_behavior_call_cps`（值路径与表达式路径是不同形态，非双通道——表达式装配无目标值可寻）。

### 2.3 破坏面清单

| 文件 | 改动 |
|------|------|
| `core/runtime/interpreter/llm_executor/_llm_callable.py` | 新增统一入口；`assemble_stream_request_cps` 改委托 |
| `core/runtime/interpreter/llm_executor/_behavior.py` | `run_batch`/`_run_batch_cps`/`_run_batch_sync` 经统一入口；双驱保持（每项参数绑定语义不同） |
| 判别测试 | `tests/e2e/test_llm_callable_unified.py` 等既有判别零回归 + 补统一入口判别 |

---

## 三、验证门

- 每增量：全量 `~/miniconda3/envs/ibci/bin/python -m pytest tests/` 零回归 + 判别测试通过。
- G5 判别：动态意图按值匹配（`@+ $x`/`@- $x`）、eager 值捕获（压入后重赋值不影响）、
  静态意图行为不变（既有 intent 测试全绿）、序列化 round-trip 值保真、可调用值契约渲染。
- 债务 2 判别：run_batch/invoke/stream 行为与 llm 类路径经统一入口后行为零变化（既有判别全绿）。

## 四、风险与回退

- G5 eager 为语义演进：以"既有 intent 测试全绿 + 新增判别"为回归防线；若序列化任意值遇阻，
  记录并收窄（值渲染模型保留、eager 捕获评估）——**不半接通**，宁收窄不夹生。
- 债务 2 为纯重构：行为零变化，回归防线为既有判别测试全绿。

## 五、实施顺序（增量）

1. 债务 2 统一装配入口（先小后大，先建立收敛模式）。
2. G5 值栈：模型（values）→ 构造（handlers/语句循环）→ 消费者（渲染/匹配）→ 序列化 → 判别测试。
3. 文档同步：`docs/syntax/09_intent_system.md`（求值时序/按值匹配说明）、
   `docs/subsystems/01_intent_system.md`（值栈模型）、NEXT_STEPS/WORKLOG/HANDOFF。
