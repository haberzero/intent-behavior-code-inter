# ADR-016: 变量存储模型 —— 类型级 memory/disk 区分 + 协议驱动分发

## Status
Accepted (2026-06-25)

**废弃命名**：本 ADR 取代过往文档（源自 `AUDIT_REPORT_20260527.md §一`）中非正式的 **"Inter 层"** 提法。该命名的出处不明（疑似过往智能体自造），项目负责人明确要求更明确、更具区分度的命名。本文采用 **"变量存储模型（Variable Storage Model）"** 作为正式术语；"Inter 层"一词即日起停用，相关文档应在接触时改写。

**治理范围**：本 ADR 是 ADR-013（响应解析）与 ADR-014（media 存储）的上层治理；二者已据此修订。

## Date
2026-06-25

## Context

### 历史背景
`AUDIT_REPORT_20260527.md §一` 把 IBCI 描述为四元结构（Code/Behavior/Intent/Inter），其中"Inter 层"被等同于 `__prompt__` 协议族——`__to_prompt__` / `__from_prompt__` / `__outputhint_prompt__` / `__payload_prompt__` / `__validate_prompt__`。项目负责人不认可此命名的出处，并指出它**不足以表达**真正需要的架构区分。

### 真正的架构张力
`__prompt__` 协议族本质上是**内存导向**的：每个方法都假设值的数据是进程内的 Python 对象/字节。这在 Phase 3 把媒体类型实现为纯内存字节（`MediaStorage` 持有 `bytes`）时暴露了三个问题：

1. **两个潜伏 bug**（`deep_clone.py:89` 严格身份判定 + `RuntimeSerializer` 无 payload 分支）：media 字节在 llmexcept 快照 / save_state 下**静默丢失**。
2. **对文件来源不诚实**：`file.read_audio` 把已在磁盘上的字节再拷一份进内存——纯浪费。
3. **不可扩展**：50MB 音频 × N 次 deep_clone / 序列化的成本无法承受。

### 项目负责人的明确指令（2026-06-25 第三轮研讨）
1. **类型必须显式区分**纯内存类 / 硬盘卸载类；**所有 media 类都是硬盘卸载类**。
2. 这种区分必须是**类型级一等区分**，基于路径系统建模，与纯内存类**平行**（不嵌套）。
3. **禁止在运行流程里硬编码过程式判断**（如 `if has_multimodal_response_cap:`）——分发必须**协议驱动**，沿用 `__prompt__` 协议族的管理思路。
4. 保留 `__prompt__` 协议族作为**纯内存类型**的处理协议；为全模态容器处理引入**平行**的协议族。
5. 允许**整体淘汰**当前 `MediaStorage`（字节持有者），替换为更干净合理的架构。
6. 潜伏 bug 的修复**不允许过渡/简易方案**，必须在存储模型架构完善后统一修复。

## Decision

### 1. 类型级 `storage_model` 属性
每个类型显式声明一个存储模型，取值二选一，**互不嵌套、平行**：

| 存储模型 | 含义 | 数据住所 | 适用类型 |
|---------|------|---------|---------|
| **memory-backed**（内存型） | 数据在进程内 | Python 对象/字节 | `int`/`float`/`str`/`bool`/`list`/`tuple`/`dict`/用户类（当前全部） |
| **disk-backed**（磁盘型） | 数据在路径上 | 路径引用（经统一路径系统，ADR-015） | **全部 media 类**（`audio`/`image`/`video`/`media`） |

磁盘型变量的**本体就是一个路径引用**——它是一个 handle（身份对象）。字节只在 LLM I/O 协议需要时**惰性物化**。

### 2. 磁盘型变量基于路径系统建模
磁盘型变量的身份、快照、序列化都以路径引用为核心：
- **deep_clone**：拷贝路径引用（浅、廉价），不拷字节。
- **序列化**：序列化路径引用（字符串），不序列化字节。
- **跨 isolation host**：路径经统一路径系统解析（ADR-015），可移植。
- **来源感知**：`FileBacking`（指向已存在的源文件，零拷贝）+ `GeneratedBacking`（指向 LLM 生成时溢写的工件）。**不存在 `MemoryBacking`**——所有 media 一律磁盘型。

### 3. 协议驱动分发（核心原则）
变量如何参与 LLM I/O，由**分发到该类型 axiom 所实现的协议方法**决定——通过 `receive()` / vtable 鸭子类型分发（与今日 `__payload_prompt__` 的分发方式一致）——**而非**在 executor/strategy 里查询能力标志位的 `if/else`。

含义：
- executor / strategy / deep_clone / 序列化器的代码**存储模型无关**（storage-model-agnostic）。
- 行为由各类型的 axiom 承载；新增磁盘型类型不需要改动 executor/strategy 一行代码。
- **明确禁止** ADR-013 原方案那种 `if has_multimodal_response_cap: from_response else: from_prompt` 的标志位分支——它已被本 ADR 取代。

