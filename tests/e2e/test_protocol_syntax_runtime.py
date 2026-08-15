"""
tests/e2e/test_protocol_syntax_runtime.py — protocol declaration runtime no-op.
"""

from tests.conftest import run_ibci


class TestProtocolDeclarationRuntime:
    def test_protocol_declaration_runs_as_noop(self):
        code = """
protocol Greeter:
    func greet(self) -> str:
        pass

print("ok")
"""
        assert run_ibci(code) == ["ok"]

    def test_protocol_with_multiple_methods_runs(self):
        code = """
protocol Serializable:
    func to_dict(self) -> dict:
        pass
    func from_dict(self, dict raw) -> any:
        pass

print("ok")
"""
        assert run_ibci(code) == ["ok"]


class TestClassImplementsProtocolRuntime:
    def test_class_implements_protocol_runs(self):
        code = """
protocol Greeter:
    func greet(self) -> str:
        pass

class Foo implements Greeter:
    func greet(self) -> str:
        return "hi"

print(Foo().greet())
"""
        assert run_ibci(code) == ["hi"]


class TestProtocolInheritanceRuntime:
    def test_protocol_inheritance_runs(self):
        code = """
protocol Base:
    func base(self) -> str:
        pass

protocol Child(Base):
    func child(self) -> str:
        pass

class Foo implements Child:
    func base(self) -> str:
        return "b"
    func child(self) -> str:
        return "c"

print(Foo().base() + Foo().child())
"""
        assert run_ibci(code) == ["bc"]


class TestGenericProtocolBoundsRuntime:
    def test_bounded_generic_class_runs(self):
        code = """
protocol Greeter:
    func greet(self) -> str:
        pass

class Foo implements Greeter:
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
