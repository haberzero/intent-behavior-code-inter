"""
tests/e2e/test_e2e_higher_order.py
==================================

高阶函数 / 闭包 / fn / lambda / snapshot 综合 e2e 测试。

覆盖范围：
* fn 关键字 callable 类型层（函数引用 / lambda / __call__ / 构造器）
* lambda 语法（无参 / 有参 / 自由变量 / 嵌套 / 错误路径）
* snapshot 语义（deep_clone / reentrancy / 无缓存 / factory）
* 返回类型标注（expression-side -> TYPE）
* behavior-bodied lambda（MOCK 模式）
* lambda 作为高阶函数参数 / factory 模式

注意：IbCell 共享语义 / snapshot 基础隔离语义 的 **公理级** 覆盖在
``tests/contracts/test_scope_semantics.py`` 中（INV-CELL-* / INV-SNAPSHOT-*）。
本文件仅保留 e2e 层面的独有场景（如容器就地突变、重入性、factory 模式等）。
"""
import pytest

from tests.conftest import run_ibci, compile_ibci, compile_or_errors, expect_compile_error, AI_MOCK_PREFIX


# ---------------------------------------------------------------------------
# 1. Behavior expression assignment to object fields
# ---------------------------------------------------------------------------

class TestBehaviorExprFieldAssignment:
    """Assigning @~...~ to a class field must compile and execute correctly."""

    def test_behavior_to_str_field(self):
        """b.content = @~MOCK:STR:hello~ compiles and stores result."""
        code = """\
class Box:
    str content

Box b = Box("")
b.content = @~MOCK:STR:hello~
print(b.content)
"""
        assert "hello" in run_ibci(code, ai=True)

    def test_behavior_to_int_field(self):
        """b.count = @~MOCK:INT:7~ compiles and stores result."""
        code = """\
class Counter:
    int count

Counter c = Counter(0)
c.count = @~MOCK:INT:7~
print((str)c.count)
"""
        assert "7" in run_ibci(code, ai=True)

class TestFnKeyword:
    """Tests for the 'fn' keyword: callable type inference."""

    def test_fn_holds_regular_function(self):
        """fn f = myFunc; f() can be called and returns correctly."""
        code = """\
func add(int a, int b) -> int:
    return a + b

fn f = add
int result = f(3, 4)
print((str)result)
"""
        assert run_ibci(code) == ["7"]

    def test_fn_holds_auto_lambda(self):
        """fn f = lambda expr; f() evaluates the expression."""
        code = """\
int x = 10
fn compute = lambda -> auto: x + 5
fn f = compute
print((str)f())
"""
        assert run_ibci(code) == ["15"]

    def test_fn_lambda_reads_latest_free_var(self):
        """fn f = lambda -> auto: expr; f reads latest value of captured variable."""
        code = """\
int x = 3
fn f = lambda -> auto: x * 2
print((str)f())
x = 10
print((str)f())
"""
        assert run_ibci(code) == ["6", "20"]

    def test_fn_compile_error_on_non_callable(self):
        """fn f = 42 should raise SEM_TYPE_MISMATCH."""
        expect_compile_error("fn f = 42", "SEM_TYPE_MISMATCH")

    def test_fn_holds_callable_class_instance(self):
        """fn f = instance where class defines __call__ should work."""
        code = """\
class Adder:
    int base

    func __init__(self, int b) -> auto:
        self.base = b

    func __call__(self, int x) -> int:
        return self.base + x

Adder adder = Adder(10)
fn my_fn = adder
int result = my_fn(5)
print((str)result)
"""
        assert run_ibci(code) == ["15"]

    def test_fn_holds_class_constructor(self):
        """fn f = ClassName (constructor ref) should always be allowed."""
        code = """\
class Point:
    int x
    int y

fn ctor = Point
Point p = ctor(3, 4)
print((str)p.x)
print((str)p.y)
"""
        assert run_ibci(code) == ["3", "4"]

    def test_fn_compile_error_instance_without_call(self):
        """fn f = instance of class that lacks __call__ should raise SEM_TYPE_MISMATCH."""
        code = """\
class Plain:
    str name

Plain p = Plain("hi")
fn f = p
"""
        expect_compile_error(code, "SEM_TYPE_MISMATCH")


################################################################################
# Lambda / Snapshot syntax
################################################################################

