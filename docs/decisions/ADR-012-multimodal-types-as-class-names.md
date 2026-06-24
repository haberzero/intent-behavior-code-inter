# ADR-012: Multimodal types as ordinary class names (DEC-1 resolution)

## Status
Accepted (2026-06-24)

## Date
2026-06-24

## Context

Phase 3 multimodal design decision DEC-1 asked whether `audio`/`image`/`video`/
`media` should be registered as **type keywords** (like `if`/`while`/`import` in
the KEYWORDS table) or as **ordinary class names** (like `Enum`, registered via
the axiom system + `builtin_initializer`).

The original recommendation in `MULTIMODAL_BEHAVIOR_DESIGN.md` §C.6 was
"keywords, same level as `str`/`int`". However, the adversarial review found
that `str`/`int` are **not** keywords — `core_scanner.py` KEYWORDS contains
only control-flow keywords (`import`/`func`/`if`/`class`/...); built-in scalar
types are resolved as ordinary identifiers via `SpecRegistry` and
`builtin_initializer`. The recommendation was based on a false premise.

Furthermore, `ARCHITECTURE_PRINCIPLES.md §九` states "99% 禁止硬编码关键字"
— adding 4 new keywords would violate this principle.

## Decision

**`audio`/`image`/`video`/`media` are registered as ordinary class names**,
not as lexer keywords.

Registration path:
1. Define `AudioAxiom`/`ImageAxiom`/`VideoAxiom`/`MediaAxiom` in
   `core/kernel/axioms/primitives/` (new files per type family)
2. Register axioms via `register_core_axioms()` in
   `core/kernel/axioms/primitives/registry.py`
3. `builtin_initializer.py` automatically creates `IbClass` instances from
   axiom specs (the standard path for all non-keyword built-in types)
4. `IbAudio`/`IbImage`/`IbVideo`/`IbMedia` runtime classes are bound via
   `@register_ib_type("audio")` etc. in `core/runtime/objects/`

This approach:
- Requires **zero** lexer/parser changes
- Is consistent with how `Enum`, `Exception`, `intent_context` and other
  built-in non-keyword types are registered
- Follows ARCHITECTURE_PRINCIPLES §九 (no hardcoded keywords)
- Minimizes blast radius (no KEYWORDS table, no TokenType additions, no
  parser grammar changes)

## Alternatives Considered

### Alternative A: Register as keywords (original DEC-1 recommendation)
- Pros: Explicit keyword status signals "language-level first-class type"
- Cons: Requires KEYWORDS table changes (`core_scanner.py`), TokenType additions
  (`tokens.py`), parser grammar changes (`declaration.py`), contradicts §九,
  based on false premise that str/int are keywords
- Rejected: str/int are not keywords; adding keywords violates §九; high blast
  radius for no benefit

### Alternative B: Hybrid — keywords for media, class names for audio/image/video
- Pros: `media` as keyword could enable special syntax (e.g., `media result = ...`)
- Cons: Inconsistent; `audio`/`image`/`video` are equally first-class; adds
  complexity without benefit
- Rejected: Unnecessary asymmetry

## Consequences

- Phase 3 implementation requires **no** lexer/parser changes
- Type registration follows the standard axiom → builtin_initializer path
- `audio`/`image`/`video`/`media` are usable as type annotations exactly like
  `str`/`int`/`list`/`dict` (which are also ordinary class names, not keywords)
- The `SpecRegistry` resolves these names through the same `resolve()` path
- Future type additions follow the same pattern (no grammar changes needed)
