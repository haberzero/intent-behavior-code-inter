# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records for the IBC-Inter project.

## What is an ADR?

An ADR captures the reasoning behind a significant technical decision — the context,
alternatives considered, and consequences. Code shows *what* was built; an ADR explains
*why it was built this way*.

## Naming Convention

```
ADR-NNN-short-kebab-title.md
```

## Template

```markdown
# ADR-NNN: Title

## Status
Accepted | Superseded by ADR-XXX | Revised | Deprecated

## Date
YYYY-MM-DD

## Context
What is the issue? What constraints apply? What problem are we solving?

## Decision
What did we decide? (1-3 sentences)

## Alternatives Considered
### Alternative A
- Pros: ...
- Cons: ...
- Rejected because: ...

### Alternative B
- Pros: ...
- Cons: ...
- Rejected because: ...

## Consequences
- What becomes easier?
- What becomes harder?
- What new constraints does this create?
```

## Index

> **关于编号 001~006**：ADR 制度于 2026-06-24（ADR-007 起）建立。001~006 对应的早期决策
> （CPS trampoline VM、公理系统、4-Phase 流水线、llmexcept 影子执行、TypeSlot 单次锁定、
> BUG #A 语义统一）发生在 ADR 制度建立之前，**未落盘为独立 ADR 文件**，其完整记录见
> `docs/HISTORY_LOG.md` 与 `docs/COMPLETED.md`。本索引不再为它们保留断链条目。

### Decided & Implemented
- [ADR-008: register_model API shape (D4 vtable alignment)](ADR-008-register-model-api.md)
- [ADR-010: Per-model capability probing (R5 endpoint strategy)](ADR-010-model-capability-probing.md)
- [ADR-011: runtime/shared/ leaf package for cycle breaking](ADR-011-runtime-shared-package.md)
- [ADR-012: Multimodal types as ordinary class names (DEC-1 resolution)](ADR-012-multimodal-types-as-class-names.md)

### Revised（已修订）
- [ADR-013: 统一响应解析（supersedes ADR-009）](ADR-013-unified-response-parsing.md) — 单一入口/单策略；**已修订**：去除标志位 `if/else`，改协议驱动分发（受 ADR-016 治理）。
- [ADR-014: media 存储为磁盘型 handle](ADR-014-media-storage-handle-backing.md) — FileBacking/GeneratedBacking；**已修订并已实施（2026-07-17）**：砍 MemoryBacking，存储模型升类型级，制动 MediaStorage 整体淘汰；`audio`/`image`/`video` 改为 `IbFileHandle` 子类，构造入口改为 `audio.from_file` / `image.from_file` / `video.from_file`。

### Superseded
- [ADR-009: _call_llm_raw introduction (D6/DEC-4 reconciliation)](ADR-009-call-llm-raw.md) — **Superseded by ADR-013**（2026-06-25）：核心前提被证伪，分叉路径被统一解析取代。

### Partially Superseded in Spirit
- [ADR-007: Multimodal snapshot strategy (DEC-5/DEC-6 reconciliation)](ADR-007-multimodal-snapshot-strategy.md) — 决策成立时基于"Phase 3 深拷贝 / Phase 5 才上磁盘"的二阶段划分；**该划分已被 ADR-014/ADR-016 推翻**（所有 media 一律 disk-backed handle，快照天然便宜）。其 isinstance bug 发现仍有历史价值，对应修复归属 `docs/PENDING_TASKS.md §九 PT-ARCH-17`。

### 路径系统与存储模型主线（ADR-015~021，路径系统已完成）

> 路径统一（ADR-015/017/018/019）与 PT-ARCH-23（ADR-016/020/021 + ADR-013/014 修订）已全部落地（2026-07-17）。变量存储模型、内核原生边界、类型化 flag 轴、file 模块 kernel-native 化、media disk-backed handle 均已完成。这些 ADR 共同构成 media Phase 4 的强制前置 gate，**非** media 决策本身。当前 gate 已解锁，media Phase 4 待项目负责人明确开工指令。

- [ADR-015: 路径系统统一为强制前置](ADR-015-path-system-unification-as-prerequisite.md) — media-as-handle 与 Phase 4 的前置 gate。
- [ADR-016: 变量存储模型 —— 类型级 memory/disk 区分 + 协议驱动分发](ADR-016-variable-storage-model.md) — **上层治理**：废弃"Inter 层"命名；确立 memory-backed / disk-backed 类型级区分；协议驱动分发；制动 MediaStorage 淘汰。ADR-013/014 据此修订。
- [ADR-017: 路径模块层位置重构 —— base/kernel/runtime 三层分工](ADR-017-path-module-layering.md) — **已实现（经 PT-ARCH-19）**：消除 compiler→runtime 违规；下沉路径模块（base 原子原语 / kernel IBCI 模型 / runtime 安装发现）；解锁 canonicalize_for_security / derive_isolated / SnapshotLayout。修正 P0-1 的 premature DONE。
- [ADR-018: 路径概念模型 —— 5 概念形式化 + 统一原则](ADR-018-path-concept-model.md) — **Partially Superseded by ADR-019**（2026-07-13）：5 概念形式化（CWD/main entry/project_root/child entry/child project_root）仍有效；但 D1（root 必填）、D5（标志分发）、CWD 上界不变量、D4 PathContext 穿透被 ADR-019 取代。
- [ADR-019: 路径与插件模型重设计 —— proj_root/plugin_path 分离 + 隔离语义修订](ADR-019-path-and-plugin-model-redesign.md) — **当前正本（2026-07-13）**：五概念分离（entry/proj_root/plugin_paths/CWD/builtin）；project_root 引擎级默认（=显式 OR entry_dir）；run_string 合成 entry `<proj_root>/__string_exec__.ibci`；plugin 优先级 builtin > global_plugin > plugin_paths > 嗅探 > 全局(预留)；隔离反转（子必须在父 proj_root 内）；plugin 只读特权；ibci.json 配置。取代 ADR-018 的 D1/D5/CWD 上界。
- [ADR-020: 内核原生 vs 插件边界重划 + FileHandle 磁盘型基类](ADR-020-kernel-native-vs-plugin-boundary.md) — **已实施（2026-07-17，PT-ARCH-23 G1.5/G2/G3-G6 全部落地）**：① 内核原生模块 = import-gated（可用性 vs 可见性两轴正交）；② FileHandle = 磁盘型基类，media 为子类，`ibci_modules/ibci_file/` 已删除；③ `file` 模块 kernel-native 化，`import file` 通过 `exported_types` 注入 `file_handle`/`audio`/`image`/`video`；④ PT-ARCH-24/26/27 安全闸门落地。协同 ADR-016/014/021；衍生命名清理 PT-ARCH-22 仍为后续窗口。
- [ADR-021: 类型化来源/可见性/存储轴 —— Provenance/Visibility/StorageModel 取代 IbSpec/Symbol 平 bool flag](ADR-021-typed-provenance-visibility-storage-axes.md) — **Accepted（2026-07-17，实现归属 G1.5）**：经碎片化审计（F1-F7 实证）收敛。① 三枚举取代 `is_user_defined` 重载（ADR-020 §A 正交轴落地）；② `Symbol.metadata` 来源键升级为类型化 `Symbol.provenance`，删 2 死字段；③ `symbols.py:147` 真值表→`Provenance.compatible_with`；④ `storage_model` 枚举提前就位（仅落字段，分发待 G3）。**修正** ADR-020 G2 的 `is_user_defined` 写法。
