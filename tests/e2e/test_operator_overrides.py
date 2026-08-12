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
