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
    ec = engine.interpreter.execution_context
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
        ec = engine.interpreter.execution_context
        data = RuntimeSerializer(engine.registry).serialize_context(
            ec.runtime_context, include_static=False
        )
        assert data["version"] == "2.1"
        assert "root_scope_uid" in data
        assert isinstance(data["pools"], dict)

    def test_deserializer_requires_factory(self, engine):
        """无 factory 时反序列化应明确报错（而非静默失败）。"""
        engine.run_string('int a = 1\n', silent=True)
        ec = engine.interpreter.execution_context
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
    """thread_result 序列化往返保真。

    契约：``IbThreadResult``（继承 ``IbObject`` 而非 ``IbValue``）须序列化为
    ``_type="thread_result"`` 判别标记，value/error/status 随值保真，反序列化
    分支（``_type == "thread_result"``）可达并重建。
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
        """thread_result 值序列化时保留类型判别标记与完成状态。

        序列化格式契约：thread_result 实例须带 ``_type="thread_result"`` 判别标记，
        且完成状态（status="done"）随值保真，供反序列化正确重建。
        """
        engine.run_string(self._SUCCESS_CODE, silent=True)
        ec = engine.interpreter.execution_context
        data = RuntimeSerializer(engine.registry).serialize_context(
            ec.runtime_context, include_static=False
        )
        pool = data["pools"]["instances"]
        hits = [v for v in pool.values() if v.get("_type") == "thread_result"]
        assert hits, "thread_result 必须序列化为 _type='thread_result'"
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


class TestTransientObjectSerialization:
    """瞬态对象（thread/chan/slot/subscriber）序列化协议化——统一 transient 存根。

    背景：原 thread 有 thread_transient 专用分支（类名硬编码），chan/slot/subscriber
    无处理 → 空 object 数据丢失。引入 __transient_state__ 协议，统一状态保真存根。
    """

    def test_chan_pubsub_serialized_as_transient(self, engine):
        engine.run_string('chan c = chan(int, "pubsub")\nsubscriber sub = c.subscribe()\n', silent=True)
        ec = engine.interpreter.execution_context
        data = RuntimeSerializer(engine.registry).serialize_context(
            ec.runtime_context, include_static=False
        )
        pool = data["pools"]["instances"]
        chan = next(
            v for v in pool.values()
            if v.get("class_name") == "chan" and v.get("_type") == "transient"
        )
        assert chan["state"]["mode"] == "pubsub"
        assert chan["state"]["subscriber_count"] == 1
        sub = next(
            v for v in pool.values()
            if v.get("class_name") == "subscriber" and v.get("_type") == "transient"
        )
        assert "qsize" in sub["state"]

    def test_slot_serialized_as_transient(self, engine):
        engine.run_string('slot st = slot("score", 42)\n', silent=True)
        ec = engine.interpreter.execution_context
        data = RuntimeSerializer(engine.registry).serialize_context(
            ec.runtime_context, include_static=False
        )
        pool = data["pools"]["instances"]
        slot = next(
            v for v in pool.values()
            if v.get("class_name") == "slot" and v.get("_type") == "transient"
        )
        assert slot["state"]["name"] == "score"
        # value 是嵌套 IbObject，经 _process_value 序列化为实例引用
        assert isinstance(slot["state"]["value"], str)
        assert slot["state"]["value"].startswith("inst_")

    def test_thread_serialized_as_transient(self, engine):
        """thread 由专用 thread_transient 分支迁移至统一 transient 协议（回归）。"""
        engine.run_string("""
func f() -> int:
    return 1
