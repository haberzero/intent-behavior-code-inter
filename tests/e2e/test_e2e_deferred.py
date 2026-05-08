"""
tests/e2e/test_e2e_deferred.py

End-to-end tests for the universal deferred expression system (lambda/snapshot).

Coverage:
  - Axiom layer: TypeDef, DeferredAxiom, CallableAxiom type hierarchy
  - TypeDef compile-time return type inference (axiom level)
  - auto immediate behavior expression type inference
  - behavior expression assignment to object fields
  - fn keyword: callable type inference
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
# 1. Axiom layer: TypeDef, DeferredAxiom, CallableAxiom
# ---------------------------------------------------------------------------

class TestDeferredAxiomLayer:
    def test_deferred_spec_exists(self):
        """TypeDef should be registered in the spec registry."""
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


# ---------------------------------------------------------------------------
# 7. TypeDef compile-time return type inference
# ---------------------------------------------------------------------------

class TestBehaviorSpecReturnTypeInference:
    """Tests for TypeDef(value_type_name) compile-time return-type inference.

    When a user writes:
        fn f = lambda -> int: @~ compute something ~
    the variable ``f`` receives a ``TypeDef(value_type_name="int")``.
    Calling ``f()`` should resolve to ``int`` at compile time, so that
    ``int result = f()`` compiles without a SEM_003 type-mismatch error.
    """

    def test_behavior_spec_creation(self):
        """SpecFactory.create_behavior() returns TypeDef with correct fields."""
        from core.kernel.factory import create_default_registry
        from core.kernel.spec.specs import TypeDef
        reg = create_default_registry()
        bs = reg.factory.create_behavior(value_type_name="int")
        assert isinstance(bs, TypeDef)
        assert bs.value_type.head == "int"
        # capture_mode is a property of the runtime *value* (IbBehavior),
        # not of the type spec — see TypeKind.CALLABLE_INSTANCE docstring.
        assert bs.get_base_name() == "behavior"
        assert bs.name == "behavior[int]"

    def test_behavior_spec_auto_name(self):
        """TypeDef with value_type_name='auto' gets name 'behavior'."""
        from core.kernel.factory import create_default_registry
        from core.kernel.spec.specs import TypeDef
        reg = create_default_registry()
        bs = reg.factory.create_behavior(value_type_name="auto")
        assert isinstance(bs, TypeDef)
        assert bs.name == "behavior"

    def test_behavior_spec_is_assignable_to_behavior(self):
        """behavior is assignable to behavior[str] (runtime container check)."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        behavior_spec = reg.resolve("behavior")
        typed_spec = reg.factory.create_behavior(value_type_name="str")
        assert reg.is_assignable(behavior_spec, typed_spec)

    def test_behavior_spec_resolve_return(self):
        """resolve_return on TypeDef(value_type_name='int') returns int spec."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        bs = reg.factory.create_behavior(value_type_name="int")
        ret = reg.resolve_return(bs, [])
        assert ret is not None
        assert ret.name == "int"

    def test_behavior_spec_resolve_return_str(self):
        """resolve_return on TypeDef(value_type_name='str') returns str spec."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        bs = reg.factory.create_behavior(value_type_name="str")
        ret = reg.resolve_return(bs, [])
        assert ret is not None
        assert ret.name == "str"

    def test_behavior_spec_auto_resolves_to_auto(self):
        """resolve_return on TypeDef(value_type_name='auto') resolves to auto."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        bs = reg.factory.create_behavior(value_type_name="auto")
        ret = reg.resolve_return(bs, [])
        # "auto" is dynamic — resolve_return falls back to axiom path which returns "auto"
        assert ret is not None

    def test_deferred_spec_creation(self):
        """SpecFactory.create_deferred() creates TypeDef with correct get_base_name()."""
        from core.kernel.factory import create_default_registry
        from core.kernel.spec.specs import TypeDef
        reg = create_default_registry()
        ds = reg.factory.create_deferred(value_type_name="int")
        assert isinstance(ds, TypeDef)
        # [TODO] M3 单一 TypeDef 迁移后，TypeDef/TypeDef 均为 TypeDef 别名，
        # 不再通过 isinstance 区分，语义区分应由 kind/get_base_name 驱动。
        assert ds.kind != "behavior"
        assert ds.get_base_name() == "deferred"
        assert ds.value_type.head == "int"
        assert ds.name == "deferred[int]"

    def test_deferred_spec_resolve_return(self):
        """resolve_return on TypeDef(value_type_name='int') returns int spec."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        ds = reg.factory.create_deferred(value_type_name="int")
        ret = reg.resolve_return(ds, [])
        assert ret is not None
        assert ret.name == "int"


# ---------------------------------------------------------------------------
# 2. auto + immediate behavior expression type inference
# ---------------------------------------------------------------------------

