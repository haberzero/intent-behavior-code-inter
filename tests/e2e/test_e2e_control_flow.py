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


# ---------------------------------------------------------------------------
# 5. Filter syntax (for ... if and while ... if)
# ---------------------------------------------------------------------------

class TestE2EFilterSyntax:
    def test_for_in_if_filter_even(self):
        """for int n in items if n % 2 == 0: should only process even numbers"""
        code = """list numbers = [1, 2, 3, 4, 5, 6]
for int n in numbers if n % 2 == 0:
    print((str)n)
"""
        lines = run_and_capture(code)
        assert "2" in lines
        assert "4" in lines
        assert "6" in lines
        assert "1" not in lines
        assert "3" not in lines
        assert "5" not in lines

    def test_for_in_if_filter_no_match(self):
        """filter that matches nothing should produce no output"""
        code = """list numbers = [1, 3, 5]
for int n in numbers if n % 2 == 0:
    print((str)n)
print("done")
"""
        lines = run_and_capture(code)
        assert "done" in lines
        assert "1" not in lines
        assert "3" not in lines
        assert "5" not in lines

    def test_for_in_if_filter_with_string_items(self):
        """filter on string length"""
        code = """list words = ["a", "bb", "ccc", "dd", "e"]
for str w in words if w.find("c") >= 0:
    print(w)
"""
        lines = run_and_capture(code)
        assert "ccc" in lines
        assert "a" not in lines

    def test_while_if_filter_body_runs_when_filter_passes(self):
        """while...if continue semantics: body runs every iteration when filter is always true"""
        code = """int i = 0
while i < 5 if i >= 0:
    i = i + 1
print((str)i)
"""
        lines = run_and_capture(code)
        assert "5" in lines

    def test_while_if_filter_body_skipped_when_main_condition_false(self):
        """while main condition is false from the start, body never runs regardless of filter"""
        code = """int i = 0
int counter = 0
while i > 10 if i < 100:
    counter = counter + 1
print((str)counter)
"""
        lines = run_and_capture(code)
        assert "0" in lines

    def test_while_if_continue_semantics_body_only_when_filter_true(self):
        """while...if: body executes only when filter is true; loop continues otherwise"""
        code = """int i = 0
int executed = 0
while i < 3 if true:
    executed = executed + 1
    i = i + 1
print((str)executed)
"""
        lines = run_and_capture(code)
        assert "3" in lines

    def test_for_in_if_filter_all_match(self):
        """filter that matches all elements"""
        code = """list nums = [2, 4, 6]
for int n in nums if n % 2 == 0:
    print((str)n)
"""
        lines = run_and_capture(code)
        assert "2" in lines
        assert "4" in lines
        assert "6" in lines

    def test_for_in_if_filter_break_works(self):
        """break inside a filtered for loop should work correctly"""
        code = """list nums = [1, 2, 3, 4, 5, 6]
for int n in nums if n % 2 == 0:
    if n == 4:
        break
    print((str)n)
"""
        lines = run_and_capture(code)
        assert "2" in lines
        assert "4" not in lines
        assert "6" not in lines


# ---------------------------------------------------------------------------
# 6. Condition-driven for with if filter  (for @~...~ if cond:)
# ---------------------------------------------------------------------------

class TestE2EConditionDrivenForIf:
    """Tests for condition-driven for-loop with an if-filter (parser P0 fix)."""

    def _run(self, code: str):
        from core.engine import IBCIEngine
        lines = []
        engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
        engine.run_string(
            'import ai\nai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n' + code,
            output_callback=lambda t: lines.append(str(t)),
            silent=True,
        )
        return lines

    def test_condition_driven_for_if_filter_terminates(self):
        """for @~MOCK:TRUE cond~ if count < 3: should stop when filter fails."""
        code = """int count = 0
for @~ MOCK:TRUE loop_cond ~ if count < 3:
    count = count + 1
print((str)count)
"""
        lines = self._run(code)
        assert "3" in lines

    def test_condition_driven_for_if_filter_never_entered(self):
        """if filter is immediately false, loop body must not execute."""
        code = """int count = 0
for @~ MOCK:TRUE loop_cond ~ if count > 100:
    count = count + 1
print((str)count)
"""
        lines = self._run(code)
        assert "0" in lines

    def test_condition_driven_for_if_filter_with_static_condition(self):
        """loop body runs while the static condition holds."""
        code = """int x = 0
for @~ MOCK:TRUE always ~ if x < 5:
    x = x + 1
print((str)x)
"""
        lines = self._run(code)
        assert "5" in lines