class TestFnNoParamLambda:
    """``fn f = lambda -> auto: EXPR``: defers a no-param expression, re-evaluates each call."""

    def test_simple_arithmetic(self):
        code = "int x = 5\nfn f = lambda -> auto: x * 2\nprint((str)f())"
        assert run_ibci(code) == ["10"]

    def test_function_call_in_body(self):
        code = """\
func double(int n) -> int:
    return n * 2

fn f = lambda -> auto: double(7)
print((str)f())
print((str)f())
"""
        assert run_ibci(code) == ["14", "14"]


class TestFnParametricLambda:
    """``fn f = lambda(PARAMS) -> auto: EXPR``: accepts arguments, body sees them."""

    def test_one_param(self):
        code = "fn square = lambda(int n) -> auto: n * n\nprint((str)square(4))\nprint((str)square(10))"
        assert run_ibci(code) == ["16", "100"]

    def test_multi_params(self):
        code = "fn add = lambda(int a, int b) -> auto: a + b\nprint((str)add(3, 4))\nprint((str)add(10, 20))"
        assert run_ibci(code) == ["7", "30"]

    def test_param_shadows_outer(self):
        """A param named the same as an outer var refers to the param."""
        code = "int x = 999\nfn f = lambda(int x) -> auto: x + 1\nprint((str)f(10))"
        assert run_ibci(code) == ["11"]


class TestFnSnapshot:
    """Snapshot semantics: deep-cloned frozen free vars at definition time."""

    def test_no_param_freezes_free_var(self):
        code = """\
int x = 5
fn snap = snapshot -> auto: x * 2
print((str)snap())
x = 999
print((str)snap())
"""
        assert run_ibci(code) == ["10", "10"]

    def test_parametric_freezes_free_var(self):
        code = """\
int base = 10
fn addbase = snapshot(int n) -> auto: n + base
print((str)addbase(5))
base = 999
print((str)addbase(7))
"""
        assert run_ibci(code) == ["15", "17"]

    def test_each_call_uses_new_args(self):
        """Parametric snapshot must NOT cache the return value."""
        code = """\
fn add = snapshot(int a, int b) -> auto: a + b
print((str)add(1, 2))
print((str)add(10, 20))
print((str)add(100, 200))
"""
        assert run_ibci(code) == ["3", "30", "300"]

    def test_snapshot_factory_pattern(self):
        code = """\
func make_adder(int b) -> fn:
    fn f = snapshot(int x) -> auto: x + b
    return f

fn a5 = make_adder(5)
fn a10 = make_adder(10)
print((str)a5(3))
print((str)a10(3))
print((str)a5(100))
"""
        assert run_ibci(code) == ["8", "13", "105"]


class TestFnLambdaNested:
    """Nested lambdas: inner param shadows outer free var."""

    def test_inner_param_shadows_outer(self):
        code = "int x = 100\nfn outer = lambda(int x) -> auto: x * 2\nprint((str)outer(7))"
        assert run_ibci(code) == ["14"]


class TestFnLambdaErrors:
    """Compile error paths for lambda/snapshot syntax."""

    def test_type_lambda_decl_is_error(self):
        """``int lambda f = EXPR`` is a parse error."""
        expect_compile_error("int x = 3\nint lambda f = x * 2", "PAR_EXPECTED_TOKEN")

    def test_auto_lambda_decl_is_error(self):
        """``auto lambda g = EXPR`` is a parse error."""
        expect_compile_error("int x = 4\nauto lambda g = x + 1", "PAR_EXPECTED_TOKEN")

    def test_lambda_bare_expr_is_error(self):
        """``lambda`` keyword must be followed by '(' or ':'."""
        expect_compile_error("fn f = lambda 5", "PAR_UNEXPECTED_TOKEN")

    def test_lambda_bracket_body_is_error(self):
        """Old ``lambda(EXPR)`` bracket-only body form is not supported."""
        expect_compile_error("fn f = lambda(1 + 2)", "PAR_UNEXPECTED_TOKEN")

    def test_lambda_returns_type_mismatch(self):
        """Body type incompatible with declared return type raises SEM_TYPE_MISMATCH."""
        expect_compile_error("fn f = lambda(int a) -> str: a + 1", "SEM_TYPE_MISMATCH")

    def test_decl_side_type_fn_is_error(self):
        """``int fn f = lambda -> auto: EXPR`` declaration-side return type is error."""
        expect_compile_error("int fn f = lambda -> auto: 1 + 1", "PAR_INVALID_SYNTAX")

    def test_expr_side_arrow_compiles(self):
        """``fn f = lambda -> int: EXPR`` expression-side annotation is valid."""
        compile_ibci("fn f = lambda -> int: 1 + 1\nint r = f()")

    def test_expr_side_arrow_params_compiles(self):
        """``fn f = lambda(PARAMS) -> int: EXPR`` expression-side annotation is valid."""
        compile_ibci("fn f = lambda(int a) -> int: a + 1\nint r = f(3)")


