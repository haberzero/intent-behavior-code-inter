"""
tests/runtime/test_optional_runtime.py
=======================================

Optional 配套运行时：``IbOptional`` 对象 + ``is_some``/``unwrap``/``or_else``
运行时实现。

锁定 Optional 运行时语义：
- ``Optional[T] x = None`` 后 ``x.is_some()`` 为 False，``x.or_else(default)`` 返回默认值
- ``Optional[T] x = <value>`` 后 ``x.is_some()`` 为 True，``x.unwrap()`` 返回内层值
- ``Optional[T] y = x`` 复制（幂等，不重复包装）
- 空 Optional ``unwrap()`` fail-fast 抛错
- 空 Optional 布尔上下文中为 False；持有值按内层值判定
- 类型覆盖（int / str / list[int]）
- Optional 序列化 round-trip
"""
import os

import pytest

from tests.conftest import run_ibci, compile_ibci


class TestOptionalIsSome:
    @pytest.mark.parametrize("code,expected", [
        pytest.param(
            "Optional[int] x = None\n"
            "bool ok = x.is_some()\n"
            "print(ok)\n",
            "False",
            id="none_is_some_false",
        ),
        pytest.param(
            "Optional[int] x = 1\n"
            "bool ok = x.is_some()\n"
            "print(ok)\n",
            "True",
            id="value_is_some_true",
        ),
    ])
    def test_is_some(self, code, expected):
        assert run_ibci(code) == [expected]


class TestOptionalUnwrap:
    @pytest.mark.parametrize("code,expected,should_raise", [
        pytest.param(
            "Optional[int] x = 1\n"
            "int y = x.unwrap()\n"
            "print(y)\n",
            "1",
            False,
            id="unwrap_some_returns_value",
        ),
        pytest.param(
            "Optional[int] x = None\n"
            "int y = x.unwrap()\n"
            "print(y)\n",
            None,
            True,
            id="unwrap_empty_raises",
        ),
    ])
    def test_unwrap(self, code, expected, should_raise):
        if should_raise:
            with pytest.raises(Exception):
                run_ibci(code)
        else:
            assert run_ibci(code) == [expected]


class TestOptionalOrElse:
    @pytest.mark.parametrize("code,expected", [
        pytest.param(
            "Optional[int] x = 1\n"
            "int y = x.or_else(9)\n"
            "print(y)\n",
            "1",
            id="or_else_some_returns_value",
        ),
        pytest.param(
            "Optional[int] x = None\n"
            "int y = x.or_else(9)\n"
            "print(y)\n",
            "9",
            id="or_else_empty_returns_default",
        ),
    ])
    def test_or_else(self, code, expected):
        assert run_ibci(code) == [expected]


class TestOptionalCopy:
    @pytest.mark.parametrize("code,expected", [
        pytest.param(
            "Optional[int] x = 1\n"
            "Optional[int] y = x\n"
            "int z = y.unwrap()\n"
            "print(z)\n",
            "1",
            id="copy_some",
        ),
        pytest.param(
            "Optional[int] x = None\n"
            "Optional[int] y = x\n"
            "bool ok = y.is_some()\n"
            "print(ok)\n",
            "False",
            id="copy_none",
        ),
    ])
    def test_copy(self, code, expected):
        assert run_ibci(code) == [expected]


class TestOptionalReassign:
    @pytest.mark.parametrize("code,expected", [
        pytest.param(
            "Optional[int] x = None\n"
            "x = 5\n"
            "int z = x.unwrap()\n"
            "print(z)\n",
            "5",
            id="reassign_none_to_some",
        ),
        pytest.param(
            "Optional[int] x = 1\n"
            "x = None\n"
            "bool ok = x.is_some()\n"
            "print(ok)\n",
            "False",
            id="reassign_some_to_none",
        ),
    ])
    def test_reassign(self, code, expected):
        assert run_ibci(code) == [expected]


class TestOptionalTypeCoverage:
    @pytest.mark.parametrize("code,expected", [
        pytest.param(
            'Optional[str] x = "hi"\n'
            "str s = x.unwrap()\n"
            "print(s)\n",
            "hi",
            id="str_optional",
        ),
        pytest.param(
            "Optional[list[int]] x = [1, 2, 3]\n"
            "list[int] l = x.unwrap()\n"
            "print(l)\n",
            "[1, 2, 3]",
            id="list_optional",
        ),
        pytest.param(
            "Optional[float] x = 3.5\n"
            "float f = x.unwrap()\n"
            "print(f)\n",
            "3.5",
            id="float_optional",
        ),
    ])
    def test_value_type_coverage(self, code, expected):
        assert run_ibci(code) == [expected]


