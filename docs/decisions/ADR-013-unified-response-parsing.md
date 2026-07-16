# ADR-013: 统一响应解析（supersedes ADR-009）

## Status
Accepted (2026-06-25，2026-06-25 修订)

**Supersedes**: [ADR-009](_call_llm_raw introduction (D6/DEC-4 reconciliation))。ADR-009 的核心前提被代码证据证伪（见 Context）。

**修订记录**：本 ADR 初版的 Decision 第 3 条提出在 `AxiomParsingStrategy.parse` 内用 `if has_multimodal_response_cap: from_response else: from_prompt` 的**标志位 `if/else` 分支**。经第三轮研讨，项目负责人明令禁止过程式硬编码判断（"不在代码运行流程里硬编码某种过程式的判断，要基于整个 `__prompt__` 系列体系"）。修订版据此改为**协议驱动分发**（与 `__payload_prompt__` 的 `receive()` 分发同构），具体治理见 **ADR-016（变量存储模型）第 3 条**。本 ADR supersede ADR-009 的核心结论（单入口、单策略、无 `execute_*` 分叉）**仍然成立**。

## Date
2026-06-25

## Context

ADR-009 为 Phase 4 多模态规定了一条**分叉**的响应处理路径：
- 新增 `_call_llm_multimodal`，与 `_call_llm` 并行
- 路由判定发生在 `execute_*` 内（分叉），而非解析管线内

ADR-009 的明文前提（:21-24）：
> "`_call_llm` is called by `execute_behavior_expression` **before** the target type is known. So the routing decision (str vs raw response) must happen inside `_call_llm` or its caller."

2026-06-25 的一次代码审计**证伪了该前提**：
- 目标类型**完全来自 AST**（`node_data["returns"]` / side-table `node_to_type`），**不依赖 LLM 响应**。
- `_get_expected_type_hint`（`_prompt.py:282-295`）从 AST 元数据计算它——纯结构查询，与响应无关。它在 `_call_llm`（`_behavior.py:119`）**之后**仅是书写顺序便利，不是数据依赖。
- `type_name` **已经作为参数贯穿整个解析管线**：`execute_*` → `_parse_result(raw_res, type_name, ...)` → `parse_result(raw_res, type_name, ...)` → `strategy.parse(raw_res, type_name, ...)`（`llm_parsing_strategy.py:51`）。
- 因此 `AxiomParsingStrategy.parse` 在其运行时**已经同时握有**路由所需的两个输入（原始响应 + 目标类型）。

在 `execute_*` 里分叉 `_call_llm_multimodal`，等于**把本该由策略层拥有的路由决策复制了一份**。项目负责人已明确拒绝分叉/bypass 式解析逻辑——"逻辑上存在分叉和不统一的职责这种代码行为本质上是一种技术债，不应该再遗留下去"。

附带证据：全部 10 个 `last_llm_result` 读者（`assignment.py`/`control_flow.py`/`llm_behavior.py`/`_shared.py`/`llm_except_frame.py`）只依赖 `{is_certain, retry_hint, raw_response}` 三元组，不依赖 value 的类型；`dispatch_eager` 异步路径也走 `parse_result`——统一在策略层可一并覆盖。

## Decision

以**单一入口、单一策略、协议驱动分发**统一响应解析：

1. `_call_llm` **保持返回 `str`**（D6 不变量保住）。它额外把完整响应对象暂存到 `runtime_context` 的旁路寄存器（`set_last_raw_response` / `get_last_raw_response`），与 `set_last_llm_result` 对称。provider 按需填充，默认 `None`。

2. `AxiomParsingStrategy` **不查询能力标志位、不写 `if/else` 分支**。它通过 `receive()` / vtable 把响应解析**委托给目标类型 axiom 所实现的协议方法**——与今日 `__payload_prompt__` 在 `_obj_to_payload` 中的分发方式同构。具体：
   - 内存型类型（`storage_model = memory-backed`，含全部现有内置类型）继续走 `__from_prompt__`——字节级不变。
   - 磁盘型类型（`storage_model = disk-backed`，含未来全部 media）走其磁盘型协议族方法（具体方法名在 PT-ARCH-17 设计期确立）。
   - executor / strategy 代码**存储模型无关**；新增磁盘型类型不改 strategy 一行代码。

