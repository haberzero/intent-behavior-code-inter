"""
tests/e2e/test_retroactive_impl_methods.py — retroactive implementation
can supply missing protocol methods (declaration → method-addition form).

Covers: full pipeline (parse → semantic → artifact → hydration → execution),
conflict / target / body validation, inheritance visibility, and protocol
bound interaction.
"""

import pytest

from tests.conftest import run_ibci, compile_ibci
from core.kernel.issue import CompilerError


class TestImplSuppliesMethods:
    def test_impl_supplies_missing_method_with_self(self):
        """impl 补充缺失协议方法；方法体可读 self 字段。"""
        code = """
protocol Greeter:
    func greet(self) -> str:
        pass

class Foo:
    str tag

impl Greeter for Foo:
    func greet(self) -> str:
        return "hi " + self.tag

Foo f = Foo("x")
print(f.greet())
"""
        assert run_ibci(code) == ["hi x"]

    def test_impl_supplies_multiple_methods(self):
        code = """
protocol Render:
    func render(self) -> str:
        pass
    func kind(self) -> str:
        pass

class Item:
    str name

impl Render for Item:
    func render(self) -> str:
        return "[" + self.kind() + ":" + self.name + "]"
    func kind(self) -> str:
        return "item"

print(Item("a").render())
"""
        assert run_ibci(code) == ["[item:a]"]

    def test_impl_two_blocks_for_two_protocols(self):
        """同一类型多个 impl 块（不同协议）各自补充方法。"""
        code = """
protocol A:
    func a(self) -> str:
        pass

protocol B:
    func b(self) -> str:
        pass

class C:
    pass

impl A for C:
    func a(self) -> str:
        return "a"

impl B for C:
    func b(self) -> str:
        return "b"

C c = C()
print(c.a() + c.b())
"""
        assert run_ibci(code) == ["ab"]

    def test_impl_method_visible_on_subclass(self):
        """父类 impl 补充的方法对子类实例可见（lookup_method 继承链）。"""
        code = """
protocol P:
    func m(self) -> str:
        pass

class Base:
    pass

impl P for Base:
    func m(self) -> str:
        return "m"

class Child(Base):
    pass

print(Child().m())
"""
        assert run_ibci(code) == ["m"]

    def test_impl_method_usable_as_generic_bound(self):
        """impl 补方法后满足协议 bound：可作 Box[T: P] 的实参。"""
        code = """
protocol Greeter:
    func greet(self) -> str:
        pass

class Foo:
    pass

impl Greeter for Foo:
    func greet(self) -> str:
        return "hi"

class Box[T: Greeter]:
    T value
    func get(self) -> T:
        return self.value

Box[Foo] b = Box[Foo](Foo())
print(b.get().greet())
"""
        assert run_ibci(code) == ["hi"]

    def test_impl_declaration_only_form_still_valid(self):
        """空 body 声明式（向后兼容）：类型已满足协议时仅记录。"""
        code = """
protocol P:
    func m(self) -> int:
        pass

class C:
    func m(self) -> int:
        return 7

impl P for C:

print(C().m())
"""
        assert run_ibci(code) == ["7"]

    def test_impl_operator_dunder_method_binds(self):
        """impl 补充运算符 dunder 方法与类方法路径同构：运算符派发生效。"""
        code = """
protocol Addable:
    func __add__(self, any other) -> any:
        pass

class Pair:
    int v
    func value(self) -> int:
        return self.v

impl Addable for Pair:
    func __add__(self, Pair other) -> Pair:
        return Pair(self.v + other.v)

Pair a = Pair(1)
Pair b = Pair(2)
print((a + b).value())
"""
        assert run_ibci(code) == ["3"]

    def test_impl_init_suppresses_auto_init(self):
        """impl 补 __init__：auto-init 跳过（与用户显式构造器优先同语义）。"""
        code = """
protocol Named:
    func name(self) -> str:
        pass

class Box:
    str tag

impl Named for Box:
    func name(self) -> str:
        return self.tag
    func __init__(self, str prefix, str tag) -> auto:
        self.tag = prefix + ":" + tag

print(Box("p", "x").name())
"""
        assert run_ibci(code) == ["p:x"]

    def test_impl_supplies_protocol_method(self):
        """impl 方法补充协议方法（P4c 迁移：llm func 方法机制删除，
        方法恒为普通 func——本用例验证 impl 补充机制本身）。"""
        code = """
protocol P:
    func m(self) -> int:
        pass

class C:
    pass

impl P for C:
    func m(self) -> int:
        return 42

print(C().m())
"""
        assert run_ibci(code) == ["42"]


class TestImplValidation:
    def test_missing_method_still_errors(self):
        """impl（含补充）仍未覆盖全部协议方法 → 编译期错误。"""
        code = """
protocol P:
    func a(self) -> int:
        pass
    func b(self) -> int:
        pass

class C:
    func a(self) -> int:
        return 1

impl P for C:
    func a(self) -> int:
        return 1
"""
        with pytest.raises(CompilerError):
            compile_ibci(code)

    def test_conflict_with_existing_member_errors(self):
        """impl 方法名与类自身成员冲突 → fail-fast。"""
        code = """
protocol P:
    func m(self) -> int:
        pass

class C:
    func m(self) -> int:
        return 1

impl P for C:
    func m(self) -> int:
        return 2
"""
        with pytest.raises(CompilerError):
            compile_ibci(code)

    def test_conflict_across_two_impl_blocks_errors(self):
        """两个 impl 块提供同名方法 → fail-fast（跨块冲突）。"""
        code = """
protocol A:
    func m(self) -> int:
        pass

protocol B:
    func n(self) -> int:
        pass

class C:
    pass

impl A for C:
    func m(self) -> int:
        return 1

impl B for C:
    func m(self) -> int:
        return 2
    func n(self) -> int:
        return 3
"""
        with pytest.raises(CompilerError):
            compile_ibci(code)

    def test_generic_target_errors(self):
        code = """
protocol P:
    func m(self) -> int:
        pass

class Box[T]:
    T v

impl P for Box:
    func m(self) -> int:
        return 1
"""
        with pytest.raises(CompilerError):
            compile_ibci(code)

    def test_dynamic_builtin_target_errors(self):
        """内置类型可作 impl 目标（见 test_retroactive_impl_builtin.py），
        但动态逃生类型 any/auto 仍不可（对一切协议恒满足，impl 无意义）。"""
        code = """
protocol P:
    func m(self) -> int:
        pass

impl P for any:
    func m(self) -> int:
        return 1
"""
        with pytest.raises(CompilerError):
            compile_ibci(code)

    def test_non_function_body_errors(self):
        code = """
protocol P:
    func m(self) -> int:
        pass

class C:
    pass

impl P for C:
    int x = 1
"""
        with pytest.raises(CompilerError):
            compile_ibci(code)

    def test_unknown_protocol_errors(self):
        code = """
class C:
    pass

impl Missing for C:
    func m(self) -> int:
        return 1
"""
        with pytest.raises(CompilerError):
            compile_ibci(code)

    def test_unknown_target_errors(self):
        code = """
protocol P:
    func m(self) -> int:
        pass

impl P for Missing:
    func m(self) -> int:
        return 1
"""
        with pytest.raises(CompilerError):
            compile_ibci(code)

    def test_signature_mismatch_errors(self):
        """impl 补充的方法签名与协议不兼容 → 编译期错误。"""
        code = """
protocol P:
    func m(self, int x) -> int:
        pass

class C:
    pass

impl P for C:
    func m(self, str s) -> int:
        return 1
"""
        with pytest.raises(CompilerError):
            compile_ibci(code)
