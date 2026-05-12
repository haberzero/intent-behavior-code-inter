"""
tests/e2e/test_e2e_higher_order.py
==================================

高阶函数 / 闭包 / fn / lambda / snapshot 综合 e2e 测试
（合并自 4 个历史文件）：

* fn[(in)->(out)] callable / behavior 类型层 + 立即执行 behavior 推断
  （原 ``test_e2e_fn_callable.py``）
* fn(...)=>{...} no-param/parametric lambda 与 snapshot 语法
  （原 ``test_e2e_fn_lambda_syntax.py``）
* snapshot 语义：定义时 deep_clone、reentrancy、不缓存、lambda reference 对比
  （原 ``test_e2e_snapshot_semantics.py``）
* lambda 作为高阶函数参数、IbCell 共享、snapshot IbCell 隔离、lambda factory
  （原 ``test_e2e_m2_higher_order.py``）

详见 docs/TESTS_REORGANIZATION_TASK.md Step 10。
"""
import os
import pytest

from core.engine import IBCIEngine


# ---------------------------------------------------------------------------
# 共享 helper（统一定义；旧 4 个文件本地副本去除）
# ---------------------------------------------------------------------------

def run_and_capture(code: str):
    lines = []
    engine = IBCIEngine(
        root_dir=os.path.dirname(os.path.abspath(__file__)),
        auto_sniff=False,
    )
    engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
    return lines


################################################################################
# MERGED: fn[(in)->(out)] callable + behavior return-type inference
# Source: tests/e2e/test_e2e_fn_callable.py
################################################################################

class TestFnCallableAxiomLayer:
    def test_fn_callable_spec_exists(self):
        """TypeDef should be registered in the spec registry."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("fn_callable")
        assert spec is not None
        assert spec.name == "fn_callable"

    def test_callable_axiom_not_dynamic(self):
        """CallableAxiom should NOT be dynamic (replaces DynamicAxiom)."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("callable")
        assert spec is not None
        axiom = reg.get_axiom(spec)
        assert axiom is not None
        assert not axiom.is_dynamic()

    def test_fn_callable_axiom_not_dynamic(self):
        """FnCallableAxiom should NOT be dynamic."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("fn_callable")
        axiom = reg.get_axiom(spec)
        assert axiom is not None
        assert not axiom.is_dynamic()

    def test_behavior_parent_is_fn_callable(self):
        """BehaviorAxiom's parent should be 'fn_callable', not 'Object'."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("behavior")
        axiom = reg.get_axiom(spec)
        assert axiom is not None
        assert axiom.get_parent_axiom_name() == "fn_callable"

    def test_fn_callable_parent_is_callable(self):
        """FnCallableAxiom's parent should be 'callable'."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("fn_callable")
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

    def test_fn_callable_has_call_capability(self):
        """FnCallableAxiom should provide CallCapability."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("fn_callable")
        cap = reg.get_call_cap(spec)
        assert cap is not None

    def test_callable_has_call_capability(self):
        """CallableAxiom should provide CallCapability."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("callable")
        cap = reg.get_call_cap(spec)
        assert cap is not None

    def test_behavior_compatible_with_fn_callable(self):
        """BehaviorAxiom should be compatible with 'fn_callable' and 'callable'."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("behavior")
        axiom = reg.get_axiom(spec)
        assert axiom.is_compatible("fn_callable")
        assert axiom.is_compatible("callable")
        assert axiom.is_compatible("behavior")

    def test_fn_callable_compatible_with_callable(self):
        """FnCallableAxiom should be compatible with 'callable' and 'fn_callable' (upward only).
        
        is_compatible(target) means "can I be assigned to a variable of type target".
        fn_callable IS-A callable, so fn_callable can go into callable/fn_callable slots.
        behavior is a sub-type of fn_callable — fn_callable cannot go into a behavior slot.
        """
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("fn_callable")
        axiom = reg.get_axiom(spec)
        assert axiom.is_compatible("callable")
        assert axiom.is_compatible("fn_callable")
        # behavior is a sub-type of fn_callable — fn_callable cannot be assigned to behavior slot
        assert not axiom.is_compatible("behavior")

    def test_callable_not_compatible_with_subtypes(self):
        """CallableAxiom can only be assigned to a callable slot, not to sub-type slots.
        
        Sub-types (fn_callable, behavior, bound_method) declare upward compatibility through
        their own is_compatible(), not through callable declaring downward compatibility.
        """
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        spec = reg.resolve("callable")
        axiom = reg.get_axiom(spec)
        assert axiom.is_compatible("callable")
        assert not axiom.is_compatible("fn_callable")
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

    def test_fn_callable_spec_creation(self):
        """SpecFactory.create_fn_callable() creates TypeDef with correct get_base_name()."""
        from core.kernel.factory import create_default_registry
        from core.kernel.spec.specs import TypeDef
        reg = create_default_registry()
        ds = reg.factory.create_fn_callable(value_type_name="int")
        assert isinstance(ds, TypeDef)
        # [TODO] M3 单一 TypeDef 迁移后，TypeDef/TypeDef 均为 TypeDef 别名，
        # 不再通过 isinstance 区分，语义区分应由 kind/get_base_name 驱动。
        assert ds.kind != "behavior"
        assert ds.get_base_name() == "fn_callable"
        assert ds.value_type.head == "int"
        assert ds.name == "fn_callable[int]"

    def test_fn_callable_spec_resolve_return(self):
        """resolve_return on TypeDef(value_type_name='int') returns int spec."""
        from core.kernel.factory import create_default_registry
        reg = create_default_registry()
        ds = reg.factory.create_fn_callable(value_type_name="int")
        ret = reg.resolve_return(ds, [])
        assert ret is not None
        assert ret.name == "int"


