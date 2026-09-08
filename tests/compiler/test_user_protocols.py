"""
tests/compiler/test_user_protocols.py

A1 用户自定义协议/类型类一等公民——机制回归锁定：

协议是方法签名的命名集合，用作类型约束（06_oop 协议节）：
- `protocol Name:` 声明（方法签名 + pass 体）；
- 类经结构判定满足协议（方法签名存在即满足——satisfies_protocol
  用户协议路径：无内置判定声明 → required methods 全部结构判定）；
- 类型参数 bound（`class Box[T: Shape]`）：符合参数通过 / 违约编译期
  fail-fast（SEM_TYPE_MISMATCH）；
- 协议继承（`protocol Child(Parent):`）。
"""

import pytest

from core.engine import IBCIEngine
from core.kernel.issue import CompilerError


@pytest.fixture
def engine():
    return IBCIEngine(root_dir=".")

_PROTO_HEAD = """protocol Shape:
    func area(self) -> float:
        pass
"""

_CIRCLE = """class Circle:
    float r
    func __init__(self, float r) -> auto:
        self.r = r
    func area(self) -> float:
        return 3.14 * self.r * self.r
"""


class TestProtocolDeclaration:
    def test_declare_and_use_end_to_end(self, engine):
        """协议声明 + 类实现 + 泛型容器 + 运行期调用（端到端）。"""
        out = []
        engine.run_string(
            _PROTO_HEAD
            + _CIRCLE
            + """class Box[T]:
    T v
    func __init__(self, T v) -> auto:
        self.v = v
    func get(self) -> T:
        return self.v
Circle c = Circle(2.0)
Box[Circle] b = Box[Circle](c)
float a = b.get().area()
print("area=" + (str)a)
""",
            output_callback=out.append, silent=True)
        assert out and "area=12.56" in out[0]


class TestTypeParamBounds:
    def test_conforming_argument(self, engine):
        """bound 符合参数（Box[Circle]）——编译通过 + 运行正确。"""
        out = []
        engine.run_string(
            _PROTO_HEAD
            + _CIRCLE
            + """class Box[T: Shape]:
    T v
    func __init__(self, T v) -> auto:
        self.v = v
    func total(self) -> float:
        return self.v.area()
Circle c = Circle(1.0)
Box[Circle] b = Box[Circle](c)
float t = b.total()
print("bound-ok=" + (str)t)
""",
            output_callback=out.append, silent=True)
        assert out and "bound-ok=3.14" in out[0]

    def test_violating_argument_fail_fast(self, engine):
        """bound 违约（Box[int]——int 无 area）——编译期 fail-fast。"""
        with pytest.raises(CompilerError) as exc:
            engine.compile_string(
                _PROTO_HEAD
                + """class Box[T: Shape]:
    T v
    func __init__(self, T v) -> auto:
        self.v = v
Box[int] b = Box[int](1)
""",
                silent=True)
        assert any("SEM_TYPE_MISMATCH" == d.code for d in exc.value.diagnostics)


class TestProtocolInheritance:
    def test_child_requires_parent_methods(self, engine):
        """协议继承（protocol Colored(Shape)）——子协议含父协议方法要求。"""
        out = []
        engine.run_string(
            _PROTO_HEAD
            + """protocol Colored(Shape):
    func color(self) -> str:
        pass
"""
            + _CIRCLE
            + """    func color(self) -> str:
        return "red"
Circle c = Circle(1.0)
print("inherit-ok=" + c.color())
""",
            output_callback=out.append, silent=True)
        assert out and "inherit-ok=red" in out[0]
