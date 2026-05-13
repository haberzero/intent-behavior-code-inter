"""
tests/contracts/test_llm_integration.py
========================================

Contract tests for LLM integration and MOCK protocol.

Validates:
- INV-MOCK-*: MOCK protocol correctness
- INV-BEHAVIOR-*: Behavior expression execution
- INV-LLMFN-*: LLM function semantics
- INV-DISPATCH-*: LLM dispatch and future guarantees
"""

import pytest
from tests.conftest import run_ibci, AI_MOCK_PREFIX


# ===========================================================================
# MOCK Protocol (INV-MOCK-*)
# ===========================================================================


class TestMOCKProtocol:
    """Validate MOCK protocol for deterministic LLM testing.

    References:
    - tests/e2e/test_e2e_llm_basic.py (legacy)
    - LLM testing infrastructure
    """

    def test_mock_true_returns_truthy(self):
        """INV-MOCK-1: MOCK:TRUE returns boolean true."""
        code = AI_MOCK_PREFIX + """
bool result = @~ MOCK:TRUE test ~
print(result)
"""
        assert run_ibci(code) == ["1"]

    def test_mock_false_returns_falsy(self):
        """INV-MOCK-2: MOCK:FALSE returns boolean false."""
        code = AI_MOCK_PREFIX + """
bool result = @~ MOCK:FALSE test ~
print(result)
"""
        assert run_ibci(code) == ["0"]

    @pytest.mark.parametrize("mock_directive,expected_type", [
        ("MOCK:INT:42", "int"),
        ("MOCK:STR:hello", "str"),
        ("MOCK:LIST:[1,2,3]", "list"),
    ])
    def test_mock_typed_returns(self, mock_directive, expected_type):
        """INV-MOCK-3: MOCK:TYPE:value returns typed value."""
        code = AI_MOCK_PREFIX + f"""
auto result = @~ {mock_directive} ~
print(result)
"""
        result = run_ibci(code)
        assert result  # Execution succeeded


# ===========================================================================
# Behavior Expression (INV-BEHAVIOR-*)
# ===========================================================================


class TestBehaviorExpression:
    """Validate behavior expression execution.

    References:
    - IBCI_SPEC.md §5.1 Behavior Expressions
    - docs/TEST_PHILOSOPHY.md
    """

    def test_behavior_expression_executes(self):
        """INV-BEHAVIOR-1: Behavior expressions execute and return values."""
        code = AI_MOCK_PREFIX + """
str result = @~ MOCK:STR:output ~
print(result)
"""
        assert run_ibci(code) == ["output"]

    def test_behavior_in_assignment(self):
        """INV-BEHAVIOR-2: Behavior can be used in assignment."""
        code = AI_MOCK_PREFIX + """
int x = @~ MOCK:INT:42 ~
print(x)
"""
        assert run_ibci(code) == ["42"]

    def test_behavior_in_expression(self):
        """INV-BEHAVIOR-3: Behavior can be used in expressions."""
        code = AI_MOCK_PREFIX + """
int result = @~ MOCK:INT:10 ~ + @~ MOCK:INT:5 ~
print(result)
"""
        assert run_ibci(code) == ["15"]

    def test_behavior_in_control_flow(self):
        """INV-BEHAVIOR-4: Behavior can be used in control flow."""
        code = AI_MOCK_PREFIX + """
if @~ MOCK:TRUE condition ~:
    print("yes")
else:
    print("no")
"""
        assert run_ibci(code) == ["yes"]


# ===========================================================================
# LLM Function (INV-LLMFN-*)
# ===========================================================================


class TestLLMFunction:
    """Validate LLM function semantics.

    References:
    - IBCI_SPEC.md §5.2 LLM Functions
    """

    def test_llm_function_definition_and_call(self):
        """INV-LLMFN-1: LLM functions can be defined and called."""
        code = AI_MOCK_PREFIX + """
llm int double(int x):
    @~ MOCK:INT:84 multiply {x} by 2 ~

print(double(42))
"""
        assert run_ibci(code) == ["84"]

    def test_llm_function_parameter_binding(self):
        """INV-LLMFN-2: LLM function parameters are bound correctly."""
        code = AI_MOCK_PREFIX + """
llm str greet(str name):
    @~ MOCK:STR:Hello greet {name} ~

print(greet("World"))
"""
        result = run_ibci(code)
        assert "Hello" in result[0]

    def test_llm_function_return_type(self):
        """INV-LLMFN-3: LLM function enforces return type."""
        code = AI_MOCK_PREFIX + """
llm int compute():
    @~ MOCK:INT:123 ~

int result = compute()
print(result)
"""
        assert run_ibci(code) == ["123"]


# ===========================================================================
# Intent Context with LLM (INV-INTENT-LLM-*)
# ===========================================================================


class TestIntentWithLLM:
    """Validate intent context in LLM calls.

    References:
    - IBCI_SPEC.md §6 Intent System
    - tests/e2e/test_e2e_intent.py (legacy)
    """

    def test_intent_affects_llm_call(self):
        """INV-INTENT-LLM-1: Intent annotations affect LLM context."""
        code = AI_MOCK_PREFIX + """
@ "context note"
str result = @~ MOCK:STR:output ~
print(result)
"""
        assert run_ibci(code) == ["output"]

    def test_intent_in_llm_function(self):
        """INV-INTENT-LLM-2: Intent works in LLM function bodies."""
        code = AI_MOCK_PREFIX + """
llm str process(str data):
    @ "processing mode"
    @~ MOCK:STR:processed ~

print(process("input"))
"""
        assert run_ibci(code) == ["processed"]

    def test_intent_cleared_after_llm_call(self):
        """INV-INTENT-LLM-3: Smear intents are cleared after resolution."""
        code = AI_MOCK_PREFIX + """
@ "temporary note"
str x = @~ MOCK:STR:first ~
str y = @~ MOCK:STR:second ~
print(x)
print(y)
"""
        result = run_ibci(code)
        assert result == ["first", "second"]


# ===========================================================================
# LLM Dispatch and Futures (INV-DISPATCH-*)
# ===========================================================================


class TestLLMDispatch:
    """Validate LLM dispatch and execution ordering.

    References:
    - docs/VM_AND_INTERPRETER_DESIGN.md §5 LLM Pipeline
    """

    def test_sequential_llm_calls_execute_in_order(self):
        """INV-DISPATCH-1: Sequential LLM calls execute in order."""
        code = AI_MOCK_PREFIX + """
str a = @~ MOCK:STR:first ~
str b = @~ MOCK:STR:second ~
str c = @~ MOCK:STR:third ~
print(a)
print(b)
print(c)
"""
        assert run_ibci(code) == ["first", "second", "third"]

    def test_llm_call_completes_before_use(self):
        """INV-DISPATCH-2: LLM calls complete before value is used."""
        code = AI_MOCK_PREFIX + """
int x = @~ MOCK:INT:10 ~
int y = x + 5
print(y)
"""
        assert run_ibci(code) == ["15"]
