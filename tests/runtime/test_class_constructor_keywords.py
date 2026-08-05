"""
类构造关键字参数支持测试。

锁定：用户类关键字构造（auto_init 字段 / 显式 __init__）在运行时正确解析。
- ``Dog(name="Rex", age=5)`` → 关键字按字段名绑定
- ``Point(x=10, y=20)`` → 显式 __init__ 关键字绑定
- 位置参数与关键字参数共存
"""

from tests.conftest import run_ibci


def test_auto_init_keyword_construction():
    code = """
class Dog:
    str name
    int age

Dog d = Dog(name="Rex", age=5)
print(d.name)
print((str)d.age)
"""
    lines = run_ibci(code)
    assert lines == ["Rex", "5"]


def test_auto_init_keyword_construction_order_independent():
    code = """
class Dog:
    str name
    int age

Dog d = Dog(age=5, name="Rex")
print(d.name)
print((str)d.age)
"""
    lines = run_ibci(code)
    assert lines == ["Rex", "5"]


def test_explicit_init_keyword_construction():
    code = """
class Point:
    int x
    int y
    func __init__(self, int x, int y):
        self.x = x
        self.y = y

Point p = Point(x=10, y=20)
print((str)p.x)
print((str)p.y)
"""
    lines = run_ibci(code)
    assert lines == ["10", "20"]


def test_mixed_positional_keyword_construction():
    code = """
class Cfg:
    str host
    int port

Cfg c = Cfg("localhost", port=8080)
print(c.host)
print((str)c.port)
"""
    lines = run_ibci(code)
    assert lines == ["localhost", "8080"]