thread[int] t = thread(callable=f, args=[])
""", silent=True)
        ec = engine.interpreter.execution_context
        data = RuntimeSerializer(engine.registry).serialize_context(
            ec.runtime_context, include_static=False
        )
        pool = data["pools"]["instances"]
        thread = next(
            v for v in pool.values()
            if v.get("class_name") == "thread" and v.get("_type") == "transient"
        )
        assert thread["state"]["state"] in ("idle", "running", "done")

    def test_round_trip_preserves_transient_state(self, engine):
        """往返后瞬态对象重建为携带 _transient_state 的占位（状态可内省）。"""
        code = (
            'slot st = slot("score", 42)\n'
            'chan c = chan(int, "pubsub")\n'
            'subscriber sub = c.subscribe()\n'
        )
        orig, rest = _round_trip(engine, code)
        st = rest.get_variable("st")
        assert st.fields["_transient_state"]["name"] == "score"
        value = st.fields["_transient_state"]["value"]
        assert value.to_native() == 42  # 嵌套 IbObject 完整往返
        c = rest.get_variable("c")
        assert c.fields["_transient_state"]["mode"] == "pubsub"
        sub = rest.get_variable("sub")
        assert "qsize" in sub.fields["_transient_state"]


class TestTypeSymbolSerialization:
    """类型符号（IbClass）序列化为类引用，round-trip 后保持类型身份。

    契约：IbClass 须序列化为类引用（非展开为空 fields 的普通实例），反序列化
    经 registry.get_class 重建为对应类，`slot(...)` 等类型构造在恢复后可用。
    """

    def test_serialized_type_symbols_are_class_ref(self, engine):
        engine.run_string('int a = 1\n', silent=True)
        ec = engine.interpreter.execution_context
        data = RuntimeSerializer(engine.registry).serialize_context(
            ec.runtime_context, include_static=False
        )
        pool = data["pools"]["instances"]
        refs = [v for v in pool.values() if v.get("_type") == "class_ref"]
        assert refs, "类型符号必须以 class_ref 序列化（原落 object 空壳）"
        assert any(v.get("name") == "slot" for v in refs)

    def test_round_trip_preserves_type_symbol_identity(self, engine):
        orig, rest = _round_trip(engine, 'int a = 1\n')
        for name in ("int", "str", "thread", "chan", "slot", "subscriber", "Type", "Object"):
            sym = rest.get_symbol(name)
            assert sym is not None, f"类型符号 {name} 缺失"
            assert type(sym.value).__name__ == "IbClass", (
                f"类型符号 {name} 身份破坏：{type(sym.value).__name__}"
            )
        # 恢复后类型可构造（类对象保留 instantiate 能力）
        slot_cls = rest.get_symbol("slot").value
        assert hasattr(slot_cls, "instantiate")


class TestGenericUserClassRoundTrip:
    """用户类泛型（class Box[T]）round-trip 后特化类身份与类型保持。"""

    def test_specialized_class_ref_round_trip(self, engine):
        """Box[int] 特化类对象序列化后保持类身份。"""
        engine.run_string(
            'class Box[T]:\n'
            '    T value\n'
            'Box[int] bi = Box[int](1)\n',
            silent=True,
        )
        ec = engine.interpreter.execution_context
        data = RuntimeSerializer(engine.registry).serialize_context(
            ec.runtime_context, include_static=False
        )
        pool = data["pools"]["instances"]
        refs = [v for v in pool.values() if v.get("_type") == "class_ref"]
        names = {v.get("name") for v in refs}
        assert "Box" in names
        # bi 实例以特化类身份序列化（_type == "object"，承载 ib_class 名）
        bi_entries = [
            v for v in pool.values()
            if v.get("_type") == "object" and v.get("class_name") == "Box[int]"
        ]
        assert bi_entries, f"Box[int] 实例身份丢失；refs={sorted(names)}"

    def test_specialized_instance_value_round_trip(self, engine):
        """Box[int] 实例 round-trip 后字段值保真、方法可达。"""
        orig, rest = _round_trip(
            engine,
            'class Box[T]:\n'
            '    T value\n'
            '    func get(self) -> T:\n'
            '        return self.value\n'
            'Box[int] bi = Box[int](7)\n',
        )
        inst = rest.get_variable("bi")
        assert inst is not None
        assert inst.fields.get("value").to_native() == 7
        getter = inst.receive("get", [])
        result = getter.to_native() if hasattr(getter, "to_native") else getter
        assert result == 7


class TestIntentContextRoundTrip:
    """意图上下文 6 槽位序列化 round-trip（持久栈 / global intents）。"""

    def _active_intents(self, ctx):
        return [i.content for i in ctx.get_active_intents()]

    def test_persistent_stack_round_trip(self, engine):
        """@+ 持久意图栈经序列化 round-trip 后内容保真（展平先入先出）。"""
        orig, rest = _round_trip(
            engine,
            '@+ 意图A\n@+ 意图B\nint seed = 1\n',
        )
        assert self._active_intents(orig) == ["意图A", "意图B"]
        assert self._active_intents(rest) == ["意图A", "意图B"]

    def test_stack_pop_round_trip(self, engine):
        """@+ 后 @- 弹出，round-trip 后栈内容与弹出后一致。"""
        orig, rest = _round_trip(
            engine,
            '@+ 意图A\n@+ 意图B\n@-\nint seed = 1\n',
        )
        assert self._active_intents(orig) == ["意图A"]
        assert self._active_intents(rest) == ["意图A"]

    def test_global_intents_round_trip(self, engine):
        """全局意图经序列化 round-trip 后保真。"""
        engine.run_string('int seed = 1\n', silent=True)
        orig_ctx = engine.interpreter.runtime_context
        orig_ctx.set_global_intent("全局意图")
        data = RuntimeSerializer(engine.registry).serialize_context(
            orig_ctx, include_static=False
        )
        restored = RuntimeDeserializer(
            engine.registry, factory=engine.interpreter.execution_context.factory
        ).deserialize_context(data)
        assert "全局意图" in [i.content for i in restored.get_global_intents()]
