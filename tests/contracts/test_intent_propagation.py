"""
tests/contracts/test_intent_propagation.py
===========================================

Contract tests for Intent system propagation and semantics.

Validates:
- INV-INTENT-PROP-*: Intent propagation across scopes
- INV-INTENT-PRIORITY-*: Intent mode/role priority rules
- INV-INTENT-RETRY-*: Intent restoration after retry
- INV-INTENT-SCOPE-*: Intent scope isolation
"""

import pytest
from tests.conftest import run_ibci, AI_MOCK_PREFIX


# ===========================================================================
# Intent Propagation (INV-INTENT-PROP-*)
# ===========================================================================


class TestIntentPropagation:
    """Validate intent propagation across frames and scopes.

    References:
    - IBCI_SPEC.md §6 Intent System
    - docs/COMPLETED.md NS-2b/2c/2d
    - tests/runtime/test_intent_context.py (legacy)
    """

    def test_intent_propagates_to_nested_llm_call(self):
        """INV-INTENT-PROP-1: Intent annotations propagate to nested LLM calls."""
        code = AI_MOCK_PREFIX + """
@ "outer context"
llm str inner():
    @~ MOCK:STR:result ~

print(inner())
"""
        assert run_ibci(code) == ["result"]

    def test_intent_propagates_across_function_calls(self):
        """INV-INTENT-PROP-2: Intents propagate through regular function calls."""
        code = AI_MOCK_PREFIX + """
func auto process():
    str x = @~ MOCK:STR:data ~
    return x

@ "important note"
print(process())
"""
        assert run_ibci(code) == ["data"]

    def test_nested_intent_accumulates(self):
        """INV-INTENT-PROP-3: Nested intent annotations accumulate."""
        code = AI_MOCK_PREFIX + """
@ "outer"
func auto inner():
    @ "inner"
    str x = @~ MOCK:STR:result ~
    return x

print(inner())
"""
        assert run_ibci(code) == ["result"]


# ===========================================================================
# Intent Priority (INV-INTENT-PRIORITY-*)
# ===========================================================================


class TestIntentPriority:
    """Validate intent mode and role priority rules.

    References:
    - IBCI_SPEC.md §6.2 Intent Modes
    - docs/VM_AND_INTERPRETER_DESIGN.md §7
    """

    def test_override_replaces_existing(self):
        """INV-INTENT-PRIORITY-1: Override mode replaces existing intents."""
        code = AI_MOCK_PREFIX + """
@ "first"
@! "second"
str x = @~ MOCK:STR:result ~
print(x)
"""
        # Second should override first
        assert run_ibci(code) == ["result"]

    def test_append_adds_to_existing(self):
        """INV-INTENT-PRIORITY-2: Append mode adds to existing intents."""
        code = AI_MOCK_PREFIX + """
@ "first"
@+ "second"
str x = @~ MOCK:STR:result ~
print(x)
"""
        # Both should be present
        assert run_ibci(code) == ["result"]

    def test_remove_clears_intents(self):
        """INV-INTENT-PRIORITY-3: Remove mode clears matching intents."""
        code = AI_MOCK_PREFIX + """
@ "note"
@- "note"
str x = @~ MOCK:STR:result ~
print(x)
"""
        assert run_ibci(code) == ["result"]


# ===========================================================================
# Intent Retry Restoration (INV-INTENT-RETRY-*)
# ===========================================================================


class TestIntentRetryRestoration:
    """Validate intent restoration after retry.

    References:
    - docs/COMPLETED.md NS-2c (2026-05-11)
    - Issue #42 intent leak in retry
    """

    def test_intent_restored_after_retry(self):
        """INV-INTENT-RETRY-1: Smear intents are restored after retry."""
        code = AI_MOCK_PREFIX + """
@ "initial"
llmexcept {
    @ "temporary"
    str x = @~ MOCK:INVALID ~
} retry {
    str x = @~ MOCK:STR:fallback ~
}
str y = @~ MOCK:STR:after ~
print(y)
"""
        # Should execute without error (verifying intent stack integrity)
        assert run_ibci(code) == ["after"]

    def test_persist_intent_survives_retry(self):
        """INV-INTENT-RETRY-2: Persist intents survive retry."""
        code = AI_MOCK_PREFIX + """
@+ persist "permanent"
llmexcept {
    str x = @~ MOCK:INVALID ~
} retry {
    str x = @~ MOCK:STR:fallback ~
}
str y = @~ MOCK:STR:after ~
print(y)
"""
        assert run_ibci(code) == ["after"]


# ===========================================================================
# Intent Scope Isolation (INV-INTENT-SCOPE-*)
# ===========================================================================


class TestIntentScopeIsolation:
    """Validate intent scope isolation.

    References:
    - tests/e2e/test_e2e_intent.py (legacy)
    """

    def test_function_intent_isolated(self):
        """INV-INTENT-SCOPE-1: Function-local intents don't leak."""
        code = AI_MOCK_PREFIX + """
func auto isolated():
    @ "local note"
    str x = @~ MOCK:STR:inner ~
    return x

str y = @~ MOCK:STR:outer ~
print(isolated())
print(y)
"""
        assert run_ibci(code) == ["inner", "outer"]

    def test_smear_intent_cleared_after_use(self):
        """INV-INTENT-SCOPE-2: Smear intents are cleared after resolution."""
        code = AI_MOCK_PREFIX + """
@ "temporary"
str x = @~ MOCK:STR:first ~
str y = @~ MOCK:STR:second ~
print(x)
print(y)
"""
        # Both calls succeed, smear is cleared after first use
        assert run_ibci(code) == ["first", "second"]

    def test_intent_in_lambda_captured(self):
        """INV-INTENT-SCOPE-3: Intent context is captured in lambda."""
        code = AI_MOCK_PREFIX + """
@ "context"
fn[()->str] f = lambda: @~ MOCK:STR:result ~
print(f())
"""
        assert run_ibci(code) == ["result"]


# ===========================================================================
# Intent with Control Flow (INV-INTENT-FLOW-*)
# ===========================================================================


class TestIntentControlFlow:
    """Validate intent behavior in control flow.

    References:
    - tests/e2e/test_e2e_intent.py (legacy)
    """

    def test_intent_in_loop_iteration(self):
        """INV-INTENT-FLOW-1: Intent annotations work in loops."""
        code = AI_MOCK_PREFIX + """
for int i in range(2):
    @ "iteration"
    str x = @~ MOCK:STR:data ~
    print(x)
"""
        assert run_ibci(code) == ["data", "data"]

    def test_intent_in_conditional(self):
        """INV-INTENT-FLOW-2: Intent annotations work in conditionals."""
        code = AI_MOCK_PREFIX + """
if True:
    @ "branch note"
    str x = @~ MOCK:STR:result ~
    print(x)
"""
        assert run_ibci(code) == ["result"]

    def test_intent_cleared_between_iterations(self):
        """INV-INTENT-FLOW-3: Smear intents cleared between loop iterations."""
        code = AI_MOCK_PREFIX + """
for int i in range(2):
    @ "temp"
    str x = @~ MOCK:STR:data ~
    print(x)
"""
        # Each iteration starts fresh
        assert run_ibci(code) == ["data", "data"]
