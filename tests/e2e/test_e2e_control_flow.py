"""
tests/e2e/test_e2e_control_flow.py

End-to-end tests for IBCI control flow constructs.

Coverage:
  - if / else / elif
  - while loops
  - for-in loops
  - break / continue
  - Nested control flow
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
# 1. if / else
# ---------------------------------------------------------------------------

class TestE2EIfElse:
    def test_if_true_branch(self):
        code = """int x = 10
if x > 5:
    print("big")
"""
        lines = run_and_capture(code)
        assert "big" in lines

    def test_else_branch(self):
        code = """int x = 3
if x > 5:
    print("big")
else:
    print("small")
"""
        lines = run_and_capture(code)
        assert "small" in lines

    def test_nested_if(self):
        code = """int x = 10
if x > 5:
    if x > 8:
        print("very big")
    else:
        print("medium")
"""
        lines = run_and_capture(code)
        assert "very big" in lines


# ---------------------------------------------------------------------------
# 2. while loops
# ---------------------------------------------------------------------------

class TestE2EWhileLoop:
    def test_simple_while(self):
        code = """int i = 0
while i < 3:
    print((str)i)
    i = i + 1
"""
        lines = run_and_capture(code)
        assert "0" in lines
        assert "1" in lines
        assert "2" in lines

    def test_while_with_break(self):
        code = """int i = 0
while true:
    if i >= 3:
        break
    print((str)i)
    i = i + 1
"""
        lines = run_and_capture(code)
        assert "0" in lines
        assert "1" in lines
        assert "2" in lines
        assert len([l for l in lines if l in ("0", "1", "2")]) == 3

    def test_while_with_continue(self):
        code = """int i = 0
while i < 5:
    i = i + 1
    if i == 3:
        continue
    print((str)i)
"""
        lines = run_and_capture(code)
        assert "3" not in lines
        assert "1" in lines
        assert "2" in lines
        assert "4" in lines


# ---------------------------------------------------------------------------
# 3. for-in loops
# ---------------------------------------------------------------------------

class TestE2EForLoop:
    def test_for_in_list(self):
        code = """list items = [10, 20, 30]
for int item in items:
    print((str)item)
"""
        lines = run_and_capture(code)
        assert "10" in lines
        assert "20" in lines
        assert "30" in lines

    def test_for_in_string_list(self):
        code = """list names = ["Alice", "Bob", "Charlie"]
for str name in names:
    print(name)
"""
        lines = run_and_capture(code)
        assert "Alice" in lines
        assert "Bob" in lines
        assert "Charlie" in lines


# ---------------------------------------------------------------------------
# 4. Nested control flow
# ---------------------------------------------------------------------------

class TestE2ENestedControl:
    def test_for_with_if(self):
        code = """list items = [1, 2, 3, 4, 5]
for int item in items:
    if item % 2 == 0:
        print((str)item)
"""
        lines = run_and_capture(code)
        assert "2" in lines
        assert "4" in lines
        assert "1" not in lines
        assert "3" not in lines

    def test_while_in_if(self):
        code = """bool run = true
if run:
    int count = 0
    while count < 3:
        count = count + 1
    print((str)count)
"""
        lines = run_and_capture(code)
        assert "3" in lines