### 4. `__prompt__` 协议族保持为内存型 I/O 协议
现有 `__prompt__` 族（`__to_prompt__`/`__from_prompt__`/`__outputhint_prompt__`/`__payload_prompt__`/`__validate_prompt__`）**语义不变**，继续作为**内存型**类型的 I/O 协议。它们不被泛化为 `Union[str, Obj]`——那样只会把分叉推进到每个实现里。

### 5. 磁盘型类型获得平行的协议族
磁盘型类型实现一组**与 `__prompt__` 平行**的协议方法（具体方法名在 PT-ARCH-17 设计期确定），治理：
- 惰性物化（按需从路径读字节）
- 基于路径的 payload 构建
- 基于路径的响应解析
- 路径引用的快照/序列化

这组协议**不与 `__prompt__` 混合**——是独立的一族，但**用同样的 `receive()` 机制分发**。

### 6. 制动 `MediaStorage` 整体淘汰
`MediaStorage`（字节持有者）是"内存型 media"模型的化身，与"所有 media 一律磁盘型"直接矛盾。本 ADR 正式批准其整体淘汰：
- `core/runtime/objects/media_storage.py` —— 淘汰
- `core/runtime/objects/media_types.py`（`IbAudio`/`IbImage`/`IbVideo` 内存包装）—— 替换为磁盘型 handle 类型
- `core/kernel/axioms/primitives/media.py` 中基于 `storage.data` 的 `__payload_prompt__` —— 改为从 backing 惰性物化
- `ibci_file.read_*` —— 改为返回磁盘型 handle（`FileBacking`），不立即读字节

## Alternatives Considered

### Alternative A：保留 `MemoryBacking` 作为第三选项（ADR-014 原案）
- Pros：改动面看似更小
- Cons：项目负责人明确要求所有 media 一律磁盘型；该选项制造歧义和过渡代码
- Rejected：违反"所有 media 磁盘型"硬要求；违反工作模式定论

### Alternative B：把存储模型做成运行时标志，而非类型级
- Pros：实现简单
- Cons：项目负责人要求类型级一等区分、专门建模、与内存类平行
- Rejected：未达到要求的建模层级

### Alternative C：用能力标志位 `if/else` 分发（ADR-013 原案）
- Pros：直接
- Cons：违反协议驱动原则；项目负责人明令禁止过程式硬编码判断
- Rejected：明确禁止；已被本 ADR 第 3 条取代

### Alternative D：泛化 `__prompt__` 协议族以同时处理两种模型
- Pros：单族
- Cons：把分叉推进到每个 axiom 实现；模糊能力意图
- Rejected：分散而非消灭分叉

## Consequences

### 对潜伏 bug 的处置（关键）
两个潜伏 bug（`deep_clone.py:89` 严格身份判定 + 序列化器 payload 缺失，PT-ARCH-12/13）**不再作为独立任务先行修复**。它们并入 media 磁盘型重建（PT-ARCH-18）统一修复：
- `deep_clone` 改为按存储模型分发——磁盘型对象拷贝路径引用，不再"深拷贝字节"。
- 序列化器增加磁盘型分支——序列化路径引用，不再"序列化字节"。
- bug 在模型切换中**自然消解**，而非被打补丁。

项目负责人明确：**不允许过渡/简易修复**。在 PT-ARCH-17/18 完成前，media 在 snapshot/serialize 下"静默丢失"的现状**作为已知限制保留**（媒体目前仅 MOCK 可用、零生产路径 hit、零序列化测试覆盖，回归风险为理论性）。

### 对其他 ADR 的传导
- **ADR-013 修订**：其"内部分支"决策被本 ADR 第 3 条取代——分发改为协议驱动。supersede ADR-009 的核心结论（单入口、单策略、无 `execute_*` 分叉）仍然成立。
- **ADR-014 修订**：`MemoryBacking` 砍除；存储模型升为类型级（本 ADR）；`MediaStorage` 整体淘汰获批准。
- **ADR-015 不变**：路径统一仍是磁盘型变量的前置 gate。

### 命名治理
- "Inter 层"即日起停用。文档接触时改写为"变量存储模型"或具体协议族名。
- IBCI 仍可保留 "Intent-Behavior-Code-Inter" 的产品名定位（Inter 表"交互"），但**不再作为协议层的命名**。

### 阻塞
- 本 ADR 的实现（PT-ARCH-17 / PT-ARCH-23 G3-G6）**阻塞于 ADR-015**（路径统一）。
- media 重建（PT-ARCH-18）**阻塞于** PT-ARCH-17。
- **协同 ADR-021**（2026-07-17）：`storage_model` 的**枚举类型**（`StorageModel`：MEMORY_BACKED/DISK_BACKED）已在 **PT-ARCH-23 G1.5** 提前落地为 `IbSpec` 一等字段（默认 `MEMORY_BACKED`），但**仅落字段不落分发逻辑**；本 ADR 的磁盘协议族 + deep_clone/序列化器分发仍在 G3（PT-ARCH-23 阶段 5）真正启用该字段。

## 改动面（实现期，分阶段）
详见 `docs/PENDING_TASKS.md §九` PT-ARCH-17（磁盘模型基础设施）与 PT-ARCH-18（media 重建）。
