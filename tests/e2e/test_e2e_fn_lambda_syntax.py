"""
End-to-end tests for the parametric ``fn = lambda(...) / snapshot(...)`` syntax (M1).

Coverage:
  - No-param lambda: ``fn f = lambda: EXPR`` defers and re-evaluates each call
  - Parametric lambda: ``fn f = lambda(PARAMS): EXPR`` accepts arguments
  - No-param snapshot: ``fn f = snapshot: EXPR`` evaluates once and caches
  - Parametric snapshot: each call re-runs body, but free variables are frozen
  - Closure semantics:
      * lambda mode reads latest value of free vars at call time
      * snapshot mode freezes values at definition time (IbCell-backed)
  - Factory pattern: returning a snapshot lambda from a function captures locals
  - Nested lambdas: inner-param shadowing outer free vars
  - Behavior-body lambdas: ``fn f = lambda: @~...~`` produces a behavior with
    captured intents/closure
  - Backward compatibility: legacy ``TYPE lambda NAME = EXPR`` still works

Syntax rule: ``:`` is the only valid body-start delimiter.
Old parenthesis-only body forms (``lambda(EXPR)``, ``lambda(PARAMS)(EXPR)``, etc.)
are no longer supported and raise a parse error.
"""

import os
import pytest
from core.engine import IBCIEngine


def run_and_capture(code: str):
    lines = []
    engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
    engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
    return lines


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
    """``fn f = snapshot: EXPR``: evaluates once at first call, caches result."""

    def test_caches_value(self):
        code = """int x = 5
fn snap = snapshot: x * 2
print((str)snap())
x = 999
print((str)snap())
"""
        lines = run_and_capture(code)
        # snapshot caches: first call freezes 10, second returns the cache
        assert lines == ["10", "10"]


class TestFnParametricSnapshot:
    """
    ``fn f = snapshot(PARAMS): EXPR``: arguments are bound on each call,
    but free variables are captured (frozen via IbCell) at definition time.
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


class TestFnLambdaBackwardCompat:
    """Legacy ``TYPE lambda NAME = EXPR`` syntax must continue to work."""

    def test_legacy_int_lambda(self):
        code = """int x = 3
int lambda f = x * 2
print((str)f())
x = 10
print((str)f())
"""
        lines = run_and_capture(code)
        assert lines == ["6", "20"]

    def test_legacy_auto_lambda(self):
        code = """int x = 4
auto lambda g = x + 1
print((str)g())
"""
        assert run_and_capture(code) == ["5"]


class TestFnLambdaErrors:
    """Compile/runtime error paths for the new syntax."""

    def test_lambda_bare_expr_is_error(self):
        """``lambda`` keyword in expression position must be followed by '(', '->', or ':'."""
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


# ---------------------------------------------------------------------------
# Return type annotation: ``fn f = lambda -> TYPE: EXPR``
# and ``fn f = lambda(PARAMS) -> TYPE: EXPR``
# ---------------------------------------------------------------------------

class TestFnLambdaReturnsAnnotation:
    """Explicit return type annotation on lambda/snapshot."""

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
        """``int r = f()`` passes compile-time check when ``-> int`` is annotated."""
        from core.kernel.issue import CompilerError
        engine_dir = os.path.dirname(os.path.abspath(__file__))
        # Without annotation → SEM_003 (auto → int mismatch)
        with pytest.raises(CompilerError):
            IBCIEngine(root_dir=engine_dir, auto_sniff=False).compile_string(
                "fn f = lambda: 1 + 1\nint r = f()", silent=True)
        # With annotation → compiles OK
        IBCIEngine(root_dir=engine_dir, auto_sniff=False).compile_string(
            "fn f = lambda -> int: 1 + 1\nint r = f()", silent=True)


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
    """Behavior-body lambdas with explicit ``-> TYPE`` return type annotation."""

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
        # With annotation: compiles OK
        IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False).compile_string(
            _ai_prefix() + "\nfn f = lambda -> str: @~MOCK:STR:hi~\nstr r = f()", silent=True)

    def test_param_behavior_lambda_returns_str(self):
        """Parametric behavior lambda with ``-> str`` and prompt variable."""
        code = _ai_prefix() + """
fn greet = lambda(str name) -> str: @~MOCK:STR:hi-$name~
str r = greet("alice")
print(r)
"""
        assert run_and_capture(code) == ["hi-alice"]

    def test_snapshot_behavior_returns_str_freezes_intent(self):
        """``snapshot -> TYPE: @~...~`` freezes intent context at definition time."""
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

    # --- lambda -> TYPE: EXPR (no params + return type) ---

    def test_no_param_lambda_colon_with_return_type_compiles(self):
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        engine.compile_string("fn f = lambda -> int: 21 * 2\nint r = f()", silent=True)

    def test_no_param_lambda_colon_with_return_type_runtime(self):
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

    # --- lambda(PARAMS) -> TYPE: EXPR (params + return type) ---

    def test_param_lambda_colon_with_return_type_compiles(self):
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        engine.compile_string("fn mul = lambda(int a, int b) -> int: a * b\nint r = mul(6, 7)", silent=True)

    def test_param_lambda_colon_with_return_type_runtime(self):
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

    # --- snapshot -> TYPE: EXPR ---

    def test_snapshot_colon_with_return_type(self):
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

    # --- snapshot(PARAMS) -> TYPE: EXPR ---

    def test_snapshot_param_colon_with_return_type_runtime(self):
        code = """
int scale = 3
fn f = snapshot(int n) -> int: n * scale
scale = 100
int r = f(7)
print((str)r)
"""
        assert run_and_capture(code) == ["21"]

    # --- String body with colon ---

    def test_snapshot_colon_string_concat(self):
        code = """
str prefix = "hello"
fn f = snapshot -> str: prefix + " world"
prefix = "bye"
str r = f()
print(r)
"""
        assert run_and_capture(code) == ["hello world"]

    # --- Backward compat: old parenthesis forms are now parse errors ---

    def test_old_no_param_bracket_body_is_error(self):
        """``lambda(EXPR)`` no-param bracket-only body form is now a parse error."""
        from core.kernel.issue import CompilerError
        with pytest.raises(CompilerError):
            IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False).compile_string(
                "fn f = lambda(1 + 2)", silent=True)

    def test_old_param_bracket_body_is_error(self):
        """``lambda(PARAMS)(EXPR)`` bracket body form is now a parse error."""
        from core.kernel.issue import CompilerError
        with pytest.raises(CompilerError):
            IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False).compile_string(
                "fn f = lambda(int n)(n + 1)", silent=True)

    def test_old_returns_bracket_body_is_error(self):
        """``lambda -> TYPE (EXPR)`` bracket body form is now a parse error."""
        from core.kernel.issue import CompilerError
        with pytest.raises(CompilerError):
            IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False).compile_string(
                "fn f = lambda -> int (1 + 2)\nint r = f()", silent=True)

    def test_colon_returns_type_mismatch(self):
        """Body type mismatch with `-> TYPE:` raises SEM_003."""
        from core.kernel.issue import CompilerError
        with pytest.raises(CompilerError) as exc_info:
            IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False).compile_string(
                "fn f = lambda(int a) -> str: a + 1", silent=True)
        assert any(d.code == "SEM_003" for d in exc_info.value.diagnostics)
