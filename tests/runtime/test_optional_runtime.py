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
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conftest import run_ibci, compile_ibci


class TestOptionalIsSome:
    def test_none_is_some_false(self):
        lines = run_ibci(
            "Optional[int] x = None\n"
            "bool ok = x.is_some()\n"
            "print(ok)\n"
        )
        assert lines == ["False"]

    def test_value_is_some_true(self):
        lines = run_ibci(
            "Optional[int] x = 1\n"
            "bool ok = x.is_some()\n"
            "print(ok)\n"
        )
        assert lines == ["True"]


class TestOptionalUnwrap:
    def test_unwrap_some_returns_value(self):
        lines = run_ibci(
            "Optional[int] x = 1\n"
            "int y = x.unwrap()\n"
            "print(y)\n"
        )
        assert lines == ["1"]

    def test_unwrap_empty_raises(self):
        with pytest.raises(Exception):
            run_ibci(
                "Optional[int] x = None\n"
                "int y = x.unwrap()\n"
                "print(y)\n"
            )


class TestOptionalOrElse:
    def test_or_else_some_returns_value(self):
        lines = run_ibci(
            "Optional[int] x = 1\n"
            "int y = x.or_else(9)\n"
            "print(y)\n"
        )
        assert lines == ["1"]

    def test_or_else_empty_returns_default(self):
        lines = run_ibci(
            "Optional[int] x = None\n"
            "int y = x.or_else(9)\n"
            "print(y)\n"
        )
        assert lines == ["9"]


class TestOptionalCopy:
    def test_copy_some(self):
        lines = run_ibci(
            "Optional[int] x = 1\n"
            "Optional[int] y = x\n"
            "int z = y.unwrap()\n"
            "print(z)\n"
        )
        assert lines == ["1"]

    def test_copy_none(self):
        lines = run_ibci(
            "Optional[int] x = None\n"
            "Optional[int] y = x\n"
            "bool ok = y.is_some()\n"
            "print(ok)\n"
        )
        assert lines == ["False"]


class TestOptionalReassign:
    def test_reassign_none_to_some(self):
        lines = run_ibci(
            "Optional[int] x = None\n"
            "x = 5\n"
            "int z = x.unwrap()\n"
            "print(z)\n"
        )
        assert lines == ["5"]

    def test_reassign_some_to_none(self):
        lines = run_ibci(
            "Optional[int] x = 1\n"
            "x = None\n"
            "bool ok = x.is_some()\n"
            "print(ok)\n"
        )
        assert lines == ["False"]


class TestOptionalTypeCoverage:
    def test_str_optional(self):
        lines = run_ibci(
            'Optional[str] x = "hi"\n'
            "str s = x.unwrap()\n"
            "print(s)\n"
        )
        assert lines == ["hi"]

    def test_list_optional(self):
        lines = run_ibci(
            "Optional[list[int]] x = [1, 2, 3]\n"
            "list[int] l = x.unwrap()\n"
            "print(l)\n"
        )
        assert lines == ["[1, 2, 3]"]

    def test_float_optional(self):
        lines = run_ibci(
            "Optional[float] x = 3.5\n"
            "float f = x.unwrap()\n"
            "print(f)\n"
        )
        assert lines == ["3.5"]


class TestOptionalTruthiness:
    def test_empty_optional_is_false(self):
        lines = run_ibci(
            "Optional[int] x = None\n"
            "if x:\n"
            "    print('true')\n"
            "else:\n"
            "    print('false')\n"
        )
        assert lines == ["false"]

    def test_some_optional_value_truthiness(self):
        lines = run_ibci(
            "Optional[int] x = 1\n"
            "if x:\n"
            "    print('true')\n"
            "else:\n"
            "    print('false')\n"
        )
        assert lines == ["true"]


class TestOptionalSerialization:
    def test_serialize_roundtrip_some(self):
        from core.runtime.serialization.runtime_serializer import (
            RuntimeSerializer,
            RuntimeDeserializer,
        )
        from core.engine import IBCIEngine

        engine = IBCIEngine(root_dir=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), auto_sniff=False)
        engine.run_string("Optional[int] x = 1\n", silent=True)
        ec = engine.interpreter._execution_context
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
        ec = engine.interpreter._execution_context
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