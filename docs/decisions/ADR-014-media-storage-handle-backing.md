# ADR-014: media 存储为磁盘型 handle（受 ADR-016 治理，修订版）

## Status
Accepted (2026-06-25 修订；2026-07-17 随 PT-ARCH-23 G3-G6 实施完成)

**修订记录**：本 ADR 初版（2026-06-25）提出 FileBacking / GeneratedBacking / **MemoryBacking** 三选项，并把存储模型视为 media 的实现细节。经第三轮研讨，项目负责人要求：(1) 所有 media 一律磁盘型，**砍除 MemoryBacking**；(2) 存储模型升为**类型级一等区分**；(3) **整体淘汰** `MediaStorage`。修订版据此重写，并受 **ADR-016（变量存储模型）** 上层治理。

**阻塞于**：ADR-015（路径系统统一）+ ADR-016（变量存储模型框架实现 PT-ARCH-17）。

## Date
2026-06-25

## Context

Phase 3 把媒体（`audio`/`image`/`video`）实现为**纯内存字节**（`MediaStorage` 持有 `bytes`）。2026-06-25 审计发现该模型是"哑的"——两个潜伏 bug 致字节在 llmexcept 快照与 save_state 下静默丢失；且对文件来源不诚实（拷贝已在磁盘上的字节）。

经三轮研讨，项目负责人确立了**变量存储模型**框架（ADR-016）：类型显式区分 memory-backed / disk-backed；**所有 media 一律 disk-backed**；磁盘型变量是路径引用 handle；分发协议驱动。本 ADR 是该框架在 media 类型上的具体应用。

## Decision

### 1. media 类型一律为 disk-backed（无 MemoryBacking 选项）
`audio`/`image`/`video`/`media` 全部声明 `storage_model = disk-backed`。不存在内存型 media，不存在 `MemoryBacking`。

### 2. media 变量是路径引用 handle
```
IbAudio / IbImage / IbVideo / IbMedia   （用户可见 handle；disk-backed 身份对象）
    │  - 在 deep_clone 中按 disk-backed 协议分发（拷贝路径引用，浅、廉价）
    │  - 序列化为路径引用描述符；恢复期经统一路径系统重解析
    │  - identity-object opt-out（同 IbNativeObject 先例）
    │
    └── backing: 磁盘型 backing（实现细节，对用户透明）
          ├── FileBacking(path: IbPath)       # 指向已存在的源文件（file.read_*，零拷贝）
          └── GeneratedBacking(path: IbPath)  # 指向 LLM 生成时溢写的工件
```

字节**惰性物化**——仅在 LLM I/O 协议（磁盘型协议族，见 ADR-016 第 5 条）需要时从路径读取。

### 3. 来源感知
- `audio.from_file(path)` / `image.from_file(path)` / `video.from_file(path)` → `FileBacking(resolved_path)`，**不立即读字节**（零拷贝）。旧 `ibci_file.read_audio/read_image/read_video` 已随 `ibci_modules/ibci_file/` 删除而移除。
- `MediaAxiom.from_response`（响应解析，协议驱动分发，media Phase 4 实现）→ 把 LLM 返回的二进制溢写到 project_root 下媒体缓存目录，产出 `GeneratedBacking(path)`。
- 小数据不享受"内存豁免"——所有 media 一视同仁为磁盘型（项目负责人明确要求）。

### 4. 整体制动淘汰 `MediaStorage`
`MediaStorage`（字节持有者）是"内存型 media"模型的化身，与第 1 条直接矛盾。本 ADR 正式批准淘汰：
- `core/runtime/objects/media_storage.py` —— **删除**
- `core/runtime/objects/media_types.py` —— **替换**为磁盘型 handle 类（`IbAudio`/`IbImage`/`IbVideo` 继承 `IbFileHandle`）
- `core/kernel/axioms/primitives/media.py` 的 `__payload_prompt__` —— 改为从 backing 惰性物化
- `ibci_modules/ibci_file/` —— **整目录删除**；媒体读取入口改为 `audio.from_file` / `image.from_file` / `video.from_file`
- 既有 `MediaStorage` 单测 —— 替换为磁盘型 handle 的契约测试

## Alternatives Considered

### Alternative A：保留 `MemoryBacking` 作为小数据豁免（初版方案）
- Pros：小数据避免磁盘 I/O
- Cons：项目负责人明确禁止——所有 media 一律磁盘型；该选项制造歧义与过渡代码
- Rejected：违反硬要求

### Alternative B：把存储模型做成 media 的实现细节（初版方案）
- Pros：改动局限在 media 子系统
- Cons：项目负责人要求存储模型升为类型级、与内存类平行、专门建模（ADR-016）
- Rejected：未达到要求的建模层级

### Alternative C：把 media 改成磁盘型但保留 `MediaStorage` 作"字节视图"
- Pros：复用既有代码
- Cons：是兼容层/胶水实现，违反工作模式定论
- Rejected：明令禁止过渡方案

## Consequences

- **潜伏 bug 的处置**：PT-ARCH-12（`deep_clone.py:89`）/ PT-ARCH-13（序列化器）**不再独立先行修复**。它们并入 media 磁盘型重建（PT-ARCH-18）统一修复——deep_clone/序列化器改为按存储模型分发，bug 在模型切换中自然消解。**不允许过渡修复**（项目负责人明确指令）。
- **ADR-007 在精神上被进一步取代**：handle 使快照天然便宜；"Phase 3 深拷贝"与"Phase 5 才上磁盘"的二阶段划分失去意义。`type() is` → `isinstance` 的修复要求并入 PT-ARCH-17（磁盘型基础设施改造 deep_clone 时一并完成）。
- **阻塞链**：本 ADR → 阻塞于 ADR-016 实现（PT-ARCH-17）→ 阻塞于 ADR-015（路径统一）。
- 设计文档 `MULTIMODAL_BEHAVIOR_DESIGN.md` §4.3 / §十一-D3 中"`MediaStorage.location` 返回 `memory | disk:/path`"的 stringly-typed 第三套路径格式**被否决**——backing 路径必须是 `IbPath`。

## 改动面（已实施，PT-ARCH-18 作为 PT-ARCH-23 阶段 5 的一部分）
新建 `core/runtime/objects/media_backing.py`（`MediaBacking` 抽象 + `FileBacking`/`GeneratedBacking`）；重写 `media_types.py` 为磁盘型 handle；改写 `axioms/primitives/media.py` 的物化逻辑；物理删除 `ibci_modules/ibci_file/`；删 `media_storage.py`；改序列化器与 deep_clone 的 media 分支（按 PT-ARCH-17 确立的存储模型分发）。media 构造入口改为 `audio.from_file` / `image.from_file` / `video.from_file`。
