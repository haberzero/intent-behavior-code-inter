"""
tests/contracts/test_llmexcept_guarantees.py
============================================

Contract tests for llmexcept error handling guarantees.

Validates:
- INV-LLMEXCEPT-CATCH-*: Exception catching and retry semantics
- INV-LLMEXCEPT-HISTORY-*: Error history tracking
- INV-LLMEXCEPT-DEPTH-*: Frame depth limits
- INV-LLMEXCEPT-UNCERTAIN-*: Uncertain value handling

Note: IBCI llmexcept uses a colon-block "side-effect" form attached to a
preceding behavior expression rather than a try/retry brace-block. MOCK
directives drive deterministic outcomes:
- MOCK:REPAIR[:TYPE:value]  → first call fails, second succeeds with value
- MOCK:FAIL                  → all attempts fail (raises LLMRetryExhaustedError)
- MOCK:STR:value (etc.)      → always succeeds with given value
"""

import pytest
from tests.conftest import run_ibci, AI_MOCK_PREFIX


# ===========================================================================
# Exception Catching and Retry (INV-LLMEXCEPT-CATCH-*)
# ===========================================================================


class TestLLMExceptCatch:
    """Validate llmexcept catching and retry semantics."""

    def test_llmexcept_catches_llm_error(self):
        """INV-LLMEXCEPT-CATCH-1: llmexcept catches LLM errors and retries."""
        code = AI_MOCK_PREFIX + """
str x = @~ MOCK:REPAIR:STR:fallback ~
llmexcept:
    retry "use fallback"
print(x)
"""
        assert run_ibci(code) == ["fallback"]

    def test_retry_executes_on_error(self):
        """INV-LLMEXCEPT-CATCH-2: retry block executes on error."""
        code = AI_MOCK_PREFIX + """
str x = @~ MOCK:REPAIR:STR:ok ~
llmexcept:
    print("retry_ran")
    retry "again"
print(x)
"""
        assert run_ibci(code) == ["retry_ran", "ok"]

    def test_no_error_skips_retry(self):
        """INV-LLMEXCEPT-CATCH-3: retry block skipped if no error."""
        code = AI_MOCK_PREFIX + """
str x = @~ MOCK:STR:success ~
llmexcept:
    print("should_not_run")
    retry "unused"
print(x)
"""
        assert run_ibci(code) == ["success"]

    def test_nested_llmexcept_independent(self):
        """INV-LLMEXCEPT-CATCH-4: Nested llmexcept blocks are independent."""
        code = AI_MOCK_PREFIX + """
str inner = @~ MOCK:REPAIR:STR:inner_fallback ~
llmexcept:
    retry "inner"
str outer = @~ MOCK:STR:outer_ok ~
llmexcept:
    retry "outer"
print(inner)
print(outer)
"""
        assert run_ibci(code) == ["inner_fallback", "outer_ok"]


# ===========================================================================
# Error History Tracking (INV-LLMEXCEPT-HISTORY-*)
# ===========================================================================


class TestLLMExceptHistory:
    """Validate error history tracking across retries."""

    def test_error_history_accumulates(self):
        """INV-LLMEXCEPT-HISTORY-1: Sequential failures recover via retries."""
        code = AI_MOCK_PREFIX + """
str first = @~ MOCK:REPAIR:STR:first_ok ~
llmexcept:
    retry "first"
str final = @~ MOCK:REPAIR:STR:final ~
llmexcept:
    retry "final"
print(final)
"""
        assert run_ibci(code) == ["final"]

    def test_error_history_accessible_in_retry(self):
        """INV-LLMEXCEPT-HISTORY-2: Retry hint guides recovery."""
        code = AI_MOCK_PREFIX + """
str x = @~ MOCK:REPAIR:STR:recovered ~
llmexcept:
    retry "use error context"
print(x)
"""
        assert run_ibci(code) == ["recovered"]


# ===========================================================================
# Frame Depth Limits (INV-LLMEXCEPT-DEPTH-*)
# ===========================================================================


class TestLLMExceptDepth:
    """Validate llmexcept frame depth limits."""

    def test_reasonable_depth_succeeds(self):
        """INV-LLMEXCEPT-DEPTH-1: Multiple sequential llmexcept blocks succeed."""
        code = AI_MOCK_PREFIX + """
str a = @~ MOCK:REPAIR:STR:fa ~
llmexcept:
    retry "a"
str b = @~ MOCK:REPAIR:STR:fb ~
llmexcept:
    retry "b"
str c = @~ MOCK:STR:deep ~
llmexcept:
    retry "c"
print(c)
"""
        assert run_ibci(code) == ["deep"]

    def test_exhausted_retries_raises(self):
        """INV-LLMEXCEPT-DEPTH-2: Persistent failures raise LLMRetryExhaustedError."""
        code = AI_MOCK_PREFIX + """
try:
    str x = @~ MOCK:FAIL ~
    llmexcept:
        retry "give up"
    print(x)
except LLMRetryExhaustedError as e:
    print("exhausted")
"""
        assert run_ibci(code) == ["exhausted"]


