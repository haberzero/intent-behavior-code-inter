"""
tests/e2e/test_e2e_tuple_unpack.py

End-to-end tests for tuple destructuring declarations and for-loop tuple unpack.

Coverage:
  - 括号形式 `(int x, int y) = t` （历史能力，回归保护）
  - 裸列形式 `int a, int b = t` （小任务 §1）
  - `for (int x, int y) in coords:` 类型标注元组循环目标 （小任务 §2）
  - 混合类型解包 / auto 解包 / 元数错误检测
"""

import os
import pytest
from core.engine import IBCIEngine
from core.kernel.issue import CompilerError


def run_and_capture(code: str):
    lines = []

    def callback(text):
        lines.append(str(text))

    engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
    engine.run_string(code, output_callback=callback, silent=True)
    return lines


class TestParenthesizedTupleDecl:
    def test_basic_paren_decl(self):
        code = """(int a, int b) = (10, 20)
print(a)
print(b)
"""
        assert run_and_capture(code) == ["10", "20"]

    def test_paren_decl_from_var(self):
        code = """tuple t = (1, 2)
(int x, int y) = t
print(x)
print(y)
"""
        assert run_and_capture(code) == ["1", "2"]

    def test_paren_decl_mixed_types(self):
        code = """(int a, str b) = (1, "x")
print(a)
print(b)
"""
        assert run_and_capture(code) == ["1", "x"]


class TestBareCommaTupleDecl:
    """裸列形式：无需外层括号即可元组解包声明（与 Python `a, b = t` 对齐）。"""

    def test_bare_two_int(self):
        code = """tuple t = (1, 2)
int a, int b = t
print(a)
print(b)
"""
        assert run_and_capture(code) == ["1", "2"]

    def test_bare_three_int(self):
        code = """tuple t = (10, 20, 30)
int a, int b, int c = t
print(a)
print(b)
print(c)
"""
        assert run_and_capture(code) == ["10", "20", "30"]

    def test_bare_mixed_types(self):
        code = """int p, str q = (3, "hi")
print(p)
print(q)
"""
        assert run_and_capture(code) == ["3", "hi"]

    def test_bare_with_auto(self):
        code = """tuple t = (1, 2)
auto x, auto y = t
print(x)
print(y)
"""
        assert run_and_capture(code) == ["1", "2"]

    def test_bare_mixed_auto_typed(self):
        code = """auto a, int b = (5, 6)
print(a)
print(b)
"""
        assert run_and_capture(code) == ["5", "6"]


class TestForTupleUnpack:
    """for (int x, int y) in coords: 类型标注元组循环目标。"""

    def test_for_typed_tuple_target(self):
        code = """list[tuple] coords = [(1, 2), (3, 4)]
for (int x, int y) in coords:
    print(x)
    print(y)
"""
        assert run_and_capture(code) == ["1", "2", "3", "4"]

    def test_for_mixed_types(self):
        code = """list[tuple] pairs = [(1, "a"), (2, "b")]
for (int n, str s) in pairs:
    print(n)
    print(s)
"""
        assert run_and_capture(code) == ["1", "a", "2", "b"]

    def test_for_uses_unpacked_var_in_body(self):
        code = """list[tuple] coords = [(10, 1), (20, 2), (30, 3)]
int total = 0
for (int x, int y) in coords:
    total = total + x + y
print(total)
"""
        assert run_and_capture(code) == ["66"]


class TestUnpackErrors:
    """元数检查与错误传播。"""

    def test_paren_decl_arity_mismatch_runtime(self):
        # 元数错误在运行时由 _assign_to_target 抛出 RUN_001
        code = """(int a, int b) = (1, 2, 3)
print(a)
"""
        with pytest.raises(Exception):
            run_and_capture(code)

    def test_bare_decl_arity_mismatch_runtime(self):
        code = """int a, int b = (1, 2, 3)
print(a)
"""
        with pytest.raises(Exception):
            run_and_capture(code)
