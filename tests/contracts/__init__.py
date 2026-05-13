"""
tests/contracts/__init__.py
============================

Contract tests: Validate IBCI semantic invariants.

This layer tests the **language's public guarantees** (type safety, execution model,
scope semantics, intent propagation, llmexcept behavior, LLM integration), NOT
implementation details.

Contract tests:
- Use minimal IBCI code (5-15 lines)
- Assert observable behavior, not internal state
- Avoid accessing interpreter internals (node_pool, side_table, etc.)
- Use parametrized tests to cover multiple cases
- Each test validates ONE semantic invariant

See docs/TEST_PHILOSOPHY.md for detailed guidelines.
"""