# ---------------------------------------------------------------------------
# Return type annotation: ``fn NAME = lambda -> TYPE: EXPR``
# ---------------------------------------------------------------------------

class TestFnReturnsAnnotation:
    """Expression-side return type annotation via ``fn name = lambda -> TYPE: EXPR``."""

    def test_no_param_lambda_returns_int(self):
        """``fn f = lambda -> int: EXPR`` resolves at compile + runtime."""
        code = "fn f = lambda -> int: 21 * 2\nint r = f()\nprint((str)r)"
        assert run_ibci(code) == ["42"]

    def test_param_lambda_returns_int(self):
        code = "fn add = lambda(int a, int b) -> int: a + b\nint r = add(10, 32)\nprint((str)r)"
        assert run_ibci(code) == ["42"]

    def test_snapshot_returns_int_freezes_free_var(self):
        code = """\
int base = 10
fn f = snapshot -> int: base + 5
base = 999
int r = f()
print((str)r)
"""
        assert run_ibci(code) == ["15"]

    def test_snapshot_returns_int_with_params(self):
        code = """\
int scale = 3
fn f = snapshot(int n) -> int: n * scale
scale = 100
int r = f(7)
print((str)r)
"""
        assert run_ibci(code) == ["21"]

    def test_returns_str_concat(self):
        code = """\
fn greet = lambda(str name) -> str: "Hello, " + name + "!"
str r = greet("World")
print(r)
"""
        assert run_ibci(code) == ["Hello, World!"]

    def test_type_checking_call_site(self):
        """`-> auto` 推断 lambda 返回类型；显式标注亦编译通过。"""
        compile_ibci("fn f = lambda -> auto: 1 + 1\nint r = f()")
        compile_ibci("fn f = lambda -> int: 1 + 1\nint r = f()")

    def test_factory_function_returning_typed_fn(self):
        code = """\
func make_adder(int b) -> fn:
    fn inner = lambda(int x) -> int: x + b
    return inner

fn a5 = make_adder(5)
auto r = a5(3)
print((str)r)
"""
        assert run_ibci(code) == ["8"]


# ---------------------------------------------------------------------------
# Behavior-bodied lambdas: ``fn f = lambda: @~...~`` (MOCK mode)
# ---------------------------------------------------------------------------


class TestFnLambdaBehaviorBody:
    def test_no_param_behavior_lambda(self):
        code = AI_MOCK_PREFIX + "fn b = lambda -> auto: @~MOCK:STR:hello~\nstr r = (str)b()\nprint(r)"
        assert run_ibci(code) == ["hello"]

    def test_param_behavior_lambda_with_var_ref(self):
        """Param ``$who`` bound on each call and interpolated into prompt."""
        code = AI_MOCK_PREFIX + """\
fn greet = lambda(str who) -> auto: @~MOCK:STR:hi-$who~
str r1 = (str)greet("alice")
print(r1)
str r2 = (str)greet("bob")
print(r2)
"""
        assert run_ibci(code) == ["hi-alice", "hi-bob"]

    def test_behavior_lambda_returns_str_annotation(self):
        """``fn f = lambda -> str: @~...~`` enables typed call site."""
        code = AI_MOCK_PREFIX + "fn f = lambda -> str: @~MOCK:STR:hello~\nstr r = f()\nprint(r)"
        assert run_ibci(code) == ["hello"]

    def test_behavior_lambda_returns_str_call_site_typed(self):
        """行为体 `-> auto` 唯一推断为 str；`str r = f()` 免强转；`int` 需显式 `-> int`。"""
        compile_ibci(AI_MOCK_PREFIX + "\nfn f = lambda -> auto: @~MOCK:STR:hi~\nstr r = f()")
        compile_ibci(AI_MOCK_PREFIX + "\nfn f = lambda -> str: @~MOCK:STR:hi~\nstr r = f()")
        # 行为体 auto 只给 str：赋给 int 编译报错，必须显式 -> int
        expect_compile_error(
            AI_MOCK_PREFIX + "\nfn f = lambda -> auto: @~MOCK:STR:hi~\nint r = f()", "SEM_TYPE_MISMATCH")

    def test_snapshot_behavior_returns_str(self):
        """``fn f = snapshot -> str: @~...~`` freezes intent context."""
        code = AI_MOCK_PREFIX + "fn f = snapshot -> str: @~MOCK:STR:frozen~\nstr r = f()\nprint(r)"
        assert run_ibci(code) == ["frozen"]