class TestAutoImmediateBehaviorInference:
    """
    Regression tests for: auto r = @~...~ should infer 'str' (the natural LLM
    output type), not a deferred-object type.
    """

    def test_auto_immediate_behavior_infers_str_at_runtime(self):
        """auto r = @~MOCK:STR:hello~ ; r should hold the string 'hello'."""
        code = """import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
auto r = @~MOCK:STR:hello~
print(r)
"""
        lines = run_and_capture(code)
        assert "hello" in lines

    def test_auto_immediate_behavior_can_concat(self):
        """auto r = @~...~ ; r can be used as string (concat, etc.)."""
        code = """import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
auto r = @~MOCK:STR:world~
str greeting = "hello " + r
print(greeting)
"""
        lines = run_and_capture(code)
        assert "hello world" in lines

    def test_auto_immediate_behavior_print_is_str_not_behavior_repr(self):
        """auto r = @~MOCK:INT:42~ ; print must not show 'behavior' or 'deferred'."""
        code = """import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
auto r = @~MOCK:INT:42~
print(r)
"""
        lines = run_and_capture(code)
        # Must contain the actual value, not a behavior/deferred repr
        assert any(ln.strip() == "42" for ln in lines), f"Expected '42' in {lines}"
        assert all("behavior" not in ln.lower() and "deferred" not in ln.lower() for ln in lines)


# ---------------------------------------------------------------------------
# 3. Behavior expression assignment to object fields
# ---------------------------------------------------------------------------

class TestBehaviorExprFieldAssignment:
    """
    Regression tests for: assigning @~...~ to a class field must compile
    without SEM_003 and execute the LLM call, storing the result in the field.
    """

    def test_behavior_to_str_field_no_error(self):
        """b.content = @~MOCK:STR:hello~ must compile without SEM_003."""
        import os
        from core.engine import IBCIEngine
        code = """import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
class Box:
    str content

Box b = Box("")
b.content = @~MOCK:STR:hello~
print(b.content)
"""
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        lines = []
        engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
        assert "hello" in lines

    def test_behavior_to_int_field_no_error(self):
        """b.count = @~MOCK:INT:7~ must compile without SEM_003 and set the value."""
        import os
        from core.engine import IBCIEngine
        code = """import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
class Counter:
    int count

Counter c = Counter(0)
c.count = @~MOCK:INT:7~
print((str)c.count)
"""
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        lines = []
        engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
        assert "7" in lines

class TestFnKeyword:
    """Tests for the 'fn' keyword: callable type inference."""

    def test_fn_holds_regular_function(self):
        """fn f = myFunc; f() can be called and returns correctly."""
        code = """func add(int a, int b) -> int:
    return a + b

fn f = add
int result = f(3, 4)
print((str)result)
"""
        lines = run_and_capture(code)
        assert "7" in lines

    def test_fn_holds_auto_lambda(self):
        """fn f = lambda expr; f() evaluates the expression."""
        code = """int x = 10
fn compute = lambda: x + 5
fn f = compute
print((str)f())
"""
        lines = run_and_capture(code)
        assert "15" in lines

    def test_fn_lambda_declares_deferred_callable(self):
        """fn f = lambda: expr; f is a deferred callable."""
        code = """int x = 3
fn f = lambda: x * 2
print((str)f())
x = 10
print((str)f())
"""
        lines = run_and_capture(code)
        assert "6" in lines
        assert "20" in lines

    def test_fn_compile_error_on_non_callable(self):
        """fn f = 42 should raise a compile-time SEM_003 error."""
        from core.engine import IBCIEngine
        from core.kernel.issue import CompilerError
        import os
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        raised = False
        try:
            engine.compile_string("fn f = 42", silent=True)
        except CompilerError as e:
            raised = True
            # Verify it's a type mismatch error (SEM_003)
            codes = [d.code for d in e.diagnostics]
            assert "SEM_003" in codes, f"Expected SEM_003 but got: {codes}"
        assert raised, "Expected CompilerError for 'fn f = 42' (non-callable RHS)"

    def test_fn_holds_callable_class_instance(self):
        """fn f = instance where class defines __call__ should work."""
        code = """class Adder:
    int base

    func __init__(self, int b):
        self.base = b

    func __call__(self, int x) -> int:
        return self.base + x

Adder adder = Adder(10)
fn my_fn = adder
int result = my_fn(5)
print((str)result)
"""
        lines = run_and_capture(code)
        assert "15" in lines

    def test_fn_holds_class_constructor(self):
        """fn f = ClassName (constructor ref) should always be allowed."""
        code = """class Point:
    int x
    int y

fn ctor = Point
Point p = ctor(3, 4)
print((str)p.x)
print((str)p.y)
"""
        lines = run_and_capture(code)
        assert "3" in lines
        assert "4" in lines

    def test_fn_compile_error_instance_without_call(self):
        """fn f = instance of class that lacks __call__ should raise SEM_003."""
        from core.engine import IBCIEngine
        from core.kernel.issue import CompilerError
        import os
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        code = """class Plain:
    str name

Plain p = Plain("hi")
fn f = p
"""
        raised = False
        try:
            engine.compile_string(code, silent=True)
        except CompilerError as e:
            raised = True
            codes = [d.code for d in e.diagnostics]
            assert "SEM_003" in codes, f"Expected SEM_003 but got: {codes}"
        assert raised, "Expected CompilerError: Plain has no __call__"
