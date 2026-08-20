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
from tests.conftest import run_ibci, AI_MOCK_PREFIX, expect_runtime_error


# ===========================================================================
# MOCK Protocol (INV-MOCK-*)
# ===========================================================================


class TestMOCKProtocol:
    """Validate MOCK protocol for deterministic LLM testing.

    References:
    - LLM testing infrastructure
    """

    def test_mock_true_returns_truthy(self):
        """INV-MOCK-1: MOCK:TRUE returns boolean true."""
        code = AI_MOCK_PREFIX + """
bool result = @~ MOCK:TRUE test ~
print(result)
"""
        assert run_ibci(code) == ["True"]

    def test_mock_false_returns_falsy(self):
        """INV-MOCK-2: MOCK:FALSE returns boolean false."""
        code = AI_MOCK_PREFIX + """
bool result = @~ MOCK:FALSE test ~
print(result)
"""
        assert run_ibci(code) == ["False"]

    @pytest.mark.parametrize("mock_directive,expected_value", [
        ("MOCK:INT:42", "42"),
        ("MOCK:STR:hello", "hello"),
        ("MOCK:LIST:[1,2,3]", "[1,2,3]"),
        ("MOCK:FLOAT:3.14", "3.14"),
    ])
    def test_mock_typed_returns(self, mock_directive, expected_value):
        """INV-MOCK-3: MOCK:TYPE:value returns the typed value."""
        code = AI_MOCK_PREFIX + f"""
auto result = @~ {mock_directive} ~
print(result)
"""
        assert run_ibci(code) == [expected_value]

    def test_mock_invalid_directive_triggers_error(self):
        """INV-MOCK-3: 未知 MOCK 指令（MOCK:INVALID）在类型化消费位置触发 LLMParseError。

        MOCK 引擎对未知类型指令返回字面文本 ``[MOCK] MOCK:INVALID``，无法解析为
        目标类型（int）→ 运行期 LLMParseError（fail-fast，不静默给默认值）。
        """
        code = AI_MOCK_PREFIX + """
int x = @~ MOCK:INVALID ~
print(x)
"""
        expect_runtime_error(code, "LLMParseError")


# ===========================================================================
# Behavior Expression (INV-BEHAVIOR-*)
# ===========================================================================


class TestBehaviorExpression:
    """Validate behavior expression execution.
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
int x = 5
int y = x + @~ MOCK:INT:3 ~
print(y)
"""
        assert run_ibci(code) == ["8"]

    def test_behavior_in_control_flow(self):
        """INV-BEHAVIOR-4: Behavior can be used in control flow."""
        code = AI_MOCK_PREFIX + """
if @~ MOCK:INT:1 ~:
    print("branch_taken")
else:
    print("branch_skipped")
"""
        assert run_ibci(code) == ["branch_taken"]


# ===========================================================================
# LLM Function (INV-LLMFN-*)
# ===========================================================================


class TestLLMFunction:
    """Validate LLM callable class semantics（llm 函数 → llm 可调用类实例）。"""

    def test_llm_function_definition_and_call(self):
        """INV-LLMFN-1: LLM callable classes can be defined and called directly."""
        code = AI_MOCK_PREFIX + """
class Double:
    func __llm_call__(self, any x) -> dict:
        return {"user_prompt": "MOCK:INT:84", "prompt_slots": [{"kind": "user_sys", "text": "Double the input."}], "expected_type": "int"}
Double double = Double()
print(double(42))
"""
        assert run_ibci(code) == ["84"]

    def test_llm_function_parameter_binding(self):
        """INV-LLMFN-2: LLM callable class args are bound to __llm_call__ params."""
        code = AI_MOCK_PREFIX + """
class Greet:
    func __llm_call__(self, any name) -> dict:
        return {"user_prompt": "MOCK:STR:Hello", "prompt_slots": [{"kind": "user_sys", "text": "Greet the user."}], "expected_type": "str"}
Greet greet = Greet()
print(greet("World"))
"""
        result = run_ibci(code)
        assert "Hello" in result[0]

    def test_llm_function_return_type(self):
        """INV-LLMFN-3: expected_type enforces return parsing."""
        code = AI_MOCK_PREFIX + """
class Compute:
    func __llm_call__(self) -> dict:
        return {"user_prompt": "MOCK:INT:123", "prompt_slots": [{"kind": "user_sys", "text": "Compute."}], "expected_type": "int"}
Compute compute = Compute()
int result = compute()
print(result)
"""
        assert run_ibci(code) == ["123"]


# ===========================================================================
# Intent Context with LLM (INV-INTENT-LLM-*)
# ===========================================================================


class TestIntentWithLLM:
    """Validate intent context in LLM calls.
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
        """INV-INTENT-LLM-2: Intent works around LLM callable class calls."""
        code = AI_MOCK_PREFIX + """
class Process:
    func __llm_call__(self, any data) -> dict:
        return {"user_prompt": "MOCK:STR:processed", "prompt_slots": [{"kind": "user_sys", "text": "Process data."}], "expected_type": "str"}
Process process = Process()

@ "processing mode"
str out = process("input")
print(out)
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
