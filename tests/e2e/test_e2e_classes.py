"""
tests/e2e/test_e2e_classes.py

End-to-end tests for IBCI class definitions and enum types.

Coverage:
  - Class definition with fields and methods
  - Class instantiation
  - Method calls on instances
  - Enum definition
  - Switch-case with enums
"""

import os
import pytest
from core.engine import IBCIEngine


def run_and_capture(code: str):
    lines = []
    def callback(text):
        lines.append(str(text))
    engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
    engine.run_string(code, output_callback=callback, silent=True)
    return lines


# ---------------------------------------------------------------------------
# 1. Class definitions
# ---------------------------------------------------------------------------

class TestE2EClasses:
    def test_simple_class(self):
        code = """class Dog:
    str name
    int age

    func bark(self) -> str:
        return "Woof!"

Dog d = Dog("Rex", 5)
print(d.bark())
"""
        lines = run_and_capture(code)
        assert "Woof!" in lines

    def test_class_field_access(self):
        code = """class Point:
    int x
    int y

Point p = Point(10, 20)
print((str)p.x)
print((str)p.y)
"""
        lines = run_and_capture(code)
        assert "10" in lines
        assert "20" in lines

    def test_class_method_with_args(self):
        code = """class Calculator:
    int value

    func add(self, int n) -> int:
        return self.value + n

Calculator c = Calculator(10)
int result = c.add(5)
print((str)result)
"""
        lines = run_and_capture(code)
        assert "15" in lines


# ---------------------------------------------------------------------------
# 2. Enum types
# ---------------------------------------------------------------------------

class TestE2EEnums:
    def test_enum_definition_and_access(self):
        code = """class Color(Enum):
    str RED = "RED"
    str GREEN = "GREEN"
    str BLUE = "BLUE"

print((str)Color.RED)
"""
        lines = run_and_capture(code)
        assert "RED" in lines

    def test_enum_comparison(self):
        code = """class Status(Enum):
    str ACTIVE = "ACTIVE"
    str INACTIVE = "INACTIVE"

Status s = Status.ACTIVE
if s == Status.ACTIVE:
    print("is active")
else:
    print("not active")
"""
        lines = run_and_capture(code)
        assert "is active" in lines

    def test_switch_case(self):
        code = """class Color(Enum):
    str RED = "RED"
    str GREEN = "GREEN"
    str BLUE = "BLUE"

Color c = Color.BLUE
switch c:
    case Color.RED:
        print("red")
    case Color.BLUE:
        print("blue")
    default:
        print("other")
"""
        lines = run_and_capture(code)
        assert "blue" in lines


# ---------------------------------------------------------------------------
# 3. Multiple instances
# ---------------------------------------------------------------------------

class TestE2EMultipleInstances:
    def test_two_instances_independent(self):
        code = """class Counter:
    int count

Counter a = Counter(0)
Counter b = Counter(10)
print((str)a.count)
print((str)b.count)
"""
        lines = run_and_capture(code)
        assert "0" in lines
        assert "10" in lines


# ---------------------------------------------------------------------------
# 4. Explicit __init__ constructor
# ---------------------------------------------------------------------------

class TestE2EExplicitInit:
    def test_explicit_init_is_called(self):
        """func __init__ is called as constructor and can override field values"""
        code = """class Greeter:
    str name

    func __init__(self, str n):
        self.name = "Hello, " + n

Greeter g = Greeter("World")
print(g.name)
"""
        lines = run_and_capture(code)
        assert "Hello, World" in lines

    def test_auto_init_positional(self):
        """Auto-generated __init__ assigns positional args to declaration-only fields"""
        code = """class Point:
    int x
    int y

Point p = Point(3, 7)
print((str)p.x)
print((str)p.y)
"""
        lines = run_and_capture(code)
        assert "3" in lines
        assert "7" in lines

    def test_explicit_init_overrides_auto_init(self):
        """When func __init__ is defined, it takes complete control; auto-init is NOT generated"""
        code = """class Pair:
    int a
    int b

    func __init__(self, int x, int y):
        self.a = x * 2
        self.b = y * 2

Pair p = Pair(3, 4)
print((str)p.a)
print((str)p.b)
"""
        lines = run_and_capture(code)
        assert "6" in lines
        assert "8" in lines

    def test_plain_func_init_is_not_constructor(self):
        """func init (without __) is a regular method, not the constructor"""
        code = """class Box:
    int value

    func init(self, int v):
        self.value = 999

Box b = Box(42)
print((str)b.value)
b.init(1)
print((str)b.value)
"""
        lines = run_and_capture(code)
        # constructor used auto-init (42), not func init
        assert "42" in lines
        # explicit call to init() method worked
        assert "999" in lines


# ---------------------------------------------------------------------------
# Inheritance tests
# ---------------------------------------------------------------------------