# ---------------------------------------------------------------------------
# 2. auto + immediate behavior expression type inference
# ---------------------------------------------------------------------------

class TestAutoImmediateBehaviorInference:
    """
    Regression tests for: auto r = @~...~ should infer 'str' (the natural LLM
    output type), not a fn_callable-object type.
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
        """auto r = @~MOCK:INT:42~ ; print must not show 'behavior' or 'fn_callable'."""
        code = """import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
auto r = @~MOCK:INT:42~
print(r)
"""
        lines = run_and_capture(code)
        # Must contain the actual value, not a behavior/fn_callable repr
        assert any(ln.strip() == "42" for ln in lines), f"Expected '42' in {lines}"
        assert all("behavior" not in ln.lower() and "fn_callable" not in ln.lower() for ln in lines)


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

    def test_fn_lambda_declares_fn_callable(self):
        """fn f = lambda: expr; f is a fn_callable."""
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


################################################################################
# MERGED: fn(...)=>{...} lambda / snapshot syntax
# Source: tests/e2e/test_e2e_fn_lambda_syntax.py
################################################################################

class TestFnNoParamLambda:
    """``fn f = lambda: EXPR``: defers a no-param expression, re-evaluates each call."""

    def test_simple_arithmetic(self):
        code = """int x = 5
fn f = lambda: x * 2
print((str)f())
"""
        assert "10" in run_and_capture(code)

    def test_reads_latest_free_var(self):
        code = """int x = 5
fn f = lambda: x * 2
print((str)f())
x = 100
print((str)f())
"""
        lines = run_and_capture(code)
        assert lines == ["10", "200"]

    def test_function_call_in_body(self):
        code = """func double(int n) -> int:
    return n * 2

fn f = lambda: double(7)
print((str)f())
print((str)f())
"""
        lines = run_and_capture(code)
        assert lines == ["14", "14"]


class TestFnParametricLambda:
    """``fn f = lambda(PARAMS): EXPR``: accepts arguments, body sees them."""

    def test_one_param(self):
        code = """fn square = lambda(int n): n * n
print((str)square(4))
print((str)square(10))
"""
        lines = run_and_capture(code)
        assert lines == ["16", "100"]

    def test_multi_params(self):
        code = """fn add = lambda(int a, int b): a + b
print((str)add(3, 4))
print((str)add(10, 20))
"""
        lines = run_and_capture(code)
        assert lines == ["7", "30"]

    def test_param_with_free_var(self):
        """Lambda body references both a param and an outer var."""
        code = """int base = 100
fn shifted = lambda(int n): n + base
print((str)shifted(5))
base = 200
print((str)shifted(5))
"""
        lines = run_and_capture(code)
        # lambda mode → reads latest base each call
        assert lines == ["105", "205"]

    def test_param_shadows_outer(self):
        """A param named the same as an outer var refers to the param."""
        code = """int x = 999
fn f = lambda(int x): x + 1
print((str)f(10))
"""
        assert run_and_capture(code) == ["11"]


class TestFnNoParamSnapshot:
    """``fn f = snapshot: EXPR``: each call re-runs body with deep-cloned frozen free vars."""

    def test_freezes_free_var(self):
        code = """int x = 5
fn snap = snapshot: x * 2
print((str)snap())
x = 999
print((str)snap())
"""
        lines = run_and_capture(code)
        # snapshot 在定义时把 x 深克隆为只读种子（int 是不可变原语 → 共享引用）；
        # 外层 x = 999 不会污染种子，两次 snap() 均读到种子的 5 → 10。
        assert lines == ["10", "10"]


class TestFnParametricSnapshot:
    """
    ``fn f = snapshot(PARAMS): EXPR``: arguments are bound on each call,
    but free variables are deep-cloned at definition time and re-cloned per call
    (no result caching — snapshot is fully stateless / reentrant).
    """

    def test_freezes_free_var(self):
        code = """int base = 10
fn addbase = snapshot(int n): n + base
print((str)addbase(5))
base = 999
print((str)addbase(7))
"""
        lines = run_and_capture(code)
        # base captured at 10; both calls see frozen value
        assert lines == ["15", "17"]

    def test_each_call_uses_new_args(self):
        """Parametric snapshot must NOT cache the return value (args differ)."""
        code = """fn add = snapshot(int a, int b): a + b
