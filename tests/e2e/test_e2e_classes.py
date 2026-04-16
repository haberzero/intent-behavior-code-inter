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

    def bark(self) -> str:
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

    def add(self, int n) -> int:
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
