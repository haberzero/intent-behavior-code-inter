# ADR-007: Multimodal snapshot strategy (DEC-5/DEC-6 reconciliation)

## Status
Accepted (2026-06-24) — **Partially superseded in spirit by ADR-014 / ADR-016**（2026-06-25）

> 本 ADR 决策成立时基于"Phase 3 用 deep-copy / MediaStorage 纯内存，Phase 5 才上磁盘"的二阶段划分。
> 该划分已被 ADR-016（所有 media 一律 disk-backed）+ ADR-014（media 为磁盘型 handle，砍 MemoryBacking）推翻：
> handle 使快照天然便宜，原"二阶段"不再成立。本 ADR 的 isinstance bug 发现仍有历史价值，
> 对应修复归属 `docs/PENDING_TASKS.md §九 PT-ARCH-17`（deep_clone `type(val) is` → `isinstance`）。
> 多模态类型的 `__snapshot__`/`__restore__` 设计被 ADR-016 第 5 条"平行协议族"取代。

## Date
2026-06-24

## Context

Phase 3 multimodal design has two contradictory decisions in `MULTIMODAL_BEHAVIOR_DESIGN.md`:

- **DEC-5**: `__snapshot__`/`__restore__` for multimodal variables should use **path references**
  (disk-backed), because "磁盘卸载后天然支持 snapshot"
- **DEC-6**: Phase 3 MediaStorage should use **pure memory** first, deferring disk offload
  to Phase 5

These are irreconcilable for Phase 3: media lives in memory, yet the snapshot design
commits to path references for a disk backend that doesn't exist yet.

Additionally, the snapshot dispatch at `llm_except_frame.py:199` uses `type(val) is IbObject`
(strict identity check, not `isinstance`). If `IbAudio`/`IbImage`/`IbVideo` are subclasses
of `IbObject` (the natural OO choice), neither the user-protocol branch nor the fallback
`deep_clone.py:89` branch matches → the variable is **silently skipped** in the snapshot,
and an llmexcept retry body that mutates it has no restore.

## Decision

1. **Phase 3 media snapshot uses deep-copy (in-memory)**, NOT path references.
   Path-reference snapshot is deferred to Phase 5 when disk offload exists.
   This resolves DEC-5 vs DEC-6: DEC-6 wins for Phase 3.

2. **Fix the snapshot dispatch to use `isinstance` instead of `type() is`**.
   `llm_except_frame.py:199` and `deep_clone.py:89` must use `isinstance(val, IbObject)`
   to correctly match subclasses like `IbAudio`.

3. **Multimodal types (`IbAudio`/`IbImage`/`IbVideo`) must implement `__snapshot__`/`__restore__`**
   explicitly, returning a serializable representation (e.g., raw bytes + metadata for
   in-memory, or file path for disk-backed in Phase 5).

## Alternatives Considered

### Alternative A: Path references in Phase 3 (DEC-5 as written)
- Pros: No deep-copy overhead for large media
- Cons: Requires disk offload in Phase 3 (contradicting DEC-6); temp file lifecycle
  under host checkpoints is unsolved; `type() is` dispatch would silently skip media
- Rejected: Contradicts DEC-6 and requires premature infrastructure

### Alternative B: No snapshot for media (skip silently)
- Pros: Simplest
- Cons: llmexcept retry bodies that read media variables would see stale or missing values
- Rejected: Violates llmexcept isolation semantics

## Consequences

- Phase 3 media types must implement deep-copy-able snapshot (small in-memory media is fine)
- `type() is` dispatch bug must be fixed before Phase 3 implementation
- Phase 5 can upgrade to path-reference snapshot when disk offload is available
- Large media (>10MB) in llmexcept-protected code will have snapshot overhead until Phase 5
