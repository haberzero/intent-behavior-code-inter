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

Examples:
- `ADR-001-cps-trampoline-vm-over-stack-vm.md`
- `ADR-002-axiom-system-over-python-inheritance.md`

## Template

```markdown
# ADR-NNN: Title

## Status
Accepted | Superseded by ADR-XXX | Deprecated

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

### Historical Decisions (retroactive ADRs)
- [ADR-001: CPS trampoline VM over stack-based VM](ADR-001-cps-trampoline-vm.md)
- [ADR-002: Axiom system over Python inheritance](ADR-002-axiom-system-over-inheritance.md)
- [ADR-003: 7-Pass to 4-Phase semantic pipeline consolidation](ADR-003-4-phase-pipeline.md)
- [ADR-004: llmexcept shadow-execution over exception-throwing](ADR-004-llmexcept-shadow-execution.md)
- [ADR-005: TypeSlot single-lock over HM-style type inference](ADR-005-typeslot-single-lock.md)

### Recent Decisions
- [ADR-006: LLM condition uncertainty raises LLMParseError (BUG #A fix)](ADR-006-llm-parse-error-unification.md)

### Pending Decisions (Phase 3 multimodal blockers)
- [ADR-007: Multimodal snapshot strategy (DEC-5/DEC-6 reconciliation)](ADR-007-multimodal-snapshot-strategy.md)
- [ADR-008: register_model API shape (D4 vtable alignment)](ADR-008-register-model-api.md)
- [ADR-009: _call_llm_raw introduction (D6/DEC-4 reconciliation)](ADR-009-call-llm-raw.md)
- [ADR-010: Per-model capability probing (R5 endpoint strategy)](ADR-010-model-capability-probing.md)

### Infrastructure Decisions
- [ADR-011: runtime/shared/ leaf package for cycle breaking](ADR-011-runtime-shared-package.md)
- [ADR-012: Multimodal types as ordinary class names (DEC-1 resolution)](ADR-012-multimodal-types-as-class-names.md)
