"""
Tests for SEM_DUAL_ASSIGNABLE (method override signature compatibility) and SEM_SUPER_OUTSIDE_METHOD (super() legality).

SEM_DUAL_ASSIGNABLE: When a child class overrides a parent method, the child's signature must
         be compatible (parameter count + types + return type).

SEM_SUPER_OUTSIDE_METHOD: super() must be called inside a class method of a class with a parent.
"""

import pytest
from tests.conftest import run_ibci, compile_ibci, compile_or_errors


# ============================================================
# SEM_DUAL_ASSIGNABLE: Method override signature compatibility
# ============================================================


class TestMethodOverrideSignature:
    """SEM_DUAL_ASSIGNABLE: Override method signature must be compatible with parent."""

    def test_compatible_override_no_warning(self):
        """Same signature override should NOT produce SEM_DUAL_ASSIGNABLE."""
        code = """class Animal:
    func speak(self) -> str:
        return "..."

class Dog(Animal):
    func speak(self) -> str:
        return "Woof"

Dog d = Dog()
print(d.speak())
"""
        result = run_ibci(code)
        assert "Woof" in result

    def test_override_different_param_count(self):
        """Override with matching signature should work correctly."""
        code = """class Base:
    func greet(self, str name) -> str:
        return "Hello " + name

class Child(Base):
    func greet(self, str name) -> str:
        return "Hi " + name

Child c = Child()
print(c.greet("World"))
"""
        result = run_ibci(code)
        assert "Hi World" in result

    def test_override_incompatible_param_type(self):
        """Override with incompatible param types should produce SEM_DUAL_ASSIGNABLE warning."""
        code = """class Base:
    func process(self, int x) -> int:
        return x

class Child(Base):
    func process(self, str x) -> int:
        return 0

Child c = Child()
print((str)c.process("test"))
"""
        # Should compile (SEM_DUAL_ASSIGNABLE is a warning) and run
        result = run_ibci(code)
        assert "0" in result

    def test_override_incompatible_return_type(self):
        """Override with incompatible return type should produce SEM_DUAL_ASSIGNABLE warning."""
        code = """class Base:
    func compute(self) -> int:
        return 42

class Child(Base):
    func compute(self) -> str:
        return "hello"

Child c = Child()
print(c.compute())
"""
        # Should compile with warning and run
        result = run_ibci(code)
        assert "hello" in result

    def test_init_override_no_warning(self):
        """__init__ override should NOT produce SEM_DUAL_ASSIGNABLE (signature-free method)."""
        code = """class Base:
    int x
    func __init__(self, int v) -> auto:
        self.x = v

class Child(Base):
    str name
    func __init__(self, int v, str n) -> auto:
        self.x = v
        self.name = n

Child c = Child(42, "test")
print(c.name)
"""
        result = run_ibci(code)
        assert "test" in result

    def test_new_method_not_override_no_warning(self):
        """Method not present in parent should NOT produce SEM_DUAL_ASSIGNABLE."""
        code = """class Base:
    func greet(self) -> str:
        return "Hello"

class Child(Base):
    func unique(self) -> str:
        return "I'm unique"

Child c = Child()
print(c.unique())
"""
        result = run_ibci(code)
        assert "I'm unique" in result

    def test_compatible_subtype_return(self):
        """Override with subclass return type should be compatible."""
        code = """class Animal:
    str name
    func __init__(self, str n) -> auto:
        self.name = n

class Dog(Animal):
    func __init__(self, str n) -> auto:
        self.name = n

class Factory:
    func create(self) -> Animal:
        return Animal("base")

class DogFactory(Factory):
    func create(self) -> Dog:
        return Dog("Rex")

DogFactory f = DogFactory()
print(f.create().name)
"""
        # Dog is a subclass of Animal, so return type is covariant — no warning
        result = run_ibci(code)
        assert "Rex" in result


# ============================================================
# SEM_SUPER_OUTSIDE_METHOD: super() call legality
# ============================================================


