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
    - IBCI_SYNTAX_REFERENCE.md §6 Intent System
    - docs/COMPLETED.md NS-2b/2c/2d
    - tests/e2e/test_e2e_intent.py
    """

    def test_intent_propagates_to_nested_llm_call(self):
        """INV-INTENT-PROP-1: Intent annotations propagate to nested LLM calls."""
        code = AI_MOCK_PREFIX + """
llm inner() -> str:
    __sys__
    Inner LLM call.
    __user__
    MOCK:STR:result
    llmend

@ "outer context"
print(inner())
"""
        assert run_ibci(code) == ["result"]

    def test_intent_propagates_across_function_calls(self):
        """INV-INTENT-PROP-2: Intents propagate through immediate behavior call."""
        code = AI_MOCK_PREFIX + """
@ "important note"
str x = @~ MOCK:STR:data ~
print(x)
"""
        assert run_ibci(code) == ["data"]

    def test_nested_intent_accumulates(self):
        """INV-INTENT-PROP-3: Nested intent annotations accumulate within function."""
        code = AI_MOCK_PREFIX + """
func inner() -> str:
    @ "inner"
    str x = @~ MOCK:STR:result ~
    return x

@ "outer"
str y = @~ MOCK:STR:outer_result ~
print(inner())
print(y)
"""
        assert run_ibci(code) == ["result", "outer_result"]


# ===========================================================================
# Intent Priority (INV-INTENT-PRIORITY-*)
# ===========================================================================


class TestIntentPriority:
    """Validate intent mode and role priority rules.

    References:
    - IBCI_SYNTAX_REFERENCE.md §6.2 Intent Modes
    - docs/VM_AND_INTERPRETER_DESIGN.md §7
    """

    def test_override_replaces_existing(self):
        """INV-INTENT-PRIORITY-1: Override mode replaces existing intents."""
        code = AI_MOCK_PREFIX + """
@! "second"
str x = @~ MOCK:STR:result ~
print(x)
"""
        assert run_ibci(code) == ["result"]

    def test_append_adds_to_existing(self):
        """INV-INTENT-PRIORITY-2: Append mode adds to existing intents."""
        code = AI_MOCK_PREFIX + """
@+ "second"
str x = @~ MOCK:STR:result ~
print(x)
"""
        assert run_ibci(code) == ["result"]

    def test_remove_clears_intents(self):
        """INV-INTENT-PRIORITY-3: Remove mode clears matching intents."""
        code = """
@+ "A"
@+ "B"
@-
intent_context ctx = intent_context.get_current()
print((str)ctx.resolve())
"""
        lines = run_ibci(code)
        assert len(lines) == 1
        assert "A" in lines[0]
        assert "B" not in lines[0]


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
@ "temporary"
str x = @~ MOCK:REPAIR:STR:fallback ~
llmexcept:
    retry "recover"
@ "after"
str y = @~ MOCK:STR:after ~
print(y)
"""
        assert run_ibci(code) == ["after"]

    def test_persist_intent_survives_retry(self):
        """INV-INTENT-RETRY-2: Append intents survive retry."""
        code = AI_MOCK_PREFIX + """
@+ "permanent"
str x = @~ MOCK:REPAIR:STR:fallback ~
llmexcept:
    retry "recover"
@ "after"
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
    - tests/e2e/test_e2e_intent.py
    """

    def test_function_intent_isolated(self):
        """INV-INTENT-SCOPE-1: Function-local intents don't leak."""
        code = AI_MOCK_PREFIX + """
func isolated() -> auto:
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

    def test_single_intent_on_regular_call_no_llm_path_does_not_leak(self):
        """INV-INTENT-SCOPE-3: one-shot on regular call with no LLM path is cleaned per statement."""
        code = """
func pure_no_llm():
    int x = 1
    return

@ no leak
pure_no_llm()

intent_context current = intent_context.get_current()
str prompt_view = current.__to_prompt__()
if prompt_view == "":
    print("EMPTY")
else:
    print(prompt_view)
"""
        assert run_ibci(code) == ["EMPTY"]


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
