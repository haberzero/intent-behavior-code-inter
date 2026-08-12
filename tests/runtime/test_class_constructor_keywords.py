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
    func __init__(self, int x, int y) -> auto:
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

class TestClassConstructionCPS:
    """A5 类构造接入帧内 CPS：__init__ 含 Waitable 时 auto-yield，不阻塞主调度线程。"""

    def test_init_with_llm_behavior_constructs(self):
        """__init__ 内含 LLM 行为（Waitable）→ 类构造 auto-yield 帧内驱动，正确返回实例。"""
        from tests.conftest import AI_MOCK_PREFIX
        code = AI_MOCK_PREFIX + """
class Box:
    str label
    func __init__(self, str seed) -> void:
        self.label = @~ MOCK:STR:hi-$seed ~
Box b = Box("world")
print(b.label)
"""
        lines = run_ibci(code)
        assert lines and "hi-world" in lines[0]

    def test_init_with_channel_waitable_completes(self):
        """__init__ 内含 chan.recv（Waitable，由独立线程喂）→ 构造完成不阻塞/死锁。"""
        code = """
chan c = chan(int, "stream")
func feeder(chan x) -> int:
    x.send(42)
    return 1
class Box:
    int v
    func __init__(self) -> void:
        int a = c.recv()
        self.v = a
thread[int] t = thread(callable=feeder, args=[c])
Box b = Box()
print((str)b.v)
thread_result[int] r = t.join()
print((str)r.expect())
"""
        lines = run_ibci(code)
        assert lines == ["42", "1"]