print((str)add(1, 2))
print((str)add(10, 20))
print((str)add(100, 200))
"""
        lines = run_and_capture(code)
        assert lines == ["3", "30", "300"]


class TestFnLambdaFactory:
    """Returning a snapshot from a function captures its locals."""

    def test_snapshot_factory_pattern(self):
        code = """func make_adder(int b) -> fn:
    fn f = snapshot(int x): x + b
    return f

fn a5 = make_adder(5)
fn a10 = make_adder(10)
print((str)a5(3))
print((str)a10(3))
print((str)a5(100))
"""
        lines = run_and_capture(code)
        assert lines == ["8", "13", "105"]


class TestFnLambdaNested:
    """Nested lambdas: inner param shadows outer free var."""

    def test_inner_param_shadows_outer(self):
        code = """int x = 100
fn outer = lambda(int x): x * 2
print((str)outer(7))
"""
        # inner param x=7 shadows outer x=100
        assert run_and_capture(code) == ["14"]


class TestFnLambdaInvalidDeclarationSyntax:
    """Invalid declaration-side syntax forms produce compile errors."""

    def test_type_lambda_decl_is_error(self):
        """``int lambda f = EXPR`` declaration syntax is a parse error."""
        from core.kernel.issue import CompilerError
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        with pytest.raises(CompilerError):
            engine.compile_string("int x = 3\nint lambda f = x * 2", silent=True)

    def test_auto_lambda_decl_is_error(self):
        """``auto lambda g = EXPR`` declaration syntax is a parse error."""
        from core.kernel.issue import CompilerError
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        with pytest.raises(CompilerError):
            engine.compile_string("int x = 4\nauto lambda g = x + 1", silent=True)


class TestFnLambdaErrors:
    """Compile/runtime error paths for the new syntax."""

    def test_lambda_bare_expr_is_error(self):
        """``lambda`` keyword in expression position must be followed by '(' or ':'."""
        from core.kernel.issue import CompilerError
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        with pytest.raises(CompilerError):
            engine.compile_string("fn f = lambda 5", silent=True)

    def test_lambda_paren_body_only_is_error(self):
        """Old ``lambda(EXPR)`` bracket-only body form is no longer supported."""
        from core.kernel.issue import CompilerError
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        with pytest.raises(CompilerError):
            engine.compile_string("fn f = lambda(1 + 2)", silent=True)

    def test_lambda_returns_type_mismatch(self):
        """Body type incompatible with declared return type raises SEM_003."""
        from core.kernel.issue import CompilerError
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        with pytest.raises(CompilerError) as exc_info:
            engine.compile_string("fn f = lambda(int a) -> str: a + 1", silent=True)
        assert any(d.code == "SEM_003" for d in exc_info.value.diagnostics)

    def test_decl_side_type_fn_is_error(self):
        """``int fn f = lambda: EXPR`` declaration-side return type is PAR_003."""
        from core.kernel.issue import CompilerError
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        with pytest.raises(CompilerError):
            engine.compile_string("int fn f = lambda: 1 + 1", silent=True)

    def test_decl_side_type_fn_params_is_error(self):
        """``int fn add = lambda(int a, int b): a+b`` declaration-side form is PAR_003."""
        from core.kernel.issue import CompilerError
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        with pytest.raises(CompilerError):
            engine.compile_string("int fn add = lambda(int a, int b): a + b", silent=True)

    def test_lambda_exprside_arrow_compiles(self):
        """``fn f = lambda -> int: EXPR`` expression-side annotation is valid."""
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        engine.compile_string("fn f = lambda -> int: 1 + 1\nint r = f()", silent=True)

    def test_lambda_exprside_arrow_params_compiles(self):
        """``fn f = lambda(PARAMS) -> int: EXPR`` expression-side annotation is valid."""
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        engine.compile_string("fn f = lambda(int a) -> int: a + 1\nint r = f(3)", silent=True)


# ---------------------------------------------------------------------------
# Return type annotation: ``fn NAME = lambda -> TYPE: EXPR``
# ---------------------------------------------------------------------------

class TestFnReturnsAnnotation:
    """Expression-side return type annotation via ``fn name = lambda -> TYPE: EXPR``."""

    def test_no_param_lambda_returns_int_compiles(self):
        """`fn f = lambda -> int: EXPR` resolves `int r = f()` at compile time."""
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        engine.compile_string("""
fn f = lambda -> int: 21 * 2
int r = f()
""", silent=True)

    def test_no_param_lambda_returns_int_runtime(self):
        code = """
fn f = lambda -> int: 21 * 2
int r = f()
print((str)r)
"""
        assert run_and_capture(code) == ["42"]

    def test_param_lambda_returns_int_compiles(self):
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        engine.compile_string("""
fn add = lambda(int a, int b) -> int: a + b
int r = add(1, 2)
""", silent=True)

    def test_param_lambda_returns_int_runtime(self):
        code = """
fn add = lambda(int a, int b) -> int: a + b
int r = add(10, 32)
print((str)r)
"""
        assert run_and_capture(code) == ["42"]

    def test_snapshot_returns_int_freezes_free_var(self):
        code = """
