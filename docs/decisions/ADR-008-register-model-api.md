# ADR-008: register_model API shape (D4 vtable alignment)

## Status
Accepted (2026-06-24)

## Date
2026-06-24

## Context

The multimodal design doc (`MULTIMODAL_BEHAVIOR_DESIGN.md` §5.2, §6.1, §10.1) shows
examples like:
```ibci
ai.register_model("GPT4o", {
    "base_url": "https://api.openai.com/v1",
    "api_key": env("OPENAI_KEY"),
    "model": "gpt-4o",
    "modalities": ["text", "audio", "image"]
})
```

But the actual implementation (`ibci_modules/ibci_ai/core.py:113`) has signature:
```python
def register_model(self, name: str, url: str, key: str, model: str, **kwargs):
```

And the vtable (`_spec.py:22`) declares `param_types: ["str","str","str","str"]`,
which means the compiler **rejects dict-based calls**. All Phase 3+ multimodal
examples in the design doc are uncompilable.

Additionally, §10.2 `_dispatch_call` branches on `config.endpoint == "audio/transcriptions"`,
but `register_model` doesn't store an `endpoint` field.

## Decision

1. **Extend `register_model` to accept `**kwargs` for modalities/endpoint/audio_config**.
   The current 4-positional-str signature remains backward-compatible; new fields are
   passed as keyword arguments and stored in the model registry entry.

2. **Update the vtable** to declare the extended signature with optional dict parameter,
   OR keep 4-string positional + accept kwargs through the IBCI `dict` parameter type.

3. **Store `modalities`, `endpoint`, `audio_config`** in the `_model_registry` entry
   so `_dispatch_call` can access them.

4. **Update all design doc examples** to use the actual API shape:
```ibci
ai.register_model("GPT4o", "https://api.openai.com/v1", env("OPENAI_KEY"), "gpt-4o")
```
(4 positional strings, matching the vtable)

## Alternatives Considered

### Alternative A: Change register_model to accept a single dict parameter
- Pros: Matches design doc examples
- Cons: Breaks backward compatibility with Phase 1; IBCI dict parameter typing is
  less safe than 4 explicit strings
- Rejected: Backward compat matters; Phase 1 already shipped

### Alternative B: Add a new `register_multimodal_model` function
- Pros: Clean separation between text-only and multimodal registration
- Cons: API surface growth; users need to know which function to call
- Rejected: Unnecessary complexity; kwargs on existing function is sufficient

## Consequences

- Phase 3 implementation must update the vtable and `register_model` to accept kwargs
- Design doc examples must be corrected to match the actual API
- `_dispatch_call` can access endpoint/modalities from the registry entry
- Mock mode must be extended to handle multimodal-specific config fields
