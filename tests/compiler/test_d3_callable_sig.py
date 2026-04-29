"""
D3: fn[(param_types) -> return_type] callable signature annotation tests.

Covers:
  - Parse: fn[(int, str) -> bool], fn[() -> int], fn[(int) -> int]
  - Semantic: CallableSigSpec produced from IbCallableType
  - Return-type inference: calling a fn[...] param inside function body
  - Structural arg-type check at call site (CallableSigSpec parameter)
  - Structural sig mismatch at declaration site
  - End-to-end: HOF with fn[(int) -> int] parameter executes correctly
  - Return type fn[...]: function returning a callable
  - Negative: wrong arg count → SEM_005
  - Negative: wrong arg type → SEM_003
  - Negative: sig mismatch at declaration → SEM_003
  - Backward compat: bare fn f = myfunc still works
"""

import os
import pytest
from core.engine import IBCIEngine
from core.kernel.issue import CompilerError


# ─────────────────────────────────────────────────────────────── helpers ──

def make_engine():
    return IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)


def compile_code(code: str):
    """Compile *code*, return (artifact_or_None, error_codes)."""
    engine = make_engine()
    try:
        artifact = engine.compile_string(code, silent=True)
        return artifact, set()
    except CompilerError as e:
        return None, {d.code for d in e.diagnostics}


def assert_compiles(code: str):
    artifact, errors = compile_code(code)
    assert not errors, f"Expected no errors, got: {errors}"
    assert artifact is not None


def assert_error_codes(code: str, *expected_codes: str):
    _, errors = compile_code(code)
    for code_val in expected_codes:
        assert code_val in errors, f"Expected error {code_val!r} but got: {errors}"


def run_and_capture(code: str):
    lines = []
    engine = make_engine()
    engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
    return lines


# ──────────────────────────────────────────────────────── parse / compile ──

class TestD3Parse:
    """Parser accepts fn[(...)→(...)] in type-annotation positions."""

    def test_no_params_int_return(self):
        """fn[() -> int] as parameter annotation compiles without errors."""
        assert_compiles("""
func apply(fn[() -> int] f) -> int:
    return f()
""")

    def test_single_param(self):
        """fn[(int) -> int] as parameter annotation compiles without errors."""
        assert_compiles("""
func apply(fn[(int) -> int] f, int x) -> int:
    return f(x)
""")

    def test_multi_param(self):
        """fn[(int, str) -> bool] as parameter annotation compiles without errors."""
        assert_compiles("""
func check(fn[(int, str) -> bool] predicate, int n, str s) -> bool:
    return predicate(n, s)
""")

    def test_as_variable_declaration_type(self):
        """fn[(int) -> int] as variable declaration type compiles without errors."""
        assert_compiles("""
func add_one(int n) -> int:
    return n + 1

fn[(int) -> int] f = add_one
""")

    def test_as_return_type_annotation(self):
        """fn[(int) -> int] as function return type annotation compiles without errors."""
        assert_compiles("""
func make_adder(int n) -> fn[(int) -> int]:
    fn add = lambda(int x): n + x
    return add
""")

    def test_bare_fn_still_works(self):
        """Plain fn f = myfunc (without signature) is unaffected by D3."""
        assert_compiles("""
func double(int n) -> int:
    return n * 2

fn f = double
print((str)f(3))
""")


# ─────────────────────────────────────────────────────── call-site checks ──

class TestD3CallSiteStructural:
    """Calling a fn[(...)→(...)] parameter: arg-count and type checks."""

    def test_correct_call_no_error(self):
        """Calling fn[(int) -> int] with correct arg type produces no error."""
        assert_compiles("""
func apply(fn[(int) -> int] f, int x) -> int:
    return f(x)
""")

    def test_too_many_args(self):
        """Calling fn[(int) -> int] with 2 args → SEM_005."""
        assert_error_codes("""
func apply(fn[(int) -> int] f, int x, int y) -> int:
    return f(x, y)
""", "SEM_005")

    def test_too_few_args(self):
        """Calling fn[(int, str) -> bool] with 1 arg → SEM_005."""
        assert_error_codes("""
func apply(fn[(int, str) -> bool] pred) -> bool:
    return pred(1)
""", "SEM_005")

    def test_wrong_arg_type(self):
        """Calling fn[(int) -> int] with str arg → SEM_003."""
        assert_error_codes("""
func apply(fn[(int) -> int] f, str s) -> int:
    return f(s)
""", "SEM_003")