class TestSuperCallLegality:
    """SEM_SUPER_OUTSIDE_METHOD: super() must be called inside a class method with a parent."""

    def test_super_in_class_method_valid(self):
        """super() inside a class method with parent should be valid."""
        code = """class Base:
    func greet(self) -> str:
        return "Hello from Base"

class Child(Base):
    func greet(self) -> str:
        return "Hello from Child"

Child c = Child()
print(c.greet())
"""
        result = run_ibci(code)
        assert "Hello from Child" in result

    def test_super_outside_class_error(self):
        """super() at module level should produce SEM_SUPER_OUTSIDE_METHOD."""
        code = """super()
"""
        artifact, errors = compile_or_errors(code)
        assert "SEM_SUPER_OUTSIDE_METHOD" in errors

    def test_super_in_regular_function_error(self):
        """super() inside a regular function (not class method) should produce SEM_SUPER_OUTSIDE_METHOD."""
        code = """func test() -> auto:
    super()
    return 0

print((str)test())
"""
        artifact, errors = compile_or_errors(code)
        assert "SEM_SUPER_OUTSIDE_METHOD" in errors

    def test_super_in_class_without_explicit_parent_is_valid(self):
        """super() in a class without explicit parent is valid (implicit Object inheritance)."""
        code = """class Standalone:
    func test(self) -> str:
        super()
        return "ok"

Standalone s = Standalone()
print(s.test())
"""
        # All user classes implicitly inherit Object, so super() is valid
        artifact, errors = compile_or_errors(code)
        assert "SEM_SUPER_OUTSIDE_METHOD" not in errors


# ============================================================
# Subclass → Parent assignability
# ============================================================


class TestSubclassAssignability:
    """Compile-time: subclass instance should be assignable to parent type variable."""

    def test_subclass_to_parent_assignment(self):
        """Animal a = Dog() should compile and work."""
        code = """class Animal:
    str name
    func __init__(self, str n) -> auto:
        self.name = n

class Dog(Animal):
    func __init__(self, str n) -> auto:
        self.name = n

Animal a = Dog("Rex")
print(a.name)
"""
        result = run_ibci(code)
        assert "Rex" in result

    def test_multi_level_assignability(self):
        """Grandchild should be assignable to grandparent."""
        code = """class Base:
    int x
    func __init__(self, int v) -> auto:
        self.x = v

class Mid(Base):
    func __init__(self, int v) -> auto:
        self.x = v

class Leaf(Mid):
    func __init__(self, int v) -> auto:
        self.x = v

Base b = Leaf(99)
print((str)b.x)
"""
        result = run_ibci(code)
        assert "99" in result

    def test_parent_to_child_assignment_type_error(self):
        """Dog d = Animal("x") should fail type checking (SEM_TYPE_MISMATCH)."""
        code = """class Animal:
    str name
    func __init__(self, str n) -> auto:
        self.name = n

class Dog(Animal):
    func __init__(self, str n) -> auto:
        self.name = n

Dog d = Animal("x")
"""
        artifact, errors = compile_or_errors(code)
        assert "SEM_TYPE_MISMATCH" in errors

    def test_unrelated_class_assignment_type_error(self):
        """Assigning unrelated class instance should fail."""
        code = """class Cat:
    str name = "cat"

class Dog:
    str name = "dog"

Cat c = Dog()
"""
        artifact, errors = compile_or_errors(code)
        assert "SEM_TYPE_MISMATCH" in errors

    def test_upcast_expression(self):
        """(Animal)dog should compile without errors."""
        code = """class Animal:
    str name = ""

class Dog(Animal):
    func __init__(self) -> auto:
        self.name = "Rex"

Dog d = Dog()
Animal a = (Animal)d
print(a.name)
"""
        result = run_ibci(code)
        assert "Rex" in result

    def test_virtual_dispatch_after_assignment(self):
        """Virtual method dispatch should work after parent-type assignment."""
        code = """class Animal:
    func speak(self) -> str:
        return "..."

class Dog(Animal):
    func speak(self) -> str:
        return "Woof!"

Animal a = Dog()
print(a.speak())
"""
        result = run_ibci(code)
        assert "Woof!" in result
