# ADR-009: _call_llm_raw introduction (D6/DEC-4 reconciliation)

## Status
Accepted (2026-06-24)

## Date
2026-06-24

## Context

Two contradictory decisions exist in the multimodal design doc:

- **D6** (§十一): "Don't change `_call_llm` return value contract (returns `str`)"
  — to ensure all text-only code paths are completely unaffected
- **DEC-4** (§C.6): "Phase 3 pre-reserve `_call_llm_raw`"
  — to avoid Phase 4 large-scale refactoring

Additionally, `COMPLETED.md:49` records "_call_llm_raw 待 Phase 4", meaning the
actual implementation deferred this to Phase 4.

The `_call_llm` method is called by `execute_behavior_expression` **before** the target
type is known. The axiom needs `target_type` to decide whether to use multimodal or
text-only response parsing. So the routing decision (str vs raw response) must happen
inside `_call_llm` or its caller — D6's "don't touch `_call_llm`" cannot literally hold.

Also, MOCK mode (`ibci_ai/core.py:357-360`) returns `str` via early-return before any
client path. To support `from_response` (Phase 4 multimodal), MOCK must be restructured
to fabricate a fake full-response object.

## Decision

1. **Phase 3 does NOT introduce `_call_llm_raw`** (confirming `COMPLETED.md:49`).
   Phase 3 multimodal types use the existing `_call_llm` → `str` path; multimodal
   payload is about INPUT (building structured content blocks), not OUTPUT parsing.

2. **Phase 4 introduces `_call_llm_multimodal`** as a new parallel path
   (not replacing `_call_llm`). This aligns with D6's spirit (text-only paths unchanged)
   while providing the raw response access Phase 4 needs.

3. **Phase 4 MOCK restructure**: MOCK mode must be extended to return a synthetic
   full-response object for multimodal calls (not just `str`).

## Alternatives Considered

### Alternative A: Pre-reserve `_call_llm_raw` in Phase 3 (DEC-4 original recommendation)
- Pros: Avoids Phase 4 refactoring
- Cons: Phase 3 doesn't need it (multimodal Phase 3 is input-only); premature API surface
- Rejected: YAGNI; add it when Phase 4 actually needs it

### Alternative B: Change `_call_llm` to always return full response (break D6)
- Pros: Single path, no parallel methods
- Cons: Breaks all text-only downstream consumers; high regression risk
- Rejected: Violates D6's backward-compatibility guarantee

## Consequences

- Phase 3 implementation is simpler (no `_call_llm_raw` needed)
- Phase 4 must add `_call_llm_multimodal` + MOCK restructure
- D6 is preserved: text-only paths are genuinely unaffected in Phase 3
- `invoke_behavior_cps` in Phase 4 will branch on target_type multimodal capability
