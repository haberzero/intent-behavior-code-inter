"""
tests/runtime/test_builtin_expansion.py
========================================

内建函数群完善测试：

* 类型转换全局函数：``int(x)`` / ``str(x)`` / ``float(x)`` / ``bool(x)``
  （此前仅 ``(int) x`` 强转语法可用，全局函数调用缺位）。
* 序列辅助：``enumerate`` / ``zip`` / ``sorted``。
* for 循环元组解包：``for (int i, int v) in ...``（编译器符号注册修复）。
"""
from tests_v2.conftest import run_ibci


class TestTypeConversionGlobals:
    """基本类型转换全局函数。"""

    def test_int_from_str(self):
        assert run_ibci('int a = int("42")\nprint(a)\n') == ["42"]

    def test_int_from_float_truncates(self):
        assert run_ibci("int a = int(3.9)\nprint(a)\n") == ["3"]

    def test_str_from_int(self):
        assert run_ibci("str s = str(42)\nprint(s)\n") == ["42"]

    def test_float_from_str(self):
        assert run_ibci('float f = float("3.5")\nprint(f)\n') == ["3.5"]

    def test_bool_from_int(self):
        assert run_ibci("bool b = bool(1)\nprint(b)\n") == ["True"]

    def test_bool_from_zero_is_false(self):
        assert run_ibci("bool b = bool(0)\nprint(b)\n") == ["False"]

    def test_zero_arg_conversions(self):
        assert run_ibci("int a = int()\nfloat f = float()\nbool b = bool()\nprint(a, f, b)\n") == ["0 0.0 False"]

    def test_conversions_compose(self):
        assert run_ibci('int a = int(str(7))\nprint(a)\n') == ["7"]


class TestSequenceHelpers:
    """enumerate / zip / sorted 序列辅助内建。"""

    def test_enumerate(self):
        lines = run_ibci(
            'list l = ["a", "b"]\n'
            "for (int i, str v) in enumerate(l):\n"
            "    print(i, v)\n"
        )
        assert lines == ["0 a", "1 b"]

    def test_zip(self):
        lines = run_ibci(
            "list a = [1, 2]\n"
            'list b = ["x", "y"]\n'
            "for (int n, str c) in zip(a, b):\n"
            "    print(n, c)\n"
        )
        assert lines == ["1 x", "2 y"]

    def test_zip_unequal_truncates_to_shortest(self):
        lines = run_ibci(
            "list a = [1, 2, 3]\n"
            'list b = ["x"]\n'
            "for (int n, str c) in zip(a, b):\n"
            "    print(n, c)\n"
        )
        assert lines == ["1 x"]

    def test_sorted_returns_new_list(self):
        """sorted 返回新列表，不改动原容器。"""
        lines = run_ibci(
            "list[int] l = [3, 1, 2]\n"
            "list[int] s = sorted(l)\n"
            "print(s)\n"
            "print(l)\n"
        )
        assert lines == ["[1, 2, 3]", "[3, 1, 2]"]

    def test_sorted_strings(self):
        assert run_ibci(
            'list[str] l = ["b", "a"]\n'
            "print(sorted(l))\n"
        ) == ["[a, b]"]

    def test_enumerate_iterates_in_index_order(self):
        lines = run_ibci(
            "list[int] l = [5, 6]\n"
            "for (int i, int v) in enumerate(l):\n"
            "    print(i, v)\n"
        )
        assert lines == ["0 5", "1 6"]


class TestAggregationBuiltins:
    """sum / reversed / all / min / max 聚合与迭代内建。"""

    def test_sum(self):
        assert run_ibci("list[int] l = [1, 2, 3]\nprint(sum(l))\n") == ["6"]

    def test_sum_float(self):
        assert run_ibci("list[float] l = [1.5, 2.5]\nprint(sum(l))\n") == ["4.0"]

    def test_sum_shadowable(self):
        """sum 内建名可被用户变量遮蔽（遮蔽修复使 sum 重新纳入成为可能）。"""
        code = "int sum = 0\nsum = sum + 5\nprint(sum)\n"
        assert run_ibci(code) == ["5"]

    def test_reversed_returns_new_list(self):
        """reversed 返回新逆序列表，不改动原容器。"""
        lines = run_ibci(
            "list[int] l = [1, 2, 3]\n"
            "list[int] r = reversed(l)\n"
            "print(r)\n"
            "print(l)\n"
        )
        assert lines == ["[3, 2, 1]", "[1, 2, 3]"]

    def test_all_true(self):
        assert run_ibci("list[bool] l = [True, True]\nprint(all(l))\n") == ["True"]

    def test_all_false(self):
        assert run_ibci("list[bool] l = [True, False]\nprint(all(l))\n") == ["False"]

    def test_min_and_max_over_collection(self):
        assert run_ibci(
            "list[int] l = [3, 1, 2]\nprint(min(l))\nprint(max(l))\n"
        ) == ["1", "3"]

    def test_min_and_max_varargs(self):
        assert run_ibci("print(min(3, 1, 2))\nprint(max(3, 1, 2))\n") == ["1", "3"]

    def test_min_strings(self):
        assert run_ibci('print(min(["c", "a", "b"]))\n') == ["a"]


class TestForLoopTupleUnpacking:
    """for 循环元组解包（编译器符号注册修复）。"""

    def test_typed_tuple_unpacking(self):
        lines = run_ibci(
            "for (int i, int v) in [(1, 2), (3, 4)]:\n"
            "    print(i, v)\n"
        )
        assert lines == ["1 2", "3 4"]

    def test_mixed_type_tuple_unpacking(self):
        lines = run_ibci(
            'for (int i, str v) in [(1, "a")]:\n'
            "    print(i, v)\n"
        )
        assert lines == ["1 a"]

    def test_triple_unpacking(self):
        lines = run_ibci(
            "for (int a, int b, int c) in [(1, 2, 3)]:\n"
            "    print(a + b + c)\n"
        )
        assert lines == ["6"]