# ──────────────────────────────────────────── declaration-site sig check ──

class TestD3DeclarationSite:
    """fn[(...)→(...)] variable declaration: structural sig matching on RHS."""

    def test_matching_sig_no_error(self):
        """fn[(int) -> int] f = add_one passes when signatures match."""
        assert_compiles("""
func add_one(int n) -> int:
    return n + 1

fn[(int) -> int] f = add_one
""")

    def test_param_count_mismatch(self):
        """fn[(int, str) -> int] f = add_one (1 param) → SEM_003."""
        assert_error_codes("""
func add_one(int n) -> int:
    return n + 1

fn[(int, str) -> int] f = add_one
""", "SEM_003")

    def test_return_type_mismatch(self):
        """fn[(int) -> str] f = add_one (returns int) → SEM_003."""
        assert_error_codes("""
func add_one(int n) -> int:
    return n + 1

fn[(int) -> str] f = add_one
""", "SEM_003")


# ────────────────────────────────────────────────────── return type infer ──

class TestD3ReturnTypeInference:
    """Return type of calling fn[(...)→T] parameter is inferred as T."""

    def test_int_return_inferred(self):
        """fn[(int) -> int] parameter: calling it produces int."""
        assert_compiles("""
func apply(fn[(int) -> int] f, int x) -> int:
    int result = f(x)
    return result
""")

    def test_bool_return_inferred(self):
        """fn[(int, str) -> bool] parameter: calling it produces bool."""
        assert_compiles("""
func check(fn[(int, str) -> bool] pred, int n, str s) -> bool:
    bool result = pred(n, s)
    return result
""")


# ──────────────────────────────────────────────────────── end-to-end runs ──

class TestD3E2E:
    """Full execution: HOF with fn[(...)→(...)] parameters."""

    def test_apply_double(self):
        """HOF apply(fn[(int) -> int], int) runs correctly."""
        lines = run_and_capture("""func double(int n) -> int:
    return n * 2

func apply(fn[(int) -> int] f, int x) -> int:
    return f(x)

int result = apply(double, 5)
print((str)result)
""")
        assert lines == ["10"]

    def test_apply_with_lambda(self):
        """HOF apply(fn[(int) -> int], int) works with a lambda."""
        lines = run_and_capture("""func apply(fn[(int) -> int] f, int x) -> int:
    return f(x)

fn triple = lambda(int n) -> int: n * 3
int result = apply(triple, 4)
print((str)result)
""")
        assert lines == ["12"]

    def test_multi_param_predicate(self):
        """HOF check(fn[(int, int) -> bool], int, int) works."""
        lines = run_and_capture("""func gt(int a, int b) -> bool:
    return a > b

func check(fn[(int, int) -> bool] pred, int x, int y) -> bool:
    return pred(x, y)

bool r1 = check(gt, 10, 3)
bool r2 = check(gt, 1, 7)
print((str)r1)
print((str)r2)
""")
        assert lines == ["True", "False"]

    def test_no_params_fn_sig(self):
        """HOF with fn[() -> int] parameter works."""
        lines = run_and_capture("""func get_ten() -> int:
    return 10

func call_it(fn[() -> int] f) -> int:
    return f()

int r = call_it(get_ten)
print((str)r)
""")
        assert lines == ["10"]

    def test_fn_sig_variable_callable(self):
        """fn[(int) -> int] variable pointing to a function, then called."""
        lines = run_and_capture("""func square(int n) -> int:
    return n * n

fn[(int) -> int] f = square
int result = f(7)
print((str)result)
""")
        assert lines == ["49"]

