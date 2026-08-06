"""
tests/e2e/test_e2e_for_filter_compound.py
==========================================

for...if 过滤与复合赋值运算符的 e2e 覆盖（此前两特性零 e2e 测试）。

覆盖：
* ``for T name in iterable if filter:`` 过滤（数值/字符串/函数调用条件）。
* 复合赋值：``+=`` / ``-=`` / ``*=`` / ``/=`` / ``%=`` / ``**=``（int/float/str/list）。
"""
from tests.conftest import run_ibci


class TestForIfFiltering:
    """for...if 过滤语法。"""

    def test_numeric_filter(self):
        lines = run_ibci(
            "for int x in [1, 2, 3, 4] if x % 2 == 0:\n"
            "    print(x)\n"
        )
        assert lines == ["2", "4"]

    def test_string_filter_with_len(self):
        lines = run_ibci(
            'for str s in ["a", "bb", "c"] if len(s) > 1:\n'
            "    print(s)\n"
        )
        assert lines == ["bb"]

    def test_filter_keeps_original_skip(self):
        """被过滤掉的元素不进入循环体（体计数仅对命中项生效）。"""
        lines = run_ibci(
            "int count = 0\n"
            "for int x in [1, 2, 3] if x >= 2:\n"
            "    count = count + 1\n"
            "print(count)\n"
        )
        assert lines == ["2"]

    def test_for_if_with_enumerate(self):
        lines = run_ibci(
            'for (int i, str s) in enumerate(["a", "b", "c"]) if i % 2 == 0:\n'
            "    print(i, s)\n"
        )
        assert lines == ["0 a", "2 c"]


class TestCompoundAssignment:
    """复合赋值运算符。"""

    def test_add_assign_int(self):
        assert run_ibci("int x = 1\nx += 2\nprint(x)\n") == ["3"]

    def test_sub_assign_int(self):
        assert run_ibci("int x = 5\nx -= 2\nprint(x)\n") == ["3"]

    def test_mul_assign_int(self):
        assert run_ibci("int x = 3\nx *= 4\nprint(x)\n") == ["12"]

    def test_div_assign_float(self):
        assert run_ibci("float x = 10.0\nx /= 2\nprint(x)\n") == ["5.0"]

    def test_mod_assign_int(self):
        assert run_ibci("int x = 7\nx %= 3\nprint(x)\n") == ["1"]

    def test_pow_assign_int(self):
        assert run_ibci("int x = 2\nx **= 3\nprint(x)\n") == ["8"]

    def test_add_assign_str(self):
        assert run_ibci('str s = "a"\ns += "b"\nprint(s)\n') == ["ab"]

    def test_add_assign_list(self):
        assert run_ibci(
            "list[int] l = [1]\nl += [2]\nprint(l)\n"
        ) == ["[1, 2]"]

    def test_compound_assign_in_loop(self):
        """复合赋值与 for...if 结合（累加命中项）。"""
        lines = run_ibci(
            "int total = 0\n"
            "for int x in [1, 2, 3, 4] if x % 2 == 0:\n"
            "    total += x\n"
            "print(total)\n"
        )
        assert lines == ["6"]
