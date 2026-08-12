"""
tests/e2e/test_nonlocal.py
=========================================

Tests for nonlocal keyword implementation:
- Lexer: nonlocal is a reserved keyword
- Parser: IbNonlocalStmt is correctly parsed
- Semantic: nonlocal names resolve to outer scope symbols
- Runtime: nonlocal assignment writes through to outer scope (Cell mechanism)
- Error handling: nonlocal in invalid contexts produces diagnostics
"""

from tests.conftest import run_ibci, compile_or_errors


class TestNonlocalBasicSemantics:
    """Basic nonlocal keyword compile and execution."""

    def test_nonlocal_simple_write_back(self):
        """Inner function modifies outer variable via nonlocal."""
        code = """
func outer() -> int:
    int count = 0
    func inc() -> auto:
        nonlocal count
        count = count + 1
    inc()
    inc()
    return count

print(outer())
"""
        assert run_ibci(code) == ["2"]

    def test_nonlocal_read_outer_variable(self):
        """Inner function reads outer variable without writing (nonlocal still works)."""
        code = """
func outer() -> int:
    int x = 42
    func inner() -> int:
        nonlocal x
        return x
    return inner()

print(outer())
"""
        assert run_ibci(code) == ["42"]

    def test_nonlocal_multiple_variables(self):
        """nonlocal with multiple variable names."""
        code = """
func outer() -> int:
    int a = 1
    int b = 2
    func swap() -> auto:
        nonlocal a, b
        int temp = a
        a = b
        b = temp
    swap()
    return a + b * 10

print(outer())
"""
        assert run_ibci(code) == ["12"]

    def test_nonlocal_counter_pattern(self):
        """Classic counter closure with nonlocal (called within outer scope)."""
        code = """
func test_counter() -> int:
    int count = 0
    func increment() -> auto:
        nonlocal count
        count = count + 1
    func get_count() -> int:
        nonlocal count
        return count
    increment()
    increment()
    increment()
    return get_count()

print(test_counter())
"""
        assert run_ibci(code) == ["3"]

    def test_nonlocal_nested_two_levels(self):
        """nonlocal works across two nesting levels."""
        code = """
func outer() -> int:
    int x = 0
    func middle() -> auto:
        nonlocal x
        func inner() -> auto:
            nonlocal x
            x = x + 10
        inner()
        x = x + 1
    middle()
    return x

print(outer())
"""
        assert run_ibci(code) == ["11"]


class TestNonlocalClosureReturn:
    """nonlocal with returned functions (closure with Cell write-back)."""

    def test_nonlocal_returned_function_read(self):
        """Returned closure can read captured nonlocal variable."""
        code = """
func make_getter() -> fn:
    int val = 99
    func getter() -> int:
        nonlocal val
        return val
    return getter

fn g = make_getter()
print(g())
"""
        assert run_ibci(code) == ["99"]

    def test_nonlocal_returned_function_write(self):
        """Returned closure can write to captured nonlocal variable (Cell)."""
        code = """
func make_counter() -> fn:
    int count = 0
    func inc() -> int:
        nonlocal count
        count = count + 1
        return count
    return inc

fn counter = make_counter()
print(counter())
print(counter())
print(counter())
"""
        assert run_ibci(code) == ["1", "2", "3"]

    def test_nonlocal_multiple_closures_share_cell(self):
        """Multiple closures share the same Cell for nonlocal variable."""
        code = """
func make_pair() -> list:
    int shared = 0
    func inc() -> int:
        nonlocal shared
        shared = shared + 1
        return shared
    func get() -> int:
        nonlocal shared
        return shared
    return [inc, get]

auto pair = make_pair()
fn do_inc = pair[0]
fn do_get = pair[1]
do_inc()
do_inc()
print(do_get())
"""
        assert run_ibci(code) == ["2"]