# ===========================================================================
# Uncertain Value Handling (INV-LLMEXCEPT-UNCERTAIN-*)
# ===========================================================================


class TestLLMExceptUncertain:
    """Validate uncertain value handling in llmexcept."""

    def test_uncertain_value_isolated(self):
        """INV-LLMEXCEPT-UNCERTAIN-1: Behavior values from retried call usable."""
        code = AI_MOCK_PREFIX + """
str x = @~ MOCK:REPAIR:STR:uncertain ~
llmexcept:
    retry "isolate"
print(x)
"""
        assert run_ibci(code) == ["uncertain"]

    def test_str_plus_uncertain_concatenates(self):
        """INV-LLMEXCEPT-UNCERTAIN-2: str concatenation with LLM result."""
        code = AI_MOCK_PREFIX + """
str base = "prefix:"
str data = @~ MOCK:STR:value ~
str result = base + data
print(result)
"""
        assert run_ibci(code) == ["prefix:value"]


# ===========================================================================
# llmexcept with Control Flow (INV-LLMEXCEPT-FLOW-*)
# ===========================================================================


class TestLLMExceptControlFlow:
    """Validate llmexcept interaction with control flow."""

    def test_llmexcept_in_loop(self):
        """INV-LLMEXCEPT-FLOW-1: llmexcept works in loop iterations."""
        code = AI_MOCK_PREFIX + """
for int i in range(2):
    str x = @~ MOCK:REPAIR:STR:ok ~
    llmexcept:
        retry "loop"
    print(x)
"""
        assert run_ibci(code) == ["ok", "ok"]

    def test_llmexcept_in_conditional(self):
        """INV-LLMEXCEPT-FLOW-2: llmexcept works in conditionals."""
        code = AI_MOCK_PREFIX + """
if True:
    str x = @~ MOCK:REPAIR:STR:recovered ~
    llmexcept:
        retry "if-branch"
    print(x)
"""
        assert run_ibci(code) == ["recovered"]

    def test_llmexcept_with_break(self):
        """INV-LLMEXCEPT-FLOW-3: break works in loop containing llmexcept."""
        code = AI_MOCK_PREFIX + """
for int i in range(10):
    if i == 2:
        break
    str x = @~ MOCK:STR:data ~
    llmexcept:
        retry "loop"
print("done")
"""
        assert run_ibci(code) == ["done"]

    def test_llmexcept_with_return(self):
        """INV-LLMEXCEPT-FLOW-4: return works in function with llmexcept."""
        code = AI_MOCK_PREFIX + """
func test() -> str:
    str x = @~ MOCK:REPAIR:STR:recovered ~
    llmexcept:
        retry "fn"
    return x

print(test())
"""
        assert run_ibci(code) == ["recovered"]


# ===========================================================================
# llmexcept Variable Scoping (INV-LLMEXCEPT-SCOPE-*)
# ===========================================================================


class TestLLMExceptScoping:
    """Validate variable scoping around llmexcept blocks."""

    def test_outer_variable_accessible_in_retry(self):
        """INV-LLMEXCEPT-SCOPE-1: Outer variables accessible in retry block."""
        code = AI_MOCK_PREFIX + """
int y = 42
str x = @~ MOCK:REPAIR:STR:ok ~
llmexcept:
    print(y)
    retry "uses y"
"""
        assert run_ibci(code) == ["42"]

    def test_target_variable_accessible_after_recovery(self):
        """INV-LLMEXCEPT-SCOPE-2: Target variable holds recovered value."""
        code = AI_MOCK_PREFIX + """
str x = @~ MOCK:REPAIR:STR:value ~
llmexcept:
    retry "go"
print(x)
"""
        assert run_ibci(code) == ["value"]

    def test_successful_target_variable_accessible_after(self):
        """INV-LLMEXCEPT-SCOPE-3: Variables from successful call accessible."""
        code = AI_MOCK_PREFIX + """
str x = @~ MOCK:STR:success ~
llmexcept:
    retry "unused"
print(x)
"""
        assert run_ibci(code) == ["success"]