3. `execute_behavior_expression` / `execute_llm_function`（含 CPS 孪生）**不修改、不分叉**。

> **与初版的差异**：初版 Decision 第 3 条是"在 `AxiomParsingStrategy.parse` 内查 `has_multimodal_response_cap` 标志位做 `if/else`"。该设计虽优于 ADR-009 的 `execute_*` 分叉，但仍是过程式硬编码判断，违反项目负责人确立的协议驱动原则（ADR-016 第 3 条）。修订后改为 `receive()` 委托，标志位不再在分发点被查询。`has_multimodal_response_cap` 这类能力位可作为**编译期/内省**的元数据保留，但**不参与运行时分发路径判定**。

## Alternatives Considered

### Alternative A：分叉 `_call_llm_multimodal`（ADR-009 原方案）
- Pros：把多模态与文本路径物理隔离
- Cons：建立在被证伪的前提上；复制路由决策；项目负责人拒绝分叉；4 处 MOCK 站点需同步复制
- Rejected：前提不成立；违反路由职责单一

### Alternative B：加宽 `_call_llm` 返回 `Union[str, ResponseObj]` 并加宽 `parse(raw_res: Union[...])`
- Pros：一条管线、无旁路寄存器
- Cons：破坏 `execute_*` 里 8 处 MOCK 哨兵字符串相等比较；破坏 `ILLMProvider.__call__ -> str` 契约；每个 `from_prompt` 实现都要加类型分叉
- Rejected：高回归风险（ADR-009 Alternative B 早已拒绝）

### Alternative C：把 `from_prompt` 泛化为 `Union[str, Obj]`
- Pros：单个协议方法
- Cons：把分叉推进到 8+ 个 axiom 实现；`EnumAxiom.from_prompt` 已经放松到 `Any` 正说明这种不一致的蔓延
- Rejected：分散而非消灭分叉

### Alternative D：标志位 `if/else` 分支（本 ADR 初版方案）
- Pros：单入口单策略，优于 ADR-009 的 `execute_*` 分叉
- Cons：仍是过程式硬编码判断；违反项目负责人确立的协议驱动原则（"不在运行流程里硬编码过程式判断"）；被 ADR-016 第 3 条明确禁止
- Rejected：明令禁止；本修订版已改协议驱动分发

## Consequences

- **文本路径零行为变更**：能力位默认 `False`，今天没有任何类型声明 `has_multimodal_response_cap` → 在 `MediaAxiom` 落地前，新分支是死代码，文本路径字节级一致。
- 全部 10 个 `last_llm_result` 读者保持不变（它们只读 `{is_certain, retry_hint, raw_response}`）。
- `dispatch_eager` 异步路径自动覆盖（同样走 `parse_result`）。
- MOCK 基础设施不变（`_call_llm` 仍返回 `str`，魔法哨兵字符串比较全保留）。
- `MediaAxiom.from_response`（Phase 4）只接入一个定义良好的点，而非一条并行管线。
- **ADR-009 被取代**；`_call_llm_multimodal` 将**不再引入**。
- `MULTIMODAL_BEHAVIOR_DESIGN.md` §C.5 / §十一-D6 需更新引用，指向本 ADR 而非分叉路径。

## 改动面（全部为加法）

`core/kernel/axioms/protocols.py`（能力位 + `from_response` 签名）、`core/kernel/axioms/primitives/base.py`（默认 `False` + 默认实现）、`core/kernel/spec/registry/_capabilities.py`（`get_from_response_cap`）、`core/runtime/interpreter/llm_parsing_strategy.py`（`AxiomParsingStrategy.parse` 一个分支）、`core/runtime/interpreter/runtime_context.py`（旁路寄存器 + getter）、`core/runtime/interpreter/llm_executor/_core.py`（`_call_llm` 顺带暂存 obj）。

**不改**：`_behavior.py`、`_llm_function.py`、`_scheduler.py`、任何 VM handler、任何现存 axiom、`LLMResult` 字段集、`ibci_ai` MOCK 路径。
