"""
tests/e2e/test_operator_overrides.py

用户类运算符覆写覆盖度回归测试（KNOWN_LIMITS §十四 #2 核对，2026-08-12）。

实测锁定：比较（==/!=/</>/<=/>=）、算术（+/-/*/%）、一元（-/~/not）、
成员（in via __contains__）均可经 dunder 方法覆写；`is` 恒为身份比较。
"""

from tests.conftest import run_ibci


class TestComparisonOperators:
    def test_eq_and_ne(self):
        code = """class T:
    int x
    func __eq__(self, T other) -> bool:
        return self.x == other.x
    func __ne__(self, T other) -> bool:
        return self.x != other.x
T a = T(1)
T b = T(2)
print((str)(a == T(1)))
print((str)(a != b))
"""
        out = run_ibci(code)
        assert out == ["True", "True"]

    def test_ordering(self):
        code = """class T:
    int x
    func __lt__(self, T other) -> bool:
        return self.x < other.x
    func __gt__(self, T other) -> bool:
        return self.x > other.x
    func __le__(self, T other) -> bool:
        return self.x <= other.x
    func __ge__(self, T other) -> bool:
        return self.x >= other.x
T a = T(1)
T b = T(2)
print((str)(a < b))
print((str)(b > a))
print((str)(a <= T(1)))
print((str)(b >= T(2)))
"""
        out = run_ibci(code)
        assert out == ["True", "True", "True", "True"]


class TestArithmeticOperators:
    def test_add_sub_mul_mod(self):
        code = """class T:
    int x
    func __add__(self, T other) -> T:
        return T(self.x + other.x)
    func __sub__(self, T other) -> T:
        return T(self.x - other.x)
    func __mul__(self, T other) -> T:
        return T(self.x * other.x)
    func __mod__(self, T other) -> T:
        return T(self.x % other.x)
T a = T(10)
print((str)(a + T(5)).x)
print((str)(a - T(3)).x)
print((str)(a * T(2)).x)
print((str)(a % T(4)).x)
"""
        out = run_ibci(code)
        assert out == ["15", "7", "20", "2"]


class TestUnaryOperators:
    def test_neg_invert_not(self):
        code = """class T:
    int x
    func __neg__(self) -> T:
        return T(-self.x)
    func __invert__(self) -> T:
        return T(~self.x)
    func __not__(self) -> bool:
        return self.x == 0
T a = T(5)
T z = T(0)
print((str)(-a).x)
print((str)(~a).x)
print((str)(not z))
"""
        out = run_ibci(code)
        assert out == ["-5", "-6", "True"]


class TestContainment:
    def test_contains(self):
        code = """class T:
    int x
    func __contains__(self, int v) -> bool:
        return self.x == v
T a = T(5)
print((str)(5 in a))
print((str)(3 in a))
"""
        out = run_ibci(code)
        assert out == ["True", "False"]


class TestIsIsIdentity:
    def test_is_identity_not_overridable(self):
        """`is` 恒为身份比较（Python 语义），用户类不可覆写。"""
        code = """class T:
    int x
    func __is__(self, T other) -> bool:
        return True
T a = T(1)
T b = T(1)
print((str)(a is b))
print((str)(a is a))
"""
        out = run_ibci(code)
        assert out == ["False", "True"]


class TestGenericOperatorOverrides:
    """GEN-6A：泛型类 × 运算符重载——返回类型特化（KERNEL_ISSUE-GEN-6 判别性回归）。

    运算符方法返回 `Vec[T]` 时，`a + b` 结果类型须为特化 `Vec[int]`（resolve_op
    经 resolve_typeref 保留实参），而非降级为基类 Vec。
    修复前：SEM_TYPE_MISMATCH: Cannot assign 'Vec' to 'Vec[int]'。
    """

    def test_generic_add_returns_specialized(self):
        code = """class Vec[T]:
    T x
    T y
    func __init__(self, T x, T y) -> void:
        self.x = x
        self.y = y
    func __add__(self, Vec[T] other) -> Vec[T]:
        return Vec[T](self.x + other.x, self.y + other.y)
    func __eq__(self, Vec[T] other) -> bool:
        return self.x == other.x and self.y == other.y

Vec[int] a = Vec[int](1, 2)
Vec[int] b = Vec[int](3, 4)
Vec[int] c = a + b
print("cx=" + (str)c.x)
print("cy=" + (str)c.y)
print("eq=" + (str)(a == Vec[int](1, 2)))
print("neq=" + (str)(a == b))
"""
        out = run_ibci(code)
        assert out == ["cx=4", "cy=6", "eq=True", "neq=False"]

    def test_generic_add_bare_T_param(self):
        """裸 T 参数 + 泛型返回同样生效（触发因子是返回类型，非参数形态）。"""
        code = """class Box[T]:
    T value
    func __init__(self, T value) -> void:
        self.value = value
    func __add__(self, T other) -> Box[T]:
        return Box[T](self.value + other)
Box[int] b = Box[int](1)
Box[int] c = b + 2
print((str)c.value)
"""
        out = run_ibci(code)
        assert out == ["3"]

    def test_generic_add_in_expression_context(self):
        """泛型运算符结果在嵌套表达式（如 list 元素）中使用。"""
        code = """class Vec[T]:
    T x
    T y
    func __init__(self, T x, T y) -> void:
        self.x = x
        self.y = y
    func __add__(self, Vec[T] other) -> Vec[T]:
        return Vec[T](self.x + other.x, self.y + other.y)
Vec[int] a = Vec[int](1, 2)
Vec[int] b = Vec[int](3, 4)
list[Vec[int]] lst = [a + b]
print((str)lst[0].x)
"""
        out = run_ibci(code)
        assert out == ["4"]