int base = 10
fn f = snapshot -> int: base + 5
base = 999
int r = f()
print((str)r)
"""
        assert run_and_capture(code) == ["15"]

    def test_snapshot_returns_int_with_params(self):
        code = """
int scale = 3
fn f = snapshot(int n) -> int: n * scale
scale = 100
int r = f(7)
print((str)r)
"""
        # scale frozen at 3 at snapshot creation time → 7 * 3 = 21
        assert run_and_capture(code) == ["21"]

    def test_returns_str_concat(self):
        code = """
fn greet = lambda(str name) -> str: "Hello, " + name + "!"
str r = greet("World")
print(r)
"""
        assert run_and_capture(code) == ["Hello, World!"]

    def test_type_checking_call_site(self):
        """``int r = f()`` passes compile-time check when ``fn f = lambda -> int`` is declared."""
        from core.kernel.issue import CompilerError
        engine_dir = os.path.dirname(os.path.abspath(__file__))
        # Without annotation → SEM_003 (auto → int mismatch)
        with pytest.raises(CompilerError):
            IBCIEngine(root_dir=engine_dir, auto_sniff=False).compile_string(
                "fn f = lambda: 1 + 1\nint r = f()", silent=True)
        # With expression-side annotation → compiles OK
        IBCIEngine(root_dir=engine_dir, auto_sniff=False).compile_string(
            "fn f = lambda -> int: 1 + 1\nint r = f()", silent=True)

    def test_factory_function_returning_typed_fn(self):
        """``fn f = make_adder()`` — factory result used (full type propagation requires D3)."""
        # [INFO] 高阶 fn 工厂返回值应保持可调用返回类型传播，调用侧可直接得到推导结果。
        code = """
func make_adder(int b) -> fn:
    fn inner = lambda(int x) -> int: x + b
    return inner

fn a5 = make_adder(5)
auto r = a5(3)
print((str)r)
"""
        assert run_and_capture(code) == ["8"]


# ---------------------------------------------------------------------------
# Behavior-bodied lambdas: ``fn f = lambda(@~...~)`` produces an IbBehavior.
# Uses MOCK mode so tests are deterministic.
# ---------------------------------------------------------------------------

def _ai_prefix() -> str:
    return 'import ai\nai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'


class TestFnLambdaBehaviorBody:
    def test_no_param_behavior_lambda(self):
        code = _ai_prefix() + """
fn b = lambda: @~MOCK:STR:hello~
str r = (str)b()
print(r)
"""
        assert run_and_capture(code) == ["hello"]

    def test_param_behavior_lambda_with_var_ref(self):
        """Param ``$who`` is bound on each call and interpolated into the prompt."""
        code = _ai_prefix() + """
fn greet = lambda(str who): @~MOCK:STR:hi-$who~
str r1 = (str)greet("alice")
print(r1)
str r2 = (str)greet("bob")
print(r2)
"""
        assert run_and_capture(code) == ["hi-alice", "hi-bob"]


class TestFnLambdaBehaviorBodyReturnsAnnotation:
    """Behavior-body lambdas with expression-side ``-> TYPE`` return type annotation (D2)."""

    def test_behavior_lambda_returns_str_no_param(self):
        """``fn f = lambda -> str: @~...~`` annotates expected LLM output type."""
        code = _ai_prefix() + """
fn f = lambda -> str: @~MOCK:STR:hello~
str r = f()
print(r)
"""
        assert run_and_capture(code) == ["hello"]

    def test_behavior_lambda_returns_str_call_site_typed(self):
        """`fn f = lambda -> str: @~...~` enables `str r = f()` without cast."""
        from core.kernel.issue import CompilerError
        # Without annotation: `str r = f()` would be SEM_003
        with pytest.raises(CompilerError):
            IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False).compile_string(
                _ai_prefix() + "\nfn f = lambda: @~MOCK:STR:hi~\nstr r = f()", silent=True)
        # With expression-side annotation: compiles OK
        IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False).compile_string(
            _ai_prefix() + "\nfn f = lambda -> str: @~MOCK:STR:hi~\nstr r = f()", silent=True)

    def test_param_behavior_lambda_returns_str(self):
        """Parametric behavior lambda with expression-side ``-> str`` and prompt variable."""
        code = _ai_prefix() + """
fn greet = lambda(str name) -> str: @~MOCK:STR:hi-$name~
str r = greet("alice")
print(r)
"""
        assert run_and_capture(code) == ["hi-alice"]

    def test_snapshot_behavior_returns_str_freezes_intent(self):
        """``fn f = snapshot -> str: @~...~`` freezes intent context at definition time."""
        code = _ai_prefix() + """