class TestOptionalTruthiness:
    @pytest.mark.parametrize("code,expected", [
        pytest.param(
            "Optional[int] x = None\n"
            "if x:\n"
            "    print('true')\n"
            "else:\n"
            "    print('false')\n",
            "false",
            id="empty_optional_is_false",
        ),
        pytest.param(
            "Optional[int] x = 1\n"
            "if x:\n"
            "    print('true')\n"
            "else:\n"
            "    print('false')\n",
            "true",
            id="some_optional_value_truthiness",
        ),
    ])
    def test_truthiness(self, code, expected):
        assert run_ibci(code) == [expected]


class TestOptionalSerialization:
    def test_serialize_roundtrip_some(self):
        from core.runtime.serialization.runtime_serializer import (
            RuntimeSerializer,
            RuntimeDeserializer,
        )
        from core.engine import IBCIEngine

        engine = IBCIEngine(root_dir=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), auto_sniff=False)
        engine.run_string("Optional[int] x = 1\n", silent=True)
        ec = engine.interpreter.execution_context
        orig_ctx = ec.runtime_context
        data = RuntimeSerializer(engine.registry).serialize_context(orig_ctx, include_static=False)
        restored = RuntimeDeserializer(engine.registry, factory=ec.factory).deserialize_context(data)
        val = restored.get_variable("x")
        assert val.is_some().to_native() is True
        assert val.unwrap().to_native() == 1

    def test_serialize_roundtrip_none(self):
        from core.runtime.serialization.runtime_serializer import (
            RuntimeSerializer,
            RuntimeDeserializer,
        )
        from core.engine import IBCIEngine

        engine = IBCIEngine(root_dir=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), auto_sniff=False)
        engine.run_string("Optional[int] x = None\n", silent=True)
        ec = engine.interpreter.execution_context
        orig_ctx = ec.runtime_context
        data = RuntimeSerializer(engine.registry).serialize_context(orig_ctx, include_static=False)
        restored = RuntimeDeserializer(engine.registry, factory=ec.factory).deserialize_context(data)
        val = restored.get_variable("x")
        assert val.is_some().to_native() is False
        assert val.or_else(9) == 9


def test_optional_single_carrier():
    """Optional 单承载——内层值存 payload，无 _inner 双载槽。"""
    from core.runtime.objects.primitives.optional import IbOptional
    assert "_inner" not in IbOptional.__slots__

class TestOptionalEmptyErrorCode:
    """空 Optional 操作统一报 RUN_ATTRIBUTE_ERROR（DOC-29 根治）。

    修复前：``unwrap()`` / ``for`` 迭代 / ``next()`` 抛 InterpreterError 未指定
    error_code → 默认 RUN_GENERIC_ERROR，与 receive 委托链空值路径
    （RUN_ATTRIBUTE_ERROR）及文档 arch/03 §8 承诺不一致。
    修复后：三处发射点统一 RUN_ATTRIBUTE_ERROR。
    """

    def test_unwrap_empty_raises_run_attribute_error(self):
        from tests.conftest import expect_runtime_error
        expect_runtime_error(
            "Optional[int] e = None\n"
            "print(e.unwrap())\n",
            "RUN_ATTRIBUTE_ERROR",
        )

    def test_for_iter_empty_raises_run_attribute_error(self):
        from tests.conftest import expect_runtime_error
        expect_runtime_error(
            "Optional[list[int]] e = None\n"
            "for x in e:\n"
            "    print(x)\n",
            "RUN_ATTRIBUTE_ERROR",
        )

    def test_receive_empty_raises_run_attribute_error(self):
        """委托链空值路径（修复前已正确）回归确认。"""
        from tests.conftest import expect_runtime_error
        expect_runtime_error(
            "Optional[list[int]] e = None\n"
            "print(len(e))\n",
            "RUN_ATTRIBUTE_ERROR",
        )

    def test_unwrap_some_still_works(self):
        """非空 unwrap 不受影响（回归）。"""
        assert run_ibci("Optional[int] x = 5\nprint(x.unwrap())\n") == ["5"]
