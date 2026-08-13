"""
tests/e2e/test_type_annotations_runtime.py — 类型标注运行时黑盒行为。

自 tests/compiler/test_type_annotations.py 拆分（mixed-concerns）：完整程序执行
用例（callable HOF / tuple 位置类型运行时）归 e2e/；纯编译期契约归
tests/compiler/test_type_annotations.py。
"""
from tests.conftest import expect_compile_error, run_ibci


# ──────────────────────────────────────────────────────── end-to-end runs ──

class TestCallableSigE2E:
    """Full execution: HOF with fn[(...)→(...)] parameters."""

    def test_apply_double(self):
        """HOF apply(fn[(int) -> int], int) runs correctly."""
        lines = run_ibci("""func double(int n) -> int:
    return n * 2

func apply(fn[(int) -> int] f, int x) -> int:
    return f(x)

int result = apply(double, 5)
print((str)result)
""")
        assert lines == ["10"]

    def test_apply_with_lambda(self):
        """HOF apply(fn[(int) -> int], int) works with a lambda."""
        lines = run_ibci("""func apply(fn[(int) -> int] f, int x) -> int:
    return f(x)

fn triple = lambda(int n) -> int: n * 3
int result = apply(triple, 4)
print((str)result)
""")
        assert lines == ["12"]

    def test_multi_param_predicate(self):
        """HOF check(fn[(int, int) -> bool], int, int) works."""
        lines = run_ibci("""func gt(int a, int b) -> bool:
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
        lines = run_ibci("""func get_ten() -> int:
    return 10

func call_it(fn[() -> int] f) -> int:
    return f()

int r = call_it(get_ten)
print((str)r)
""")
        assert lines == ["10"]

    def test_fn_sig_variable_callable(self):
        """fn[(int) -> int] variable pointing to a function, then called."""
        lines = run_ibci("""func square(int n) -> int:
    return n * n

fn[(int) -> int] f = square
int result = f(7)
print((str)result)
""")
        assert lines == ["49"]


################################################################################
# tuple[T1,T2,...] 位置类型推断
################################################################################

class TestTuplePositionalTypeInference:
    def test_int_str_literal_index(self):
        """`tuple[int, str] t = (1, "x"); int a = t[0]; str b = t[1]` 应通过类型检查。"""
        out = run_ibci("""
tuple[int, str] t = (1, "hello")
int a = t[0]
str b = t[1]
print(a)
print(b)
""")
        assert out == ["1", "hello"]

    def test_three_elements_positional(self):
        """三元位置类型 `tuple[int, str, bool]`。"""
        out = run_ibci("""
tuple[int, str, bool] t = (7, "z", True)
int a = t[0]
str b = t[1]
bool c = t[2]
print(a)
print(b)
print(c)
""")
        assert out == ["7", "z", "True"]


# ===========================================================================
# 2. 错误目标类型应触发 SEM_TYPE_MISMATCH
# ===========================================================================

class TestTuplePositionalTypeMismatch:
    def test_wrong_target_type_position_0(self):
        """位置 0 是 int，赋给 str 应报错。"""
        expect_compile_error("""
tuple[int, str] t = (1, "hello")
str bad = t[0]
""", "SEM_TYPE_MISMATCH")

    def test_wrong_target_type_position_1(self):
        """位置 1 是 str，赋给 int 应报错。"""
        expect_compile_error("""
tuple[int, str] t = (1, "hello")
int bad = t[1]
""", "SEM_TYPE_MISMATCH")


# ===========================================================================
# 3. 非字面量索引/越界 fallback 到 any（不报错）
# ===========================================================================

class TestTuplePositionalFallback:
    def test_variable_index_falls_back_to_any(self):
        """变量索引时回退到通用 fallback 路径。"""
        out = run_ibci("""
tuple[int, str] t = (1, "hello")
int i = 0
any x = t[i]
print(x)
""")
        assert out == ["1"]


# ===========================================================================
# 4. tuple[A, B] 可赋值给裸 tuple
# ===========================================================================

class TestTupleCovariance:
    def test_assign_positional_to_plain_tuple(self):
        """tuple[int, str] → tuple 兼容（已实现的 is_compatible）。"""
        out = run_ibci("""
tuple[int, str] t = (1, "x")
tuple plain = t
print(plain[0])
print(plain[1])
""")
        assert out == ["1", "x"]


# ===========================================================================
# 5. 顺序敏感：tuple[int, str] ≠ tuple[str, int]
# ===========================================================================

class TestTupleOrderSensitivity:
    def test_order_discriminates_specs(self):
        """`tuple[int, str]` 与 `tuple[str, int]` 必须是不同的位置类型。"""
        out = run_ibci("""
tuple[int, str] t1 = (1, "x")
tuple[str, int] t2 = ("y", 2)
int a = t1[0]
str b = t1[1]
str c = t2[0]
int d = t2[1]
print(a)
print(b)
print(c)
print(d)
""")
        assert out == ["1", "x", "y", "2"]

    def test_order_swap_target_type_mismatch(self):
        """对 `tuple[str, int]` 用 int 接 [0] 应失败（验证不被 sorted 缓存污染）。"""
        expect_compile_error("""
tuple[str, int] t = ("y", 2)
int bad = t[0]
""", "SEM_TYPE_MISMATCH")


# ===========================================================================
# 6. 单类型回退路径保留
# ===========================================================================

class TestTupleSingleTypeBackCompat:
    def test_single_element_type_path(self):
        """`tuple[int]` 走 element_type 单字段路径（不创建 positional_element_types）。"""
        out = run_ibci("""
tuple[int] t = (42,)
int a = t[0]
print(a)
""")
        assert out == ["42"]