fn f = snapshot -> str: @~MOCK:STR:frozen~
str r = f()
print(r)
"""
        assert run_and_capture(code) == ["frozen"]


# ---------------------------------------------------------------------------
# Colon body-start syntax: the only valid body-start delimiter.
# ---------------------------------------------------------------------------

class TestFnLambdaColonSyntax:
    """Colon body-start is the mandatory syntax for all lambda/snapshot forms."""

    # --- lambda: EXPR (no params, no return type) ---

    def test_no_param_lambda_colon_compile(self):
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        engine.compile_string("fn f = lambda: 1 + 2", silent=True)

    def test_no_param_lambda_colon_runtime(self):
        assert run_and_capture("fn f = lambda: 21 * 2\nprint((str)f())") == ["42"]

    def test_no_param_lambda_colon_free_var(self):
        code = """int x = 10
fn f = lambda: x * 4
print((str)f())
x = 20
print((str)f())
"""
        assert run_and_capture(code) == ["40", "80"]

    # --- fn f = lambda -> int: EXPR (no params + expression-side return type, D2) ---

    def test_no_param_lambda_expr_return_type_compiles(self):
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        engine.compile_string("fn f = lambda -> int: 21 * 2\nint r = f()", silent=True)

    def test_no_param_lambda_expr_return_type_runtime(self):
        code = """
fn f = lambda -> int: 21 * 2
int r = f()
print((str)r)
"""
        assert run_and_capture(code) == ["42"]

    # --- lambda(PARAMS): EXPR (params, no return type) ---

    def test_param_lambda_colon_compile(self):
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        engine.compile_string("fn add = lambda(int a, int b): a + b", silent=True)

    def test_param_lambda_colon_runtime(self):
        code = """
fn add = lambda(int a, int b): a + b
auto r = add(10, 32)
print((str)r)
"""
        assert run_and_capture(code) == ["42"]

    # --- fn f = lambda(PARAMS) -> int: EXPR (params + expression-side return type, D2) ---

    def test_param_lambda_expr_return_type_compiles(self):
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        engine.compile_string("fn mul = lambda(int a, int b) -> int: a * b\nint r = mul(6, 7)", silent=True)

    def test_param_lambda_expr_return_type_runtime(self):
        code = """
fn mul = lambda(int a, int b) -> int: a * b
int r = mul(6, 7)
print((str)r)
"""
        assert run_and_capture(code) == ["42"]

    # --- snapshot: EXPR (no params, free var frozen) ---

    def test_snapshot_colon_freezes_free_var(self):
        code = """
int n = 10
fn f = snapshot: n + 5
n = 999
auto r = f()
print((str)r)
"""
        assert run_and_capture(code) == ["15"]

    # --- fn f = snapshot -> int: EXPR (expression-side return type, D2) ---

    def test_snapshot_expr_return_type(self):
        code = """
int n = 10
fn f = snapshot -> int: n + 5
n = 999
int r = f()
print((str)r)
"""
        assert run_and_capture(code) == ["15"]

    # --- snapshot(PARAMS): EXPR ---

    def test_snapshot_param_colon_runtime(self):
        code = """
int scale = 3
fn f = snapshot(int n): n * scale
scale = 100
auto r = f(7)
print((str)r)
"""
        assert run_and_capture(code) == ["21"]

    # --- fn f = snapshot(PARAMS) -> int: EXPR (params + expression-side return type, D2) ---

    def test_snapshot_param_expr_return_type_runtime(self):
        code = """
int scale = 3
fn f = snapshot(int n) -> int: n * scale
scale = 100
int r = f(7)
print((str)r)
"""
        assert run_and_capture(code) == ["21"]

    # --- String body with colon (expression-side return type) ---

    def test_snapshot_colon_string_concat(self):
        code = """
str prefix = "hello"
fn f = snapshot -> str: prefix + " world"
prefix = "bye"
str r = f()
print(r)
"""
        assert run_and_capture(code) == ["hello world"]

    # --- Invalid bracket-only body forms ---

    def test_no_param_bracket_body_is_error(self):
        """``lambda(EXPR)`` bracket-only body form is a parse error."""
        from core.kernel.issue import CompilerError
        with pytest.raises(CompilerError):
            IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False).compile_string(
                "fn f = lambda(1 + 2)", silent=True)

    def test_param_bracket_body_is_error(self):
        """``lambda(PARAMS)(EXPR)`` bracket body form is a parse error."""
        from core.kernel.issue import CompilerError
        with pytest.raises(CompilerError):
            IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False).compile_string(
                "fn f = lambda(int n)(n + 1)", silent=True)

    def test_decl_side_type_fn_is_error(self):
        """``int fn f = lambda: EXPR`` declaration-side return type is PAR_003."""
        from core.kernel.issue import CompilerError
        with pytest.raises(CompilerError):
            IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False).compile_string(
                "int fn f = lambda: 1 + 2\nint r = f()", silent=True)

    def test_expr_side_arrow_is_valid(self):
        """``fn f = lambda -> int: EXPR`` expression-side return type is valid."""
        IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False).compile_string(
            "fn f = lambda -> int: 1 + 2\nint r = f()", silent=True)

    def test_return_type_mismatch_raises_sem_003(self):
        """Body type mismatch with expression-side ``-> TYPE`` raises SEM_003."""
        from core.kernel.issue import CompilerError
        with pytest.raises(CompilerError) as exc_info:
            IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False).compile_string(
                "fn f = lambda(int a) -> str: a + 1", silent=True)
        assert any(d.code == "SEM_003" for d in exc_info.value.diagnostics)


################################################################################
# MERGED: snapshot semantics: deep_clone / reentrancy / no-cache
# Source: tests/e2e/test_e2e_snapshot_semantics.py
################################################################################

class TestSnapshotDeepCloneAtDefinition:
    """snapshot 在定义时对自由变量做深克隆；外部对原容器的就地突变不应影响 snapshot。"""

    def test_snapshot_isolates_list_from_outer_mutation(self):
        """外层在 snapshot 创建后向 list append——snapshot 仍读到定义时刻的列表。"""
        code = """list xs = [1, 2, 3]
