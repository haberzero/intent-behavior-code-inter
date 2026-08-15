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


class TestProtocolInheritance:
    def test_protocol_inheritance_compiles(self):
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
"""
        assert compile_ibci(code) is not None

    def test_protocol_inheritance_missing_parent_method_fails(self):
        from tests.conftest import expect_compile_error
        code = """
protocol Base:
    func base(self) -> str:
        pass

protocol Child(Base):
    func child(self) -> str:
        pass

class Foo implements Child:
    func child(self) -> str:
        return "c"
"""
        expect_compile_error(code, "SEM_TYPE_MISMATCH")


class TestGenericProtocolBounds:
    def test_bounded_generic_class_compiles(self):
        code = """
protocol Greeter:
    func greet(self) -> str:
        pass

class Foo implements Greeter:
    func greet(self) -> str:
        return "hi"

class Box[T: Greeter]:
    T value
"""
        assert compile_ibci(code) is not None

    def test_bounded_generic_class_rejects_non_conforming_arg(self):
        from tests.conftest import expect_compile_error
        code = """
protocol Greeter:
    func greet(self) -> str:
        pass

class Box[T: Greeter]:
    T value

Box[int] b = Box[int](1)
"""
        expect_compile_error(code, "SEM_TYPE_MISMATCH")


class TestGenericFunctions:
    def test_generic_identity_compiles(self):
        code = """
func identity[T](T x) -> T:
    return x

int a = identity(42)
str b = identity("hi")
"""
        assert compile_ibci(code) is not None

    def test_bounded_generic_function_compiles(self):
        code = """
protocol Greeter:
    func greet(self) -> str:
        pass

class Foo implements Greeter:
    func greet(self) -> str:
        return "hi"

func call_greet[T: Greeter](T x) -> str:
    return x.greet()

str s = call_greet(Foo())
"""
        assert compile_ibci(code) is not None

    def test_bounded_generic_function_rejects_non_conforming_arg(self):
        from tests.conftest import expect_compile_error
        code = """
protocol Greeter:
    func greet(self) -> str:
        pass

class Foo implements Greeter:
    func greet(self) -> str:
        return "hi"

func call_greet[T: Greeter](T x) -> str:
    return x.greet()

str s = call_greet(42)
"""
        expect_compile_error(code, "SEM_TYPE_MISMATCH")


class TestProtocolMethodSignatureChecking:
    def test_protocol_wrong_param_count_fails(self):
        from tests.conftest import expect_compile_error
        code = """
protocol Greeter:
    func greet(self, str name) -> str:
        pass

class Foo implements Greeter:
    func greet(self) -> str:
        return "hi"
"""
        expect_compile_error(code, "SEM_TYPE_MISMATCH")

    def test_protocol_wrong_param_type_fails(self):
        from tests.conftest import expect_compile_error
        code = """
protocol Greeter:
    func greet(self, str name) -> str:
        pass

class Foo implements Greeter:
    func greet(self, int name) -> str:
        return "hi"
"""
        expect_compile_error(code, "SEM_TYPE_MISMATCH")

    def test_protocol_wrong_return_type_fails(self):
        from tests.conftest import expect_compile_error
        code = """
protocol Greeter:
    func greet(self) -> str:
        pass

class Foo implements Greeter:
    func greet(self) -> int:
        return 1
"""
        expect_compile_error(code, "SEM_TYPE_MISMATCH")


class TestGenericProtocols:
    def test_generic_protocol_compiles(self):
        code = """
protocol Container[T]:
    func get(self) -> T:
        pass

class Box implements Container[int]:
    func get(self) -> int:
        return 42
"""
        assert compile_ibci(code) is not None

    def test_generic_protocol_wrong_return_fails(self):
        from tests.conftest import expect_compile_error
        code = """
protocol Container[T]:
    func get(self) -> T:
        pass

class Box implements Container[int]:
    func get(self) -> str:
        return "x"
"""
        expect_compile_error(code, "SEM_TYPE_MISMATCH")
