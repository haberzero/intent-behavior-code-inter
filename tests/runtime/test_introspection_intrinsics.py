"""
tests/runtime/test_introspection_intrinsics.py
===============================================

运行时内省/常用内置函数测试（PT-INTRO-1）。

覆盖：
* ``type(x)`` 内建：对值/容器/None/fn_callable/用户类返回规范类型名。
* ``type`` 的编译期签名（``str type(any)``）与运行时行为一致。
"""
from tests.conftest import run_ibci


class TestTypeIntrinsic:
    """``type(x)`` 运行时内省。"""

    def test_type_of_primitives(self):
        lines = run_ibci(
            "print(type(42))\n"
            "print(type(3.14))\n"
            "print(type(\"hi\"))\n"
            "print(type(True))\n"
        )
        assert lines == ["int", "float", "str", "bool"]

    def test_type_of_containers(self):
        lines = run_ibci(
            "print(type([1, 2]))\n"
            "print(type({\"k\": 1}))\n"
            "print(type((1, 2)))\n"
        )
        assert lines == ["list", "dict", "tuple"]

    def test_type_of_none(self):
        lines = run_ibci("auto n = None\nprint(type(n))\n")
        assert lines == ["None"]

    def test_type_of_callable(self):
        lines = run_ibci(
            "fn f = lambda -> auto: 1\n"
            "print(type(f))\n"
            "func g() -> int:\n"
            "    return 1\n"
            "print(type(g))\n"
        )
        assert lines == ["fn_callable", "callable"]

    def test_type_of_user_class(self):
        lines = run_ibci(
            "class Box:\n"
            "    int v\n"
            "Box b = Box(1)\n"
            "print(type(b))\n"
        )
        assert lines == ["Box"]

    def test_type_assignable_to_str(self):
        """type() 返回 str，可赋给 str 变量并参与字符串拼接。"""
        lines = run_ibci(
            "str t = type(42)\n"
            "print(t)\n"
            "str msg = \"value is \" + type(3.14)\n"
            "print(msg)\n"
        )
        assert lines == ["int", "value is float"]
