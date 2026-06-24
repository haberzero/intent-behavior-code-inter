# ADR-011: runtime/shared/ leaf package for cycle breaking

## Status
Accepted (2026-06-24)

## Date
2026-06-24

## Context

The runtime layer (`core/runtime/`) had three internal import cycles masked by
deferred (in-method) imports:

1. `interpreter ↔ vm`: interpreter imports `UnhandledSignal` from vm/task; vm/handlers
   imports constants and llm_result from interpreter
2. `objects ↔ interpreter`: objects/builtins imports `LLMResult` from interpreter;
   interpreter imports `IbObject` hierarchy from objects
3. `objects ↔ vm`: objects/kernel imports `ControlSignal`/`UnhandledSignal` from vm/task;
   vm/handlers imports `IbObject` hierarchy from objects

These cycles don't crash at import time (because the deferred imports are inside method
bodies, not at module top-level), but they make the runtime non-DAG and fragile to
import-order changes. Refactoring any of these modules risks triggering partial-initialization
errors.

## Decision

Create `core/runtime/shared/` as a universal leaf package containing types that multiple
runtime subpackages need:

- `shared/op_constants.py` — operator mapping dicts (from `interpreter/constants.py`)
- `shared/llm_result.py` — `LLMResult`/`LLMFuture` dataclasses (from `interpreter/llm_result.py`)
- `shared/signals.py` — `ControlSignal`/`Signal`/`UnhandledSignal` (extracted from `vm/task.py`)

All cross-package consumers now import from `shared/` instead of reaching across
interpreter/vm/objects. The original files are kept as backward-compat re-export shims.

`vm/task.py` keeps `VMTask`/`VMTaskResult` (VM-internal frame data) and re-exports the
signal types from `shared/signals.py` for intra-vm backward compatibility.

## Alternatives Considered

### Alternative A: Move everything to core/base/
- Pros: Foundation layer, importable by everything
- Cons: These are runtime-specific types (LLM results, VM signals), not general-purpose
  foundation types. Polluting base/ with runtime concerns violates layering.
- Rejected: Wrong conceptual layer

### Alternative B: Keep deferred imports as-is
- Pros: No code changes needed
- Cons: Cycles remain; future refactoring is fragile; deferred imports are a code smell
  that masks real coupling
- Rejected: The cycles are a structural debt that should be paid off

## Consequences

- `shared/` is a stdlib-only leaf: it imports nothing from interpreter/vm/objects at
  top-level (only one deferred import of `IbNone` in `LLMResult.unwrap()`)
- All three runtime cycles are eliminated
- Future refactoring within interpreter/vm/objects is safer
- The `shared/` package may grow if more shared leaf types are identified
