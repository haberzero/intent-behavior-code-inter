"""
tests/runtime/test_runtime_serialization.py
============================================

Round-trip 测试：``RuntimeSerializer.serialize_context`` →
``RuntimeDeserializer.deserialize_context`` 的值保真性（area 1）。

覆盖所有支持类型的 ``serialize → deserialize == identity`` 属性。

消费者：``HostService``（save/load_state）、``rt_scheduler``（isolation snapshot）。
"""
import pytest

from core.runtime.serialization.runtime_serializer import (
    RuntimeSerializer,
    RuntimeDeserializer,
)


def _native(ctx, name):
    """读取上下文中某变量的原生 Python 值。"""
    v = ctx.get_variable(name)
    return v.to_native() if hasattr(v, "to_native") else v


def _round_trip(engine, code):
    """运行代码，序列化其运行时上下文，反序列化为全新上下文。

    返回 ``(original_ctx, restored_ctx)``。
    """
    engine.run_string(code, silent=True)
    ec = engine.interpreter._execution_context
    orig_ctx = ec.runtime_context
    data = RuntimeSerializer(engine.registry).serialize_context(
        orig_ctx, include_static=False
    )
    restored = RuntimeDeserializer(
        engine.registry, factory=ec.factory
    ).deserialize_context(data)
    return orig_ctx, restored


class TestSerializationRoundTrip:
    """serialize → deserialize 后，变量值应与原始一致。"""

    def test_primitives(self, engine):
        orig, rest = _round_trip(
            engine, 'int a = 42\nfloat b = 3.14\nstr c = "hello"\nbool d = True\n'
        )
        assert _native(rest, "a") == 42
        assert _native(rest, "b") == pytest.approx(3.14)
        assert _native(rest, "c") == "hello"
        assert _native(rest, "d") is True
        for n in ("a", "b", "c", "d"):
            assert _native(rest, n) == _native(orig, n)

    def test_list(self, engine):
        orig, rest = _round_trip(engine, 'list xs = [10, 20, 30]\n')
        assert _native(rest, "xs") == [10, 20, 30]

    def test_tuple(self, engine):
        orig, rest = _round_trip(engine, 'tuple t = (1, 2, 3)\n')
        assert _native(rest, "t") == (1, 2, 3)

    def test_dict(self, engine):
        orig, rest = _round_trip(engine, 'dict d = {"k1": "v1", "k2": 99}\n')
        assert _native(rest, "d") == {"k1": "v1", "k2": 99}

    def test_nested_containers(self, engine):
        orig, rest = _round_trip(
            engine,
            'list nested = [1, [2, 3], [4, [5, 6]]]\ndict dm = {"a": [10, 20], "b": [30]}\n',
        )
        assert _native(rest, "nested") == [1, [2, 3], [4, [5, 6]]]
        assert _native(rest, "dm") == {"a": [10, 20], "b": [30]}

    def test_none_value(self, engine):
        orig, rest = _round_trip(engine, 'auto n = None\n')
        assert _native(rest, "n") is None
        assert _native(orig, "n") is None

    def test_empty_containers(self, engine):
        orig, rest = _round_trip(engine, 'list le = []\ndict de = {}\n')
        assert _native(rest, "le") == []
        assert _native(rest, "de") == {}

    def test_multiple_variables_mixed_types(self, engine):
        """混合类型多变量在单次 round-trip 中全部保持一致。"""
        code = (
            'int i = 7\nstr s = "word"\nlist l = [1, 2]\n'
            'dict dd = {"x": 1}\ntuple tu = (9,)\n'
        )
        orig, rest = _round_trip(engine, code)
        assert _native(rest, "i") == 7
        assert _native(rest, "s") == "word"
        assert _native(rest, "l") == [1, 2]
        assert _native(rest, "dd") == {"x": 1}
        assert _native(rest, "tu") == (9,)


class TestSerializationStructureAndContract:
    """序列化产物的结构契约。"""

    def test_payload_is_versioned(self, engine):
        engine.run_string('int a = 1\n', silent=True)
        ec = engine.interpreter._execution_context
        data = RuntimeSerializer(engine.registry).serialize_context(
            ec.runtime_context, include_static=False
        )
        assert data["version"] == "2.1"
        assert "root_scope_uid" in data
        assert isinstance(data["pools"], dict)

    def test_deserializer_requires_factory(self, engine):
        """无 factory 时反序列化应明确报错（而非静默失败）。"""
        engine.run_string('int a = 1\n', silent=True)
        ec = engine.interpreter._execution_context
        data = RuntimeSerializer(engine.registry).serialize_context(
            ec.runtime_context, include_static=False
        )
        with pytest.raises(RuntimeError, match="ObjectFactory is required"):
            RuntimeDeserializer(engine.registry, factory=None).deserialize_context(data)

    def test_restored_context_is_distinct_object(self, engine):
        """反序列化产生的是独立上下文（深拷贝语义，非同一对象引用）。"""
        orig, rest = _round_trip(engine, 'list xs = [1, 2, 3]\n')
        assert rest is not orig
        # 恢复出的 list 变量是不同的 IbObject 实例
        assert rest.get_variable("xs") is not orig.get_variable("xs")
        assert _native(rest, "xs") == _native(orig, "xs")


class TestThreadResultSerializationRoundTrip:
    """B1 回归：thread_result 序列化往返保真。

    背景（COMMS_DESIGN_REVIEW B1）：``IbThreadResult`` 继承 ``IbObject`` 而非
    ``IbValue``，旧守卫 ``isinstance(obj, IbValue) and cls_name == "thread_result"``
    永不触发 → 序列化为 ``{"_type": "object", "fields": {}}``，value/error/status
    静默丢失，反序列化分支（``_type == "thread_result"``）因此不可达。
    """

    _SUCCESS_CODE = (
        "func c() -> int:\n"
        "    return 1\n"
        "thread[int] t = thread(callable=c, args=[])\n"
        "thread_result[int] r = t.join()\n"
    )

    _FAILED_CODE = (
        'func c() -> int:\n'
        '    raise LLMParseError("boom")\n'
        'thread[int] t = thread(callable=c, args=[])\n'
        'thread_result[int] r = t.join()\n'
    )

    def test_serialized_entry_has_thread_result_type(self, engine):
        """序列化产物必须出现 ``_type == "thread_result"``（旧守卫从未触发的回归）。"""
        engine.run_string(self._SUCCESS_CODE, silent=True)
        ec = engine.interpreter._execution_context
        data = RuntimeSerializer(engine.registry).serialize_context(
            ec.runtime_context, include_static=False
        )
        pool = data["pools"]["instances"]
        hits = [v for v in pool.values() if v.get("_type") == "thread_result"]
        assert hits, "thread_result 必须序列化为 _type='thread_result'（B1 回归）"
        assert hits[0]["status"] == "done"

    def test_round_trip_success_preserves_value_and_status(self, engine):
        orig, rest = _round_trip(engine, self._SUCCESS_CODE)
        assert _native(rest, "r") == 1
        r_rest = rest.get_variable("r")
        assert r_rest.status().to_native() == "done"
        assert r_rest.is_success().to_native() is True
        assert r_rest.is_error().to_native() is False

    def test_round_trip_failed_preserves_status_and_error(self, engine):
        orig, rest = _round_trip(engine, self._FAILED_CODE)
        r_rest = rest.get_variable("r")
        assert r_rest.status().to_native() == "failed"
        assert r_rest.is_error().to_native() is True
        assert r_rest.is_success().to_native() is False
        assert r_rest.value().to_native() is None
        assert r_rest.error() is not None