# ---------------------------------------------------------------------------
# Colon syntax: additional coverage for less-common forms
# (Most lambda/snapshot colon syntax is already covered above;
#  this section validates remaining edge cases.)
# ---------------------------------------------------------------------------

class TestFnLambdaColonSyntaxEdgeCases:
    """Edge cases for lambda/snapshot colon syntax not covered by primary tests."""

    def test_lambda_free_var_reads_latest(self):
        """No-param lambda with free var reads latest value at call time."""
        code = "int x = 10\nfn f = lambda -> auto: x * 4\nprint((str)f())\nx = 20\nprint((str)f())"
        assert run_ibci(code) == ["40", "80"]

    def test_snapshot_string_concat(self):
        code = """\
str prefix = "hello"
fn f = snapshot -> str: prefix + " world"
prefix = "bye"
str r = f()
print(r)
"""
        assert run_ibci(code) == ["hello world"]

    def test_param_bracket_body_is_error(self):
        """``lambda(PARAMS)(EXPR)`` bracket body form is a parse error."""
        expect_compile_error("fn f = lambda(int n)(n + 1)", "PAR_UNEXPECTED_TOKEN")


################################################################################
# Snapshot deep-clone / reentrancy / no-cache (mutable container focus)
################################################################################

class TestSnapshotDeepCloneAtDefinition:
    """snapshot deep-clones mutable containers; outer mutations don't affect it."""

    def test_snapshot_isolates_list_from_outer_mutation(self):
        code = """\
list xs = [1, 2, 3]
fn snap = snapshot -> auto: xs.len()
print((str)snap())
xs.append(4)
xs.append(5)
print((str)snap())
"""
        assert run_ibci(code) == ["3", "3"]

    def test_snapshot_isolates_dict_from_outer_mutation(self):
        code = """\
dict d = {"k": 1}
fn snap = snapshot -> auto: (int)d["k"]
print((str)snap())
d["k"] = 999
print((str)snap())
"""
        assert run_ibci(code) == ["1", "1"]

    def test_snapshot_with_param_isolates_list(self):
        code = """\
list base = [10, 20]
fn add_first = snapshot(int x) -> auto: base[0] + x
print((str)add_first(5))
base.append(999)
base[0] = 777
print((str)add_first(5))
"""
        assert run_ibci(code) == ["15", "15"]


class TestSnapshotReentrancy:
    """snapshot is stateless/reentrant: each call re-clones from frozen seed."""

    def test_body_mutation_does_not_persist(self):
        code = """\
func _mutate_count(list b) -> int:
    b.append(99)
    return b.len()

list buf = [1, 2]
fn snap = snapshot -> auto: _mutate_count(buf)
print((str)snap())
print((str)snap())
print((str)snap())
"""
        assert run_ibci(code) == ["3", "3", "3"]

    def test_dict_mutation_isolation(self):
        code = """\
func _bump(dict d) -> int:
    int n = (int)d["n"] + 1
    d["n"] = n
    return n

dict d = {"n": 0}
fn snap = snapshot -> auto: _bump(d)
print((str)snap())
print((str)snap())
print((str)snap())
"""
        assert run_ibci(code) == ["1", "1", "1"]

    def test_with_params_reentrant(self):
        code = """\
func _add(list s, int d) -> int:
    int newv = (int)s[0] + d
    s[0] = newv
    return newv

list shared = [0]
fn snap = snapshot(int delta) -> auto: _add(shared, delta)
print((str)snap(5))
print((str)snap(7))
print((str)snap(100))
"""
        assert run_ibci(code) == ["5", "7", "100"]


