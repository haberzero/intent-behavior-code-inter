"""语言行为层：代表性语言行为测试（内核无关可观察面断言）。

R3 测试体系五层重构·语言行为层种子——数据面 / 诊断码 + 现场位置断言。
断言面纪律：可观察面 + 诊断码 + 结构化现场，禁实现内部形态 / 消息子串。
"""

from tests.behavior.helpers import assert_compile_error, assert_error, assert_output


class TestDataPlane:
    """数据面（print 输出）——代表性语言行为，内核无关。"""

    def test_arithmetic(self):
        assert_output("print(1 + 2 * 3)\n", ["7"])
        assert_output("print(10 / 4)\n", ["2"])          # IBC / = floor 除
        assert_output("print(7 % 3)\n", ["1"])
        assert_output("print(2 ** 10)\n", ["1024"])
        assert_output("print(-5 + 3)\n", ["-2"])
        assert_output("print(1 + 2.5)\n", ["3.5"])       # int + float = float

    def test_typed_numeric_precision(self):
        """R2-3a typed 数值：i64 精确（消灭 f64 全包精度丢失）。"""
        assert_output("print(9007199254740993 + 1)\n", ["9007199254740994"])
        assert_output("print(-7 // 2)\n", ["-4"])        # floor 除向负无穷
        assert_output("print(-7 % 2)\n", ["1"])          # mod 符号随除数
        assert_output("print(9007199254740993 == 9007199254740992)\n", ["False"])

    def test_bounded_int_overflow(self):
        """i64 有界契约（打破清单 #5）：超界 = 显式 OverflowError。"""
        assert_error("print(9223372036854775807 + 1)\n", "RUN_GENERIC_ERROR")

    def test_control_flow(self):
        assert_output("x = 7\nif x > 5:\n    print('big')\n", ["big"])
        assert_output(
            "s = 0\nfor i in range(1, 4):\n    s = s + i\nprint(s)\n",
            ["6"],
        )
        assert_output(
            "i = 0\nwhile i < 3:\n    print(i)\n    i = i + 1\n",
            ["0", "1", "2"],
        )

    def test_containers(self):
        assert_output("xs = [1, 2, 3]\nxs.append(4)\nprint(len(xs))\n", ["4"])
        assert_output("xs = [1, 2, 3]\nxs[0] = 99\nprint(xs)\n", ["[99, 2, 3]"])
        assert_output("d = {'a': 1}\nprint(d['a'])\n", ["1"])
        # dict 键：bool == 数值（Python 契约：True 命中 1 键）
        assert_output("d = {1: 'a'}\nprint(d[True])\n", ["a"])

    def test_strings(self):
        assert_output("print('a' + 'b')\n", ["ab"])
        # IBCI 显示语义：容器 str 元素不带引号（Python 参考实证 [a, b]）
        assert_output("print('a,b'.split(','))\n", ["[a, b]"])
        # R2-1：无参 split = 空白切分（Python 契约）
        assert_output("print('a  b'.split())\n", ["[a, b]"])
        assert_output("print('hello'.upper())\n", ["HELLO"])
        assert_output("print(len('abc'))\n", ["3"])

    def test_functions(self):
        assert_output(
            "func add(int a, int b) -> int:\n    return a + b\nprint(add(2, 3))\n",
            ["5"],
        )
        assert_output(
            "func fact(int n) -> int:\n"
            "    if n <= 1:\n        return 1\n"
            "    return n * fact(n - 1)\n"
            "print(fact(5))\n",
            ["120"],
        )

    def test_quoted_selfref(self):
        assert_output(
            "from meta import quote\nq = quote('1 + 2')\nprint(q.source)\n",
            ["1 + 2"],
        )


class TestRuntimeErrors:
    """运行时错误 = 诊断码 + 结构化现场（P3 typed 错误契约面）。"""

    def test_division_by_zero(self):
        assert_error("print(1 // 0)\n", "RUN_DIVISION_BY_ZERO", line=1, column=7)

    def test_index_out_of_range(self):
        assert_error("xs = [1]\nprint(xs[5])\n", "RUN_INDEX_ERROR")

    def test_list_index_missing(self):
        assert_error("xs = [1]\nprint(xs.index(9))\n", "RUN_GENERIC_ERROR")

    def test_pop_empty(self):
        assert_error("xs = []\nxs.pop()\n", "RUN_INDEX_ERROR")

    def test_type_error_len(self):
        assert_error("print(len(5))\n", "RUN_TYPE_MISMATCH")

    def test_slice_step_zero(self):
        assert_error("xs = [1, 2, 3]\nprint(xs[::0])\n", "RUN_GENERIC_ERROR")

    def test_assignment_out_of_range(self):
        assert_error("xs = [1]\nxs[5] = 1\n", "RUN_INDEX_ERROR")


class TestCompileErrors:
    """编译错误 = 诊断码（前端契约面）。"""

    def test_undefined_symbol(self):
        assert_compile_error("print(x)\n", "SEM_UNDEFINED_SYMBOL")

    def test_type_mismatch_decl(self):
        assert_compile_error("int x = 'hello'\n", "SEM_TYPE_MISMATCH")


class TestTensor:
    """统一批量数值形态（R5——vector = 1D tensor；tensor = 通用 N-D）。"""

    def test_tensor_1d_surface(self):
        assert_output("t = tensor([1, 2, 3])\nprint(t.shape())\n", ["[3]"])
        assert_output("t = tensor([1, 2, 3])\nprint(t.dtype())\n", ["f64"])
        assert_output("t = tensor([1, 2, 3])\nprint(t.dim())\n", ["3"])
        assert_output("t = tensor([1, 2, 3])\nprint(t[1])\n", ["2.0"])

    def test_tensor_2d_surface(self):
        assert_output(
            "t = tensor([[1, 2], [3, 4]])\nprint(t.shape())\nprint(t.ndim())\n",
            ["[2, 2]", "2"],
        )
        # 2D 下标 = 行（返回 1D tensor）
        assert_output("t = tensor([[1, 2], [3, 4]])\nprint(t[1])\n", ["vector[2](3, 4)"])
        # 2D 显示面
        assert_output("t = tensor([[1, 2], [3, 4]])\nprint(t)\n", ["tensor[2,2](1, 2, 3, 4)"])

    def test_tensor_elementwise(self):
        assert_output(
            "a = tensor([1, 2])\nb = tensor([3, 4])\nprint(a.add(b))\nprint(a.sub(b))\n",
            ["vector[2](4, 6)", "vector[2](-2, -2)"],
        )
        assert_output("a = tensor([1, 2, 3])\nprint(a.scale(2))\n", ["vector[3](2, 4, 6)"])

    def test_tensor_1d_is_vector(self):
        """vector = 1D tensor（统一数据形态——vec() 与 tensor() 1D 同构）。"""
        assert_output("v = vec([1.0, 2.0, 3.0])\nprint(v.dim())\nprint(v.dot(vec([4.0, 5.0, 6.0])))\n", ["3", "32.0"])
        assert_output("t = tensor([1.0, 2.0, 3.0])\nprint(t.dim())\nprint(t.norm())\n", ["3", "3.7416573867739413"])

    def test_tensor_ragged_rejected(self):
        assert_error("t = tensor([[1, 2], [3]])\n", "RUN_GENERIC_ERROR")
