"""
tests/e2e/test_e2e_deferred.py

End-to-end tests for the universal deferred expression system (lambda/snapshot).

Coverage:
  - lambda with function call expressions
  - snapshot with function call expressions
  - lambda with arithmetic expressions
  - snapshot with arithmetic expressions
  - lambda re-evaluates on each call
  - snapshot caches after first call
  - lambda with variable references (reads latest value)
  - Backward compatibility: lambda/snapshot with @~...~ behavior expressions
"""

import os
import pytest
from core.engine import IBCIEngine


def run_and_capture(code: str):
    lines = []
    def callback(text):
        lines.append(str(text))
    engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
    engine.run_string(code, output_callback=callback, silent=True)
    return lines


# ---------------------------------------------------------------------------
# 1. Lambda with function calls
# ---------------------------------------------------------------------------

class TestDeferredLambdaFunctionCall:
    def test_lambda_defers_function_call(self):
        """lambda wrapping a function call should defer execution and re-evaluate each time."""
        code = """
func greeting() -> str:
    return "hello"

auto lambda greet = greeting()
print(greet())
print(greet())
"""
        lines = run_and_capture(code)
        # Lambda re-evaluates: both calls produce "hello"
        assert lines.count("hello") == 2

    def test_lambda_wraps_pure_function(self):
        """lambda with a simple pure function call."""
        code = """
func greeting() -> str:
    return "hello world"

auto lambda greet = greeting()
print(greet())
"""
        lines = run_and_capture(code)
        assert "hello world" in lines


# ---------------------------------------------------------------------------
# 2. Snapshot with function calls
# ---------------------------------------------------------------------------

class TestDeferredSnapshotFunctionCall:
    def test_snapshot_caches_function_call(self):
        """snapshot wrapping a function call should evaluate once and cache."""
        code = """
func greeting() -> str:
    return "snapshot_result"

auto snapshot greet = greeting()
print(greet())
print(greet())
"""
        lines = run_and_capture(code)
        # Snapshot evaluates once: both calls return same result
        assert lines.count("snapshot_result") == 2


# ---------------------------------------------------------------------------
# 3. Lambda with arithmetic expressions
# ---------------------------------------------------------------------------

class TestDeferredLambdaArithmetic:
    def test_lambda_arithmetic_reevaluates(self):
        """lambda wrapping arithmetic expression re-evaluates each call."""
        code = """
int x = 10
auto lambda compute = x + 5
print((str)compute())
x = 20
print((str)compute())
"""
        lines = run_and_capture(code)
        assert "15" in lines
        assert "25" in lines


# ---------------------------------------------------------------------------
# 4. Snapshot with arithmetic expressions
# ---------------------------------------------------------------------------

class TestDeferredSnapshotArithmetic:
    def test_snapshot_arithmetic_freezes(self):
        """snapshot wrapping arithmetic expression evaluates once and caches."""
        code = """
int x = 10
auto snapshot compute = x + 5
print((str)compute())
x = 20
print((str)compute())
"""
        lines = run_and_capture(code)
        # Snapshot freezes at first evaluation: both calls return 15
        assert lines.count("15") == 2


# ---------------------------------------------------------------------------
# 5. Backward compatibility: lambda/snapshot with @~...~ behavior
# ---------------------------------------------------------------------------

class TestDeferredBehaviorBackwardCompat:
    def test_behavior_lambda_still_works(self):
        """Backward compat: lambda with behavior expression (@~...~)."""
        code = """import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
str lambda b = @~ MOCK:STR:deferred_result ~
print(b())
"""
        lines = run_and_capture(code)
        assert "deferred_result" in lines

    def test_behavior_snapshot_still_works(self):
        """Backward compat: snapshot with behavior expression (@~...~)."""
        code = """import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
str snapshot b = @~ MOCK:INT:42 ~
print((str)b())
"""
        lines = run_and_capture(code)
        assert "42" in lines


# ---------------------------------------------------------------------------
# 6. Axiom layer: DeferredSpec, DeferredAxiom, CallableAxiom
# ---------------------------------------------------------------------------

class TestDeferredAxiomLayer:
    def test_deferred_spec_exists(self):
        """DeferredSpec should be registered in the spec registry."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("deferred")
        assert spec is not None
        assert spec.name == "deferred"

    def test_callable_axiom_not_dynamic(self):
        """CallableAxiom should NOT be dynamic (replaces DynamicAxiom)."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("callable")
        assert spec is not None
        axiom = reg.get_axiom(spec)
        assert axiom is not None
        assert not axiom.is_dynamic()

    def test_deferred_axiom_not_dynamic(self):
        """DeferredAxiom should NOT be dynamic."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("deferred")
        axiom = reg.get_axiom(spec)
        assert axiom is not None
        assert not axiom.is_dynamic()

    def test_behavior_parent_is_deferred(self):
        """BehaviorAxiom's parent should be 'deferred', not 'Object'."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("behavior")
        axiom = reg.get_axiom(spec)
        assert axiom is not None
        assert axiom.get_parent_axiom_name() == "deferred"

    def test_deferred_parent_is_callable(self):
        """DeferredAxiom's parent should be 'callable'."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("deferred")
        axiom = reg.get_axiom(spec)
        assert axiom is not None
        assert axiom.get_parent_axiom_name() == "callable"

    def test_callable_parent_is_object(self):
        """CallableAxiom's parent should be 'Object'."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("callable")
        axiom = reg.get_axiom(spec)
        assert axiom is not None
        assert axiom.get_parent_axiom_name() == "Object"

    def test_deferred_has_call_capability(self):
        """DeferredAxiom should provide CallCapability."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("deferred")
        cap = reg.get_call_cap(spec)
        assert cap is not None

    def test_callable_has_call_capability(self):
        """CallableAxiom should provide CallCapability."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("callable")
        cap = reg.get_call_cap(spec)
        assert cap is not None

    def test_behavior_compatible_with_deferred(self):
        """BehaviorAxiom should be compatible with 'deferred' and 'callable'."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("behavior")
        axiom = reg.get_axiom(spec)
        assert axiom.is_compatible("deferred")
        assert axiom.is_compatible("callable")
        assert axiom.is_compatible("behavior")

    def test_deferred_compatible_with_callable(self):
        """DeferredAxiom should be compatible with 'callable' and 'deferred' (upward only).
        
        is_compatible(target) means "can I be assigned to a variable of type target".
        deferred IS-A callable, so deferred can go into callable/deferred slots.
        behavior is a sub-type of deferred — deferred cannot go into a behavior slot.
        """
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("deferred")
        axiom = reg.get_axiom(spec)
        assert axiom.is_compatible("callable")
        assert axiom.is_compatible("deferred")
        # behavior is a sub-type of deferred — deferred cannot be assigned to behavior slot
        assert not axiom.is_compatible("behavior")

    def test_callable_not_compatible_with_subtypes(self):
        """CallableAxiom can only be assigned to a callable slot, not to sub-type slots.
        
        Sub-types (deferred, behavior, bound_method) declare upward compatibility through
        their own is_compatible(), not through callable declaring downward compatibility.
        """
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("callable")
        axiom = reg.get_axiom(spec)
        assert axiom.is_compatible("callable")
        assert not axiom.is_compatible("deferred")
        assert not axiom.is_compatible("behavior")
        assert not axiom.is_compatible("bound_method")
