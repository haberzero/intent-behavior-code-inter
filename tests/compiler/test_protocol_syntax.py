"""
tests/compiler/test_protocol_syntax.py — minimal protocol declaration syntax (compile-only).
"""

from tests.conftest import compile_ibci


class TestProtocolDeclaration:
    def test_protocol_declaration_compiles(self):
        code = """
protocol Greeter:
    func greet(self) -> str:
        pass

print("ok")
"""
        artifact = compile_ibci(code)
        assert artifact is not None

    def test_protocol_with_multiple_methods_compiles(self):
        code = """
protocol Serializable:
    func to_dict(self) -> dict:
        pass
    func from_dict(self, dict raw) -> any:
        pass

print("ok")
"""
        assert compile_ibci(code) is not None


class TestClassImplementsProtocol:
    def test_class_implements_protocol_compiles(self):
        code = """
protocol Greeter:
    func greet(self) -> str:
        pass

class Foo implements Greeter:
    func greet(self) -> str:
        return "hi"
"""
        assert compile_ibci(code) is not None

    def test_class_missing_protocol_method_fails(self):
        from tests.conftest import expect_compile_error
        code = """
protocol Greeter:
    func greet(self) -> str:
        pass

class Foo implements Greeter:
    pass
"""
        expect_compile_error(code, "SEM_TYPE_MISMATCH")
