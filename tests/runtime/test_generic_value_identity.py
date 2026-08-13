"""
tests/runtime/test_generic_value_identity.py — 内置泛型值层类型身份（白盒）。

缺陷二根治：内置泛型容器特化 spec 水化为运行时特化类，值对象 type_ref 带
实参（type() 内省一致 + 运行时类型安全）。本文件为 runtime/ 白盒层，允许
import 运行时内部（深克隆 / 序列化 / is_assignable 直调）。

黑盒判别（run_ibci）见 tests/e2e/test_generics_runtime.py TestBuiltinGenericValueIdentity。
"""
import os

from core.engine import IBCIEngine

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _engine():
    return IBCIEngine(root_dir=_ROOT, auto_sniff=False)


def test_deep_clone_preserves_specialized_identity():
    """深克隆特化容器保留类型身份且值独立（快照/字段默认值路径）。"""
    from core.runtime.objects.deep_clone import try_deep_clone

    engine = _engine()
    engine.run_string("list[int] li = [1, 2]\n", silent=True)
    rc = engine.interpreter.execution_context.runtime_context
    li = rc.get_symbol("li").value
    clone = try_deep_clone(li)
    assert clone is not None and clone is not li
    assert clone.ib_class.name == "list[int]", (
        f"深克隆特化身份丢失: {clone.ib_class.name}"
    )
    clone.elements.append(engine.registry.box(99))
    assert [e.to_native() for e in li.elements] == [1, 2], (
        "深克隆后原值被共享修改（应独立）"
    )


def test_deep_clone_dict_specialized_identity():
    """深克隆特化 dict 保留类型身份且值独立。"""
    from core.runtime.objects.deep_clone import try_deep_clone

    engine = _engine()
    engine.run_string('dict[str,int] d = {"a": 1}\n', silent=True)
    rc = engine.interpreter.execution_context.runtime_context
    d = rc.get_symbol("d").value
    clone = try_deep_clone(d)
    assert clone is not None and clone is not d
    assert clone.ib_class.name == "dict[str,int]", (
        f"深克隆特化身份丢失: {clone.ib_class.name}"
    )
    clone.fields["a"] = engine.registry.box(42)
    assert d.fields["a"].to_native() == 1, "深克隆后原 dict 被共享修改（应独立）"


def test_runtime_assignability_distinguishes_specialized_values():
    """运行时值层可区分 list[int]/list[str]（缺陷一+二联动）。"""
    engine = _engine()
    engine.run_string('list[int] li = [1]\nlist[str] ls = ["a"]\n', silent=True)
    rc = engine.interpreter.execution_context.runtime_context
    spec_reg = engine.registry.get_metadata_registry()
    int_list_spec = spec_reg.resolve("list[int]")
    assert spec_reg.is_assignable(
        rc.get_symbol("li").value.ib_class.spec, int_list_spec
    )
    assert not spec_reg.is_assignable(
        rc.get_symbol("ls").value.ib_class.spec, int_list_spec
    ), "list[str] 值应不可赋给 list[int]（运行时类型安全）"


def test_serialization_roundtrip_specialized_identity():
    """list[int] 值序列化 round-trip 特化保真（同引擎）。"""
    from core.runtime.serialization.runtime_serializer import (
        RuntimeSerializer,
        RuntimeDeserializer,
    )

    engine = _engine()
    engine.run_string("list[int] li = [1, 2]\n", silent=True)
    ec = engine.interpreter.execution_context
    orig_ctx = ec.runtime_context
    data = RuntimeSerializer(engine.registry).serialize_context(
        orig_ctx, include_static=False
    )
    restored = RuntimeDeserializer(engine.registry, factory=ec.factory).deserialize_context(data)
    val = restored.get_variable("li")
    assert val.ib_class.name == "list[int]", (
        f"round-trip 特化身份丢失: {val.ib_class.name}"
    )


def test_cross_engine_deserialization_preserves_identity():
    """跨引擎反序列化特化身份保真（边界 7）。

    目标引擎未编译该特化（spec_reg 无 list[int]），从序列化 type_pool 重建
    spec 再水化特化类——与用户类泛型跨引擎 round-trip 机制同构。
    """
    from core.runtime.serialization.runtime_serializer import (
        RuntimeSerializer,
        RuntimeDeserializer,
    )

    engine_a = _engine()
    engine_a.run_string("list[int] li = [1, 2]\n", silent=True)
    ec = engine_a.interpreter.execution_context
    orig_ctx = ec.runtime_context
    data = RuntimeSerializer(engine_a.registry).serialize_context(
        orig_ctx, include_static=True, execution_context=ec
    )

    engine_b = _engine()  # 未编译 list[int]
    deser = RuntimeDeserializer(engine_b.registry, factory=engine_b.object_factory)
    restored = deser.deserialize_context(data)
    val = restored.get_variable("li")
    assert val.ib_class.name == "list[int]", (
        f"跨引擎 round-trip 特化身份丢失: {val.ib_class.name}"
    )
    assert [e.to_native() for e in val.elements] == [1, 2]
