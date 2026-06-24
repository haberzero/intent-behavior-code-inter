# ADR-010: Per-model capability probing (R5 endpoint strategy)

## Status
Accepted (2026-06-24)

## Date
2026-06-24

## Context

Phase 1 decision R5 deferred per-named-model capability probing. The fallback behavior
(`ibci_ai/core.py:397-402`) sets `is_reasoning_model = True` for every unprobed named model.

This is semantically destructive for non-chat endpoints:
- `@WHISPER~` (a transcription model) gets the reasoning-strategy prompt injected
  (`core.py:408` appends "You MUST output your final…starting with 'ANSWER:'")
- This corrupts pure transcription calls to `audio/transcriptions` endpoints
- The failure surfaces only on a real billed API call

Phase 3 multimodal will introduce more non-chat endpoints (`audio/transcriptions`,
`images/generations`), making this a critical issue.

## Decision

1. **Named models registered with an `endpoint` field** bypass reasoning-strategy
   prompt injection entirely. If `config.endpoint` is set to a non-chat endpoint
   (e.g., `"audio/transcriptions"`, `"images/generations"`), `is_reasoning_model`
   is forced to `False`.

2. **Named models without an `endpoint` field** (default chat endpoint) retain the
   current behavior: `is_reasoning_model = True` as the conservative default.

3. **Phase 3 implementation** must update `register_model` to accept and store the
   `endpoint` field (see ADR-008), and `__call__` must check it before applying
   reasoning-strategy prompts.

## Alternatives Considered

### Alternative A: Probe every named model's capabilities
- Pros: Most accurate
- Cons: Adds network latency on first call; requires capability API support from
  provider (not all providers have this); complex error handling
- Rejected: Overkill for Phase 3; endpoint-based dispatch is sufficient

### Alternative B: Remove reasoning-strategy prompt entirely for named models
- Pros: Simplest
- Cons: Chat models that benefit from reasoning strategy (e.g., GPT-4o for complex
  reasoning tasks) lose the optimization
- Rejected: Too aggressive; endpoint-based opt-out is better

## Consequences

- Non-chat endpoints (Whisper, DALL-E) will no longer receive reasoning-strategy prompts
- Chat models registered without an endpoint field are unaffected (backward compatible)
- `register_model` must store the `endpoint` field (ties to ADR-008)
- Phase 3 multimodal tests must verify endpoint-based dispatch