fn snap = snapshot: xs.len()
print((str)snap())
xs.append(4)
xs.append(5)
print((str)snap())
"""
        # 旧实现（IbCell 浅包装）会让 snap() 第二次返回 5；
        # 深克隆后 snap() 两次都返回 3。
        assert run_and_capture(code) == ["3", "3"]

    def test_snapshot_isolates_dict_from_outer_mutation(self):
        """外层修改 dict 键值后，snapshot 看到的仍是定义时刻的状态。"""
        code = """dict d = {"k": 1}
fn snap = snapshot: (int)d["k"]
print((str)snap())
d["k"] = 999
print((str)snap())
"""
        assert run_and_capture(code) == ["1", "1"]

    def test_snapshot_with_param_isolates_list(self):
        """有参 snapshot：实参随调用变化，闭包 list 仍冻结。"""
        code = """list base = [10, 20]
fn add_first = snapshot(int x): base[0] + x
print((str)add_first(5))
base.append(999)
base[0] = 777
print((str)add_first(5))
"""
        # base[0] frozen at 10, so 10+5=15 both times.
        assert run_and_capture(code) == ["15", "15"]


# ---------------------------------------------------------------------------
# 2. snapshot 可重入：体内突变不跨调用
# ---------------------------------------------------------------------------


class TestSnapshotReentrancy:
    """snapshot 是无状态可重入的可调用实例：每次调用从冻结种子再深克隆。"""

    def test_snapshot_body_mutation_does_not_persist_across_calls(self):
        """snapshot 体内 append 到闭包 list；下次调用应仍看到原始长度。"""
        code = """func _mutate_count(list b) -> int:
    b.append(99)
    return b.len()

list buf = [1, 2]
fn snap = snapshot: _mutate_count(buf)
print((str)snap())
print((str)snap())
print((str)snap())
"""
        # 若闭包种子被共享，则 3、4、5；若每次重新克隆，则 3、3、3。
        assert run_and_capture(code) == ["3", "3", "3"]

    def test_snapshot_dict_mutation_isolation(self):
        """snapshot 体内修改闭包 dict 的键值；下次调用应仍读到种子原始值。"""
        code = """func _bump(dict d) -> int:
    int n = (int)d["n"] + 1
    d["n"] = n
    return n

dict d = {"n": 0}
fn snap = snapshot: _bump(d)
print((str)snap())
print((str)snap())
print((str)snap())
"""
        # 每次都从种子开始：种子 n=0 → +1 → 1
        assert run_and_capture(code) == ["1", "1", "1"]

    def test_snapshot_with_params_reentrant(self):
        """有参 snapshot：闭包种子在调用间隔保持新鲜，调用之间互不干扰。"""
        code = """func _add(list s, int d) -> int:
    int newv = (int)s[0] + d
    s[0] = newv
    return newv

list shared = [0]
fn snap = snapshot(int delta): _add(shared, delta)
print((str)snap(5))
print((str)snap(7))
print((str)snap(100))
"""
        # 种子 shared=[0]，每次都从 0 起加上 delta
        assert run_and_capture(code) == ["5", "7", "100"]


# ---------------------------------------------------------------------------
# 3. snapshot 无缓存：无参 snapshot 也每次重新求值
# ---------------------------------------------------------------------------


class TestSnapshotNoCache:
    """删除 _cache 短路后，snapshot 不再缓存任何结果。"""

    def test_no_param_snapshot_does_not_pollute_outer_seed(self):
        """无参 snapshot 调用多次，外层的 list 始终不变（深克隆 + 无缓存共同保证）。

        若仍存在旧 _cache，第一次 snap() 调用会让 body 跑一次并把 seed[0] mutate
        为 84；之后所有 snap() 都直接返回 cache 而不重新跑 body，那么 seed 是否
        被外部观测到变化、依赖于初次执行环境——这一路在旧实现下其实也不会污染
        外层（因为定义时已 IbCell(val) 浅包装），所以本测试焦点是：删除 cache
        之后 body 反复执行，外层 seed 仍然纯净——证明每次都是从冻结种子深克隆。
        """
        code = """func _double_first(list s) -> int:
    int v = (int)s[0] * 2
    s[0] = v
    return v

