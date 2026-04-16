"""
tests/e2e/test_e2e_modules.py

End-to-end tests for IBCI module imports and plugin usage.

Coverage:
  - import math + math operations
  - import json + json operations
  - import time + time operations
  - import schema + schema validation
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
# 1. Math module
# ---------------------------------------------------------------------------

class TestE2EMathModule:
    def test_math_sqrt(self):
        code = """import math
float result = math.sqrt(16.0)
print((str)result)
"""
        lines = run_and_capture(code)
        assert any("4" in l for l in lines)

    def test_math_pow(self):
        code = """import math
float result = math.pow(2.0, 10.0)
print((str)result)
"""
        lines = run_and_capture(code)
        assert any("1024" in l for l in lines)

    def test_math_abs(self):
        code = """import math
float result = math.abs(-42.0)
print((str)result)
"""
        lines = run_and_capture(code)
        assert any("42" in l for l in lines)

    def test_math_floor_ceil(self):
        code = """import math
int f = math.floor(3.7)
int c = math.ceil(3.2)
print((str)f)
print((str)c)
"""
        lines = run_and_capture(code)
        assert "3" in lines
        assert "4" in lines

    def test_math_pi(self):
        code = """import math
float p = math.pi
print((str)p)
"""
        lines = run_and_capture(code)
        assert any("3.14" in l for l in lines)

    def test_math_round(self):
        code = """import math
float result = math.round(3.14159, 2)
print((str)result)
"""
        lines = run_and_capture(code)
        assert any("3.14" in l for l in lines)


# ---------------------------------------------------------------------------
# 2. JSON module
# ---------------------------------------------------------------------------

class TestE2EJsonModule:
    def test_json_parse(self):
        code = """import json
dict d = json.parse("{\\\"name\\\": \\\"Alice\\\"}")
print((str)d)
"""
        lines = run_and_capture(code)
        assert any("Alice" in l for l in lines)

    def test_json_stringify(self):
        code = """import json
dict d = {"key": "value"}
str s = json.stringify(d)
print(s)
"""
        lines = run_and_capture(code)
        assert any("key" in l for l in lines)

    def test_json_keys(self):
        code = """import json
dict d = {"a": 1, "b": 2}
list k = json.keys(d)
print((str)k)
"""
        lines = run_and_capture(code)
        assert any("a" in l and "b" in l for l in lines)

    def test_json_merge(self):
        code = """import json
dict a = {"x": 1}
dict b = {"y": 2}
dict merged = json.merge(a, b)
print((str)merged)
"""
        lines = run_and_capture(code)
        assert any("x" in l and "y" in l for l in lines)


# ---------------------------------------------------------------------------
# 3. Time module
# ---------------------------------------------------------------------------

class TestE2ETimeModule:
    def test_time_now(self):
        code = """import time
float t = time.now()
print((str)t)
"""
        lines = run_and_capture(code)
        # Should be a positive number
        assert len(lines) > 0
        assert float(lines[0]) > 0

    def test_time_now_ms(self):
        code = """import time
int t = time.now_ms()
print((str)t)
"""
        lines = run_and_capture(code)
        assert len(lines) > 0
        assert int(lines[0]) > 0


# ---------------------------------------------------------------------------
# 4. Schema module
# ---------------------------------------------------------------------------

class TestE2ESchemaModule:
    def test_schema_validate(self):
        code = """import schema
dict data = {"name": "Alice", "age": 30}
dict rules = {"required": ["name"], "properties": {"name": {"type": "string"}, "age": {"type": "integer"}}}
bool valid = schema.validate(data, rules)
print((str)valid)
"""
        lines = run_and_capture(code)
        assert any("true" in l.lower() or "True" in l for l in lines)

    def test_schema_infer(self):
        code = """import schema
dict data = {"name": "Alice", "age": 30}
dict inferred = schema.infer(data)
print((str)inferred)
"""
        lines = run_and_capture(code)
        assert any("string" in l or "integer" in l for l in lines)
