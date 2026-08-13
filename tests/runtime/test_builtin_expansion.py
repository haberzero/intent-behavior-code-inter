"""
tests/runtime/test_builtin_expansion.py
========================================

内建函数群完善测试：

* 类型转换全局函数：``int(x)`` / ``str(x)`` / ``float(x)`` / ``bool(x)``
  （与 ``(int) x`` 强转语法并存，全局函数调用可用）。
* 序列辅助：``enumerate`` / ``zip`` / ``sorted``。
* for 循环元组解包：``for (int i, int v) in ...``（依赖编译器符号注册）。
"""
import pytest

from tests.conftest import run_ibci


class TestTypeConversionGlobals:
    """基本类型转换全局函数。"""

    @pytest.mark.parametrize("code,expected", [
        pytest.param('int a = int("42")\nprint(a)\n', "42", id="int_from_str"),
        pytest.param("int a = int(3.9)\nprint(a)\n", "3", id="int_from_float_truncates"),
        pytest.param("str s = str(42)\nprint(s)\n", "42", id="str_from_int"),
        pytest.param('float f = float("3.5")\nprint(f)\n', "3.5", id="float_from_str"),
        pytest.param("bool b = bool(1)\nprint(b)\n", "True", id="bool_from_int"),
        pytest.param("bool b = bool(0)\nprint(b)\n", "False", id="bool_from_zero_is_false"),
        pytest.param(
            "int a = int()\nfloat f = float()\nbool b = bool()\nprint(a, f, b)\n",
            "0 0.0 False",
            id="zero_arg_conversions",
        ),
        pytest.param("int a = int(str(7))\nprint(a)\n", "7", id="conversions_compose"),
    ])
    def test_type_conversion(self, code, expected):
        assert run_ibci(code) == [expected]


class TestSequenceHelpers:
    """enumerate / zip / sorted 序列辅助内建。"""

    @pytest.mark.parametrize("code,expected", [
        pytest.param(
            'list l = ["a", "b"]\n'
            "for (int i, str v) in enumerate(l):\n"
            "    print(i, v)\n",
            ["0 a", "1 b"],
            id="enumerate",
        ),
        pytest.param(
            "list a = [1, 2]\n"
            'list b = ["x", "y"]\n'
            "for (int n, str c) in zip(a, b):\n"
            "    print(n, c)\n",
            ["1 x", "2 y"],
            id="zip",
        ),
        pytest.param(
            "list a = [1, 2, 3]\n"
            'list b = ["x"]\n'
            "for (int n, str c) in zip(a, b):\n"
            "    print(n, c)\n",
            ["1 x"],
            id="zip_unequal_truncates_to_shortest",
        ),
        pytest.param(
            'list[str] l = ["b", "a"]\n'
            "print(sorted(l))\n",
            ["[a, b]"],
            id="sorted_strings",
        ),
        pytest.param(
            "list[int] l = [5, 6]\n"
            "for (int i, int v) in enumerate(l):\n"
            "    print(i, v)\n",
            ["0 5", "1 6"],
            id="enumerate_iterates_in_index_order",
        ),
    ])
    def test_sequence_helper(self, code, expected):
        assert run_ibci(code) == expected

    def test_sorted_returns_new_list(self):
        """sorted 返回新列表，不改动原容器。"""
        lines = run_ibci(
            "list[int] l = [3, 1, 2]\n"
            "list[int] s = sorted(l)\n"
            "print(s)\n"
            "print(l)\n"
        )
        assert lines == ["[1, 2, 3]", "[3, 1, 2]"]


class TestAggregationBuiltins:
    """sum / reversed / all / min / max 聚合与迭代内建。"""

    @pytest.mark.parametrize("code,expected", [
        pytest.param("list[int] l = [1, 2, 3]\nprint(sum(l))\n", ["6"], id="sum"),
        pytest.param("list[float] l = [1.5, 2.5]\nprint(sum(l))\n", ["4.0"], id="sum_float"),
        pytest.param(
            "list[bool] l = [True, True]\nprint(all(l))\n",
            ["True"],
            id="all_true",
        ),
        pytest.param(
            "list[bool] l = [True, False]\nprint(all(l))\n",
            ["False"],
            id="all_false",
        ),
        pytest.param(
            "list[int] l = [3, 1, 2]\nprint(min(l))\nprint(max(l))\n",
            ["1", "3"],
            id="min_and_max_over_collection",
        ),
        pytest.param(
            "print(min(3, 1, 2))\nprint(max(3, 1, 2))\n",
            ["1", "3"],
            id="min_and_max_varargs",
        ),
        pytest.param(
            'print(min(["c", "a", "b"]))\n',
            ["a"],
            id="min_strings",
        ),
    ])
    def test_aggregation_builtin(self, code, expected):
        assert run_ibci(code) == expected

    def test_sum_shadowable(self):
        """sum 内建名可被用户变量遮蔽（遮蔽后使用点解析到用户变量，优先于内建名）。"""
        code = "int sum = 0\nsum = sum + 5\nprint(sum)\n"
        assert run_ibci(code) == ["5"]

    def test_sum_shadowable_with_llm_init(self):
        """内建名遮蔽 + LLM 表达式初始化：dispatch-before-use 路径也必须走 define 遮蔽。

        模块级 ``int sum = @~...~`` 经 define 遮蔽创建新符号；不得在
        ``_assign_future_to_name_target`` 原地覆写 ``intrinsic:sum`` 常量符号
        （否则使用点回写触发 ``Cannot reassign constant UID 'intrinsic:sum'``）。
        """
        code = (
            "import ai\n"
            "ai.set_mock_mode()\n"
            "int sum = @~ MOCK:INT:42 ~\n"
            "print((str)sum)\n"
        )
        assert run_ibci(code) == ["42"]

    def test_len_shadowable_with_llm_init(self):
        """另一个内建名（len）+ LLM 表达式初始化遮蔽（同一 define 遮蔽路径）。"""
        code = (
            "import ai\n"
            "ai.set_mock_mode()\n"
            "int len = @~ MOCK:INT:42 ~\n"
            "print((str)len)\n"
        )
        assert run_ibci(code) == ["42"]


    def test_reversed_returns_new_list(self):
        """reversed 返回新逆序列表，不改动原容器。"""
        lines = run_ibci(
            "list[int] l = [1, 2, 3]\n"
            "list[int] r = reversed(l)\n"
            "print(r)\n"
            "print(l)\n"
        )
        assert lines == ["[3, 2, 1]", "[1, 2, 3]"]


class TestForLoopTupleUnpacking:
    """for 循环元组解包（依赖编译器符号注册）。"""

    @pytest.mark.parametrize("code,expected", [
        pytest.param(
            "for (int i, int v) in [(1, 2), (3, 4)]:\n"
            "    print(i, v)\n",
            ["1 2", "3 4"],
            id="typed_tuple_unpacking",
        ),
        pytest.param(
            'for (int i, str v) in [(1, "a")]:\n'
            "    print(i, v)\n",
            ["1 a"],
            id="mixed_type_tuple_unpacking",
        ),
        pytest.param(
            "for (int a, int b, int c) in [(1, 2, 3)]:\n"
            "    print(a + b + c)\n",
            ["6"],
            id="triple_unpacking",
        ),
    ])
    def test_tuple_unpacking(self, code, expected):
        assert run_ibci(code) == expected