list seed = [42]
fn snap = snapshot: _double_first(seed)
print((str)snap())
print((str)snap())
print((str)seed[0])
print((str)seed.len())
"""
        # snap() 每次都从种子 [42] 深克隆 → 体内 *2 → 返回 84。
        # 外层 seed 始终保持 [42]。
        assert run_and_capture(code) == ["84", "84", "42", "1"]


# ---------------------------------------------------------------------------
# 4. lambda 对照：引用语义保持
# ---------------------------------------------------------------------------


class TestLambdaReferenceSemantics:
    """lambda 不深克隆任何东西——外部突变与体内突变都跨调用可见。"""

    def test_lambda_sees_outer_mutation(self):
        code = """list xs = [1, 2, 3]
fn read = lambda: xs.len()
print((str)read())
xs.append(4)
xs.append(5)
print((str)read())
"""
        # lambda 共享 cell → 第二次读到新长度。
        assert run_and_capture(code) == ["3", "5"]

    def test_lambda_body_mutation_persists(self):
        """lambda 体内对闭包容器的突变应跨调用可见（共享 cell）。"""
        code = """func _push_one(list b) -> int:
    b.append(1)
    return b.len()

list buf = []
fn push = lambda: _push_one(buf)
print((str)push())
print((str)push())
print((str)push())
"""
        assert run_and_capture(code) == ["1", "2", "3"]


################################################################################
# MERGED: lambda as HOF arg / IbCell sharing / snapshot isolation
# Source: tests/e2e/test_e2e_m2_higher_order.py
################################################################################

class TestLambdaAsHigherOrderArg:
    """M2: lambda 对象可以自由传入函数参数，并在函数内被调用。"""

    def test_lambda_passed_to_func_and_called(self):
        # fn 参数调用返回 auto；用 (int) 转型后赋值给 int 变量
        code = """func apply(fn f, int val) -> auto:
    return f(val)

fn double = lambda(int x): x * 2
int result = (int)apply(double, 5)
print((str)result)
"""
        assert run_and_capture(code) == ["10"]

    def test_lambda_passed_and_called_multiple_times(self):
        # [INFO] fn 形参在高阶调用链中应可稳定传播可调用返回类型。
        code = """func apply_twice(fn f, int val) -> auto:
    auto r1 = f(val)
    auto r2 = f((int)r1)
    return r2

fn triple = lambda(int x): x * 3
int result = (int)apply_twice(triple, 2)
print((str)result)
"""
        # triple(2) = 6, triple(6) = 18
        assert run_and_capture(code) == ["18"]

    def test_lambda_with_free_var_passed_to_func(self):
        """lambda 持有自由变量，传入函数后调用时读取最新值（SC-4）。"""
        code = """int base = 10
fn adder = lambda(int x): x + base

func apply(fn f, int val) -> auto:
    return f(val)

int r1 = (int)apply(adder, 5)
print((str)r1)
base = 20
int r2 = (int)apply(adder, 5)
print((str)r2)
"""
        # base=10: 5+10=15; base=20: 5+20=25
        assert run_and_capture(code) == ["15", "25"]

    def test_no_param_lambda_passed_to_func(self):
        """无参 lambda 传入函数后被调用。"""
        code = """int counter = 0

func call_fn(fn f) -> auto:
    return f()

fn get_counter = lambda: counter
counter = 42
int r = (int)call_fn(get_counter)
print((str)r)
"""
        assert run_and_capture(code) == ["42"]

    def test_multiple_lambdas_passed(self):
        """同时传入多个不同的 lambda 对象。"""
        # [INFO] 多个 fn 形参组合调用时应保持签名传播一致。
        code = """func compose(fn f, fn g, int val) -> auto:
    auto tmp = g(val)
    return f((int)tmp)

fn add1 = lambda(int x): x + 1
fn mul2 = lambda(int x): x * 2

int r = (int)compose(add1, mul2, 5)
print((str)r)
"""
        # mul2(5)=10, add1(10)=11
        assert run_and_capture(code) == ["11"]

    def test_lambda_returned_from_func_and_applied(self):
        """函数返回 lambda，高阶函数调用它。"""
        code = """func make_adder(int n) -> fn:
    fn f = lambda(int x): x + n
    return f

func apply(fn f, int val) -> auto:
    return f(val)

fn add5 = make_adder(5)
int r = (int)apply(add5, 10)
print((str)r)
"""
        assert run_and_capture(code) == ["15"]

    def test_lambda_as_str_higher_order(self):
        """lambda 处理字符串，传入高阶函数。"""
        code = """func transform(fn f, str s) -> auto:
    return f(s)

fn shout = lambda(str x): x + "!"
str r = (str)transform(shout, "hello")
print(r)
"""
        assert run_and_capture(code) == ["hello!"]


# ---------------------------------------------------------------------------
# 2. lambda 共享 IbCell 语义（SC-4 正确性）
# ---------------------------------------------------------------------------


class TestLambdaSharedIbCell:
    """lambda 通过共享 IbCell 捕获自由变量，调用时读最新值。"""

    def test_lambda_sees_updated_free_var(self):
        code = """int x = 5
