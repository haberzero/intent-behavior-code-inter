"""
End-to-end tests for M2: IbCell GC roots + lexical scope formalization.

验证以下特性：
  - lambda 实例可以自由作为高阶函数参数传递（M2 主要用户功能）
  - lambda 通过共享 IbCell 捕获自由变量：调用时读到最新值（SC-4 正确性）
  - snapshot 通过独立 IbCell 副本冻结自由变量：不受外部修改影响（SC-3 正确性）
  - 工厂模式：函数返回 lambda，lambda 携带正确闭包
  - collect_gc_roots() 接口可调用，枚举出非空结果集
"""

import os
import pytest
from core.engine import IBCIEngine


def run_and_capture(code: str):
    lines = []
    engine = IBCIEngine(
        root_dir=os.path.dirname(os.path.abspath(__file__)),
        auto_sniff=False,
    )
    engine.run_string(
        code,
        output_callback=lambda t: lines.append(str(t)),
        silent=True,
    )
    return lines


# ---------------------------------------------------------------------------
# 1. lambda 作为高阶函数参数传递（M2 核心功能）
# ---------------------------------------------------------------------------


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
        values = [obj.to_native() for obj in roots if hasattr(obj, 'to_native')]
        assert 42 in values, f"GC roots should contain x=42; got native values: {values}"