class TestE2EClassInheritance:
    """Test class inheritance: child class accessing parent members."""

    def test_child_accesses_parent_field(self):
        """Child class can access fields defined in parent class."""
        code = """class Animal:
    str name
    func __init__(self, str n):
        self.name = n

class Dog(Animal):
    str breed
    func __init__(self, str n, str b):
        self.name = n
        self.breed = b

Dog d = Dog("Rex", "Lab")
print(d.name)
print(d.breed)
"""
        lines = run_and_capture(code)
        assert "Rex" in lines
        assert "Lab" in lines

    def test_child_accesses_parent_method(self):
        """Child class can call methods defined in parent class."""
        code = """class Animal:
    str name
    func __init__(self, str n):
        self.name = n
    func describe(self) -> str:
        return "I am " + self.name

class Dog(Animal):
    str breed
    func __init__(self, str n, str b):
        self.name = n
        self.breed = b

Dog d = Dog("Rex", "Lab")
print(d.describe())
"""
        lines = run_and_capture(code)
        assert "I am Rex" in lines

    def test_child_overrides_parent_method(self):
        """Child class can override parent methods."""
        code = """class Animal:
    str name
    func __init__(self, str n):
        self.name = n
    func speak(self) -> str:
        return "..."

class Cat(Animal):
    func __init__(self, str n):
        self.name = n
    func speak(self) -> str:
        return "Meow"

Cat c = Cat("Kitty")
print(c.speak())
print(c.name)
"""
        lines = run_and_capture(code)
        assert "Meow" in lines
        assert "Kitty" in lines

    def test_multi_level_inheritance(self):
        """Multi-level inheritance: grandchild accesses grandparent members."""
        code = """class Base:
    int x
    func __init__(self, int v):
        self.x = v

class Mid(Base):
    int y
    func __init__(self, int v, int w):
        self.x = v
        self.y = w

class Leaf(Mid):
    int z
    func __init__(self, int a, int b, int c):
        self.x = a
        self.y = b
        self.z = c

Leaf obj = Leaf(1, 2, 3)
print((str)obj.x)
print((str)obj.y)
print((str)obj.z)
"""
        lines = run_and_capture(code)
        assert "1" in lines
        assert "2" in lines
        assert "3" in lines


# ---------------------------------------------------------------------------
# User-class equality operator (P0 fix: __eq__ must return bool, not int)
# ---------------------------------------------------------------------------

class TestE2EClassEquality:
    """Tests for == / != on user-defined class instances (P0 bug fix)."""

    def test_identity_equality_same_reference(self):
        """o1 == o1 should be true (same reference)."""
        code = """class Obj:
    int x
    func __init__(self, int v):
        self.x = v

Obj o1 = Obj(5)
bool same = o1 == o1
print((str)same)
"""
        lines = run_and_capture(code)
        assert "True" in lines

    def test_identity_equality_different_instances(self):
        """o1 == o2 (different instances, same value) should be false."""
        code = """class Obj:
    int x
    func __init__(self, int v):
        self.x = v

Obj o1 = Obj(5)
Obj o2 = Obj(5)
bool different = o1 == o2
print((str)different)
"""
        lines = run_and_capture(code)
        assert "False" in lines

    def test_equality_assigned_reference(self):
        """o3 = o1; o3 == o1 should be true."""
        code = """class Obj:
    int x
    func __init__(self, int v):
        self.x = v

Obj o1 = Obj(42)
Obj o3 = o1
bool same_ref = o3 == o1
print((str)same_ref)
"""
        lines = run_and_capture(code)
        assert "True" in lines

    def test_not_equal_different_instances(self):
        """o1 != o2 (different instances) should be true."""
        code = """class Obj:
    int x
    func __init__(self, int v):
        self.x = v

Obj o1 = Obj(5)
Obj o2 = Obj(5)
bool ne = o1 != o2
print((str)ne)
"""
        lines = run_and_capture(code)
        assert "True" in lines

    def test_equality_in_if_condition(self):
        """class equality in if-condition should work without type error."""
        code = """class Pt:
    int x
    func __init__(self, int v):
        self.x = v

Pt a = Pt(1)
Pt b = a
if a == b:
    print("same")
else:
    print("different")
"""
        lines = run_and_capture(code)
        assert "same" in lines

    def test_equality_result_is_bool_not_int(self):
        """== result must be assignable to bool variable (was returning int before fix)."""
        code = """class Node:
    int val
    func __init__(self, int v):
        self.val = v

Node n1 = Node(10)
Node n2 = Node(10)
bool eq_result = n1 == n2
bool same_result = n1 == n1
print((str)eq_result)
print((str)same_result)
"""
        lines = run_and_capture(code)
        assert "False" in lines
        assert "True" in lines
