"""
tests/runtime/test_introspection_intrinsics.py
===============================================

运行时内省/常用内置函数测试。

覆盖：
* ``type(x)`` 内建：对值/容器/None/fn_callable/用户类返回规范类型名。
* ``type(f)`` 对 fn_callable/behavior 返回含签名的类型名（如
  ``fn_callable[()->int]`` / ``behavior[(int,str)->bool]``）。
* ``f.__return_type__()`` 返回类型查询 API。
* 签名随序列化 round-trip 保真。
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
        """fn_callable 返回含签名类型名；用户函数（callable）保持裸类名。"""
        lines = run_ibci(
            "fn f = lambda -> auto: 1\n"
            "print(type(f))\n"
            "func g() -> int:\n"
            "    return 1\n"
            "print(type(g))\n"
        )
        assert lines == ["fn_callable[()->int]", "callable"]

    def test_type_of_callable_with_params(self):
        """参数化 fn_callable 的签名形态含参数类型列表。"""
        lines = run_ibci(
            "fn f = lambda(int x, str y) -> bool: True\n"
            "print(type(f))\n"
            "fn g = lambda(auto x) -> int: x\n"
            "print(type(g))\n"
        )
        assert lines == ["fn_callable[(int,str)->bool]", "fn_callable[(auto)->int]"]

    def test_type_of_behavior(self):
        """behavior 的签名形态（LLM 输出类型为返回类型）。"""
        lines = run_ibci(
            'fn b = lambda(auto x) -> str: @~ "hi" ~\n'
            "print(type(b))\n"
        )
        assert lines == ["behavior[(auto)->str]"]

    def test_type_of_snapshot(self):
        """snapshot 捕获模式不影响签名形态。"""
        lines = run_ibci(
            "fn f = snapshot -> auto: 42\n"
            "print(type(f))\n"
        )
        assert lines == ["fn_callable[()->int]"]

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


class TestReturnTypeQuery:
    """``f.__return_type__()`` 返回类型查询 API。"""

    def test_return_type_of_fn_callable(self):
        lines = run_ibci(
            "fn f = lambda -> int: 1\n"
            "fn g = lambda(str s) -> bool: True\n"
            "print(f.__return_type__())\n"
            "print(g.__return_type__())\n"
        )
        assert lines == ["int", "bool"]

    def test_return_type_of_behavior(self):
        lines = run_ibci(
            'fn b = lambda -> str: @~ "hi" ~\n'
            "print(b.__return_type__())\n"
        )
        assert lines == ["str"]

    def test_return_type_infers_auto(self):
        """-> auto 非行为 lambda 编译期锁定为 body 实际类型。"""
        lines = run_ibci(
            "fn f = lambda -> auto: 42\n"
            "print(f.__return_type__())\n"
        )
        assert lines == ["int"]

    def test_return_type_assignable_to_str(self):
        lines = run_ibci(
            "fn f = lambda -> int: 1\n"
            "str rt = f.__return_type__()\n"
            "print(rt)\n"
            "str msg = \"ret: \" + f.__return_type__()\n"
            "print(msg)\n"
        )
        assert lines == ["int", "ret: int"]


class TestCallableSignatureFallback:
    """签名未捕获时的退化行为（手工构造 / 旧数据回退）。"""

    def test_manual_callable_without_signature(self, engine):
        """直接构造的 fn_callable 无签名字段时退化为裸类名。"""
        engine.run_string("int seed = 1\n", silent=True)
        ec = engine.interpreter.execution_context
        fc = ec.factory.create_fn_callable("node1")
        assert fc.signature_name() == "fn_callable"
        assert fc.get_return_type() == "auto"

    def test_serialization_round_trip_preserves_signature(self, engine):
        """签名（param_types + return_type）随序列化 round-trip 保真。"""
        from core.runtime.serialization.runtime_serializer import (
            RuntimeSerializer,
            RuntimeDeserializer,
        )
        engine.run_string(
            "fn f = lambda(int x, str y) -> bool: True\n"
            'fn b = lambda(auto x) -> str: @~ "hi" ~\n',
            silent=True,
        )
        ec = engine.interpreter.execution_context
        ctx = ec.runtime_context
        data = RuntimeSerializer(engine.registry).serialize_context(ctx, include_static=False)
        hits = [v for v in data["pools"]["instances"].values()
                if v.get("_type") in ("fn_callable", "behavior")]
        assert hits, "callable 实例必须序列化"
        assert any(v.get("_type") == "fn_callable" and v.get("param_types") == ["int", "str"]
                   and v.get("return_type") == "bool" for v in hits)
        assert any(v.get("_type") == "behavior" and v.get("return_type") == "str" for v in hits)

        restored = RuntimeDeserializer(engine.registry, factory=ec.factory).deserialize_context(data)
        f = restored.get_variable("f")
        b = restored.get_variable("b")
        assert f.signature_name() == "fn_callable[(int,str)->bool]"
        assert f.get_return_type() == "bool"
        assert b.signature_name() == "behavior[(auto)->str]"