class TestSnapshotNoCache:
    """snapshot never caches results; each call re-evaluates from frozen seed."""

    def test_no_param_snapshot_does_not_pollute_outer_seed(self):
        code = """\
func _double_first(list s) -> int:
    int v = (int)s[0] * 2
    s[0] = v
    return v

list seed = [42]
fn snap = snapshot -> auto: _double_first(seed)
print((str)snap())
print((str)snap())
print((str)seed[0])
print((str)seed.len())
"""
        assert run_ibci(code) == ["84", "84", "42", "1"]


# ---------------------------------------------------------------------------
# Lambda reference semantics (contrast with snapshot)
# ---------------------------------------------------------------------------

class TestLambdaReferenceSemantics:
    """lambda shares references — outer/body mutations visible across calls."""

    def test_lambda_sees_outer_mutation(self):
        code = """\
list xs = [1, 2, 3]
fn read = lambda -> auto: xs.len()
print((str)read())
xs.append(4)
xs.append(5)
print((str)read())
"""
        assert run_ibci(code) == ["3", "5"]

    def test_lambda_body_mutation_persists(self):
        code = """\
func _push_one(list b) -> int:
    b.append(1)
    return b.len()

list buf = []
fn push = lambda -> auto: _push_one(buf)
print((str)push())
print((str)push())
print((str)push())
"""
        assert run_ibci(code) == ["1", "2", "3"]


################################################################################
# Lambda as higher-order function argument / factory patterns
################################################################################

class TestLambdaAsHigherOrderArg:
    """Lambda objects can be passed as function arguments and called inside."""

    def test_lambda_passed_and_called(self):
        code = """\
func apply(fn f, int val) -> auto:
    return f(val)

fn double = lambda(int x) -> auto: x * 2
int result = (int)apply(double, 5)
print((str)result)
"""
        assert run_ibci(code) == ["10"]

    def test_lambda_chained_calls(self):
        code = """\
func apply_twice(fn f, int val) -> auto:
    auto r1 = f(val)
    auto r2 = f((int)r1)
    return r2

fn triple = lambda(int x) -> auto: x * 3
int result = (int)apply_twice(triple, 2)
print((str)result)
"""
        assert run_ibci(code) == ["18"]

    def test_lambda_with_free_var_passed(self):
        """lambda with free var: reads latest value when called inside another function."""
        code = """\
int base = 10
fn adder = lambda(int x) -> auto: x + base

func apply(fn f, int val) -> auto:
    return f(val)

int r1 = (int)apply(adder, 5)
print((str)r1)
base = 20
int r2 = (int)apply(adder, 5)
print((str)r2)
"""
        assert run_ibci(code) == ["15", "25"]

    def test_multiple_lambdas_composed(self):
        code = """\
func compose(fn f, fn g, int val) -> auto:
    auto tmp = g(val)
    return f((int)tmp)

fn add1 = lambda(int x) -> auto: x + 1
fn mul2 = lambda(int x) -> auto: x * 2

int r = (int)compose(add1, mul2, 5)
print((str)r)
"""
        assert run_ibci(code) == ["11"]

    def test_lambda_returned_from_func_and_applied(self):
        code = """\
func make_adder(int n) -> fn:
    fn f = lambda(int x) -> auto: x + n
    return f

func apply(fn f, int val) -> auto:
    return f(val)

fn add5 = make_adder(5)
int r = (int)apply(add5, 10)
print((str)r)
"""
        assert run_ibci(code) == ["15"]


class TestLambdaFactory:
    """Functions return lambdas that retain access to captured variables."""

    def test_lambda_from_factory_reads_param(self):
        code = """\
func make_greeter(str greeting) -> fn:
    fn greet = lambda(str name) -> auto: greeting + ", " + name
    return greet

fn hello = make_greeter("Hello")
fn hi = make_greeter("Hi")
print(hello("Alice"))
print(hi("Bob"))
"""
        assert run_ibci(code) == ["Hello, Alice", "Hi, Bob"]

    def test_lambda_factory_in_higher_order(self):
        code = """\
func make_adder(int n) -> fn:
    fn adder = lambda(int x) -> auto: x + n
    return adder

func apply(fn f, int val) -> auto:
    return f(val)

fn add3 = make_adder(3)
fn add7 = make_adder(7)
print((str)(int)apply(add3, 10))
print((str)(int)apply(add7, 10))
"""
        assert run_ibci(code) == ["13", "17"]