fn f = lambda: x * 2
print((str)f())
x = 100
print((str)f())
"""
        assert run_and_capture(code) == ["10", "200"]

    def test_lambda_with_param_and_free_var_updated(self):
        code = """int base = 100
fn shifted = lambda(int n): n + base
print((str)shifted(5))
base = 200
print((str)shifted(5))
"""
        assert run_and_capture(code) == ["105", "205"]

    def test_two_lambdas_share_same_var(self):
        """两个 lambda 引用同一自由变量，均应看到最新值。"""
        code = """int shared = 0
fn reader = lambda: shared
fn doubler = lambda: shared * 2

shared = 7
print((str)reader())
print((str)doubler())
shared = 10
print((str)reader())
print((str)doubler())
"""
        assert run_and_capture(code) == ["7", "14", "10", "20"]


# ---------------------------------------------------------------------------
# 3. snapshot 独立 IbCell 语义（SC-3 正确性，回归保证）
# ---------------------------------------------------------------------------


class TestSnapshotIbCellIsolation:
    """snapshot 通过值拷贝 IbCell 冻结自由变量，外部修改不影响。"""

    def test_snapshot_freezes_free_var(self):
        code = """int x = 5
fn snap = snapshot: x * 2
print((str)snap())
x = 999
print((str)snap())
"""
        assert run_and_capture(code) == ["10", "10"]

    def test_snapshot_with_params_freezes_free(self):
        code = """int base = 10
fn addbase = snapshot(int n): n + base
print((str)addbase(5))
base = 999
print((str)addbase(7))
"""
        # base frozen at 10
        assert run_and_capture(code) == ["15", "17"]

    def test_snapshot_factory_pattern(self):
        code = """func make_adder(int b) -> fn:
    fn f = snapshot(int x): x + b
    return f

fn a5 = make_adder(5)
fn a10 = make_adder(10)
print((str)a5(3))
print((str)a10(3))
print((str)a5(100))
"""
        assert run_and_capture(code) == ["8", "13", "105"]


# ---------------------------------------------------------------------------
# 4. lambda 工厂模式（SC-4 跨函数生命周期）
# ---------------------------------------------------------------------------


class TestLambdaFactory:
    """函数返回 lambda，外层作用域退出后 lambda 仍能访问捕获的变量。"""

    def test_lambda_from_factory_reads_param(self):
        """工厂函数的参数被 lambda 捕获，函数退出后仍可读。"""
        code = """func make_greeter(str greeting) -> fn:
    fn greet = lambda(str name): greeting + ", " + name
    return greet

fn hello = make_greeter("Hello")
fn hi = make_greeter("Hi")
print(hello("Alice"))
print(hi("Bob"))
"""
        assert run_and_capture(code) == ["Hello, Alice", "Hi, Bob"]

    def test_lambda_factory_in_higher_order(self):
        """工厂返回的 lambda 直接传入高阶函数。"""
        code = """func make_adder(int n) -> fn:
    fn adder = lambda(int x): x + n
    return adder

func apply(fn f, int val) -> auto:
    return f(val)

fn add3 = make_adder(3)
fn add7 = make_adder(7)
print((str)(int)apply(add3, 10))
print((str)(int)apply(add7, 10))
"""
        assert run_and_capture(code) == ["13", "17"]


# ---------------------------------------------------------------------------
# 5. collect_gc_roots() 接口
# ---------------------------------------------------------------------------


class TestCollectGcRoots:
    """M2 GC-2: RuntimeContextImpl.collect_gc_roots() 接口验证。"""

    def test_collect_gc_roots_returns_nonempty(self):
        """简单程序运行后，collect_gc_roots() 能枚举出对象。"""
        engine = IBCIEngine(
            root_dir=os.path.dirname(os.path.abspath(__file__)),
            auto_sniff=False,
        )
        code = "int x = 42\nint y = 100\n"
        engine.run_string(code, output_callback=lambda t: None, silent=True)
        rt_ctx = engine.interpreter.runtime_context
        roots = list(rt_ctx.collect_gc_roots())
        assert len(roots) > 0, "collect_gc_roots() must yield at least one root object"

    def test_collect_gc_roots_includes_cell_vars(self):
        """lambda 捕获的 Cell 变量值能出现在 GC 根集合中。"""
        engine = IBCIEngine(
            root_dir=os.path.dirname(os.path.abspath(__file__)),
            auto_sniff=False,
        )
        code = "int x = 42\nfn f = lambda: x\n"
        engine.run_string(code, output_callback=lambda t: None, silent=True)
        rt_ctx = engine.interpreter.runtime_context
        roots = list(rt_ctx.collect_gc_roots())
        # 过滤掉未执行的 IbFnCallable/IbBehavior（M4：to_native 在未执行时抛错），
        # 直接对其余对象调用 to_native()。
        from core.runtime.objects.builtins import IbFnCallable, IbBehavior
        values = [
            obj.to_native()
            for obj in roots
            if hasattr(obj, 'to_native') and not isinstance(obj, (IbFnCallable, IbBehavior))
        ]
        assert 42 in values, f"GC roots should contain x=42; got native values: {values}"