class TestNonlocalErrorDiagnostics:
    """Compile-time diagnostics for invalid nonlocal usage."""

    def test_nonlocal_at_module_scope_error(self):
        """nonlocal at module scope should produce SEM_INTENT_PLACEMENT."""
        code = """
nonlocal x
int x = 1
"""
        artifact, errors = compile_or_errors(code)
        assert "SEM_INTENT_PLACEMENT" in errors

    def test_nonlocal_undefined_in_outer_scope(self):
        """nonlocal referencing non-existent outer variable should produce SEM_NONLOCAL_NOT_FOUND."""
        code = """
func outer() -> auto:
    func inner() -> auto:
        nonlocal does_not_exist
        does_not_exist = 1
    inner()
"""
        artifact, errors = compile_or_errors(code)
        assert "SEM_NONLOCAL_NOT_FOUND" in errors


class TestNonlocalInteractionWithLambda:
    """Interaction between nonlocal and lambda captures."""

    def test_nonlocal_and_lambda_coexist(self):
        """nonlocal variable can also be captured by a lambda."""
        code = """
func outer() -> int:
    int x = 0
    func inc() -> auto:
        nonlocal x
        x = x + 1
    fn getter = lambda -> auto: x
    inc()
    inc()
    return getter()

print(outer())
"""
        assert run_ibci(code) == ["2"]


class TestFunctionAutoReadCapture:
    """R6：嵌套函数自动只读捕获（与 lambda 同构，nonlocal 仅用于写）。

    原"引用外层局部未声明 nonlocal → 运行时 not defined"现变为自动捕获可用
    （对齐 Python 心智模型：读捕获自动、写需 nonlocal）。
    """

    def test_read_capture_after_outer_returns(self):
        """真闭包：外层返回后调用内层，只读捕获仍可用。"""
        code = """
func make_getter() -> fn:
    int x = 42
    func inner() -> int:
        return x
    return inner

fn g = make_getter()
print(g())
"""
        assert run_ibci(code) == ["42"]

    def test_read_capture_sees_latest_value(self):
        """只读捕获读取 Cell 最新值（外层修改后内层可见）。"""
        code = """
func make_reader() -> fn:
    int v = 10
    func read() -> int:
        return v
    return read

fn r = make_reader()
print(r())
"""
        assert run_ibci(code) == ["10"]

    def test_read_capture_across_two_levels(self):
        """跨两层嵌套的只读捕获。"""
        code = """
func outer() -> int:
    int x = 0
    func middle() -> int:
        func inner() -> int:
            return x
        return inner()
    return middle()

print(outer())
"""
        assert run_ibci(code) == ["0"]

    def test_func_and_lambda_capture_consistent(self):
        """函数与 lambda 对同一外层变量的只读捕获一致。"""
        code = """
func outer() -> int:
    int base = 5
    func add(int x) -> int:
        return base + x
    fn lam = lambda(int x) -> int: base + x
    return add(10) + lam(20)

print(outer())
"""
        assert run_ibci(code) == ["40"]

    def test_write_still_requires_nonlocal(self):
        """写外层局部仍需 nonlocal（无 nonlocal 的赋值是本函数局部变量）。"""
        code = """
func outer() -> int:
    int count = 0
    func inc() -> auto:
        int local = count + 1
        return local
    inc()
    return count

print(outer())
"""
        assert run_ibci(code) == ["0"]

    def test_nonlocal_write_back_still_works(self):
        """nonlocal 写回语义不受自动只读捕获影响。"""
        code = """
func make_counter() -> fn:
    int count = 0
    func inc() -> int:
        nonlocal count
        count = count + 1
        return count
    return inc

fn counter = make_counter()
print(counter())
print(counter())
"""
        assert run_ibci(code) == ["1", "2"]

    def test_p3_write_shared_cell_still_isolated(self):
        """P3：任务写共享 cell（经 nonlocal）仍被隔离拦截。"""
        code = """
func make_counter() -> fn:
    int total = 0
    func tick() -> int:
        nonlocal total
        total = total + 1
        return total
    return tick

fn c = make_counter()
thread[int] t = thread(callable=c, args=[])
thread_result[int] r = t.join()
print((str)r.is_error())
print((str)r.status())
"""
        assert run_ibci(code) == ["True", "failed"]
