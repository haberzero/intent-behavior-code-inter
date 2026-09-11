"""
tests/runtime/test_generic_value_identity.py — 内置泛型值层类型身份（白盒）。

内置泛型容器特化 spec 水化为运行时特化类，值对象 type_ref 带
实参（type() 内省一致 + 运行时类型安全）。本文件为 runtime/ 白盒层，允许
import 运行时内部（深克隆 / 序列化 / is_assignable 直调）。

黑盒判别（run_ibci）见 tests/e2e/test_generics_runtime.py TestBuiltinGenericValueIdentity。
"""
import os

from core.engine import IBCIEngine

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _engine():
    return IBCIEngine(root_dir=_ROOT)




def test_runtime_assignability_distinguishes_specialized_values():
    """运行时值层可区分 list[int]/list[str]。"""
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


def test_nested_value_type_ref_is_structured():
    """嵌套泛型值 type_ref 结构保真（创建点不扁平化）。

    修复前 `list[list[int]]` 值的 type_ref = TypeRef('list',(TypeRef('list[int]'),))
    （内层扁平 head 含方括号、args 空）；修复后内层实参结构化递归。
    """
    from core.kernel.spec.type_ref import TypeRef

    engine = _engine()
    engine.run_string("list[list[int]] m = [[1],[2]]\n", silent=True)
    rc = engine.interpreter.execution_context.runtime_context
    m = rc.get_symbol("m").value
    assert m.ib_class.name == "list[list[int]]", (
        f"嵌套特化类身份丢失: {m.ib_class.name}"
    )
    assert m.type_ref == TypeRef.parse("list[list[int]]"), (
        f"嵌套值 type_ref 应结构化，got {m.type_ref!r}"
    )
    assert m.elements[0].type_ref == TypeRef.parse("list[int]"), (
        f"内层元素 type_ref 应结构化，got {m.elements[0].type_ref!r}"
    )


def test_three_level_nested_value_identity():
    """三层嵌套 list[list[list[int]]] 全层值身份保真（S1）。"""
    from core.kernel.spec.type_ref import TypeRef

    engine = _engine()
    engine.run_string(
        "list[list[list[int]]] d = [[[1]], [[2]]]\n", silent=True
    )
    rc = engine.interpreter.execution_context.runtime_context
    d = rc.get_symbol("d").value
    assert d.ib_class.name == "list[list[list[int]]]", (
        f"三层特化类身份丢失: {d.ib_class.name}"
    )
    assert d.type_ref == TypeRef.parse("list[list[list[int]]]")
    assert d.elements[0].ib_class.name == "list[list[int]]"
    assert d.elements[0].elements[0].ib_class.name == "list[int]"


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


def test_generator_spec_serialization_preserves_value_type():
    """generator[list[int]] 特化 spec 序列化 round-trip 保真（value_type 持久化）。

    修复前：serializer 缺 GENERATOR 分支，value_type 未持久化，rehydrator 恢复
    为裸 generator（value_type=any）——赋值/迭代类型检查失效。
    """
    from core.compiler.serialization.serializer import FlatSerializer
    from core.runtime.loader.artifact_rehydrator import ArtifactRehydrator
    from core.kernel.factory import create_default_registry

    engine = _engine()
    code = (
        "func gen() -> generator[list[int]]:\n"
        "    yield [1, 2]\n"
    )
    artifact = engine.compile_string(code, silent=True)
    d = FlatSerializer().serialize_artifact(artifact)
    types = d["modules"][artifact.entry_module]["pools"]["types"]
    uid = next((u for u, t in types.items() if t.get("name") == "generator[list[int]]"), None)
    assert uid is not None, "generator[list[int]] 未序列化"
    assert types[uid].get("value_type_name") == "list[int]", (
        "generator value_type 未持久化（serializer 缺分支）"
    )
    reg = create_default_registry()
    reh = ArtifactRehydrator(types, reg)
    spec = reh.hydrate(uid)
    assert spec.name == "generator[list[int]]", f"rehydrate 退化: {spec.name}"
    from core.kernel.spec.type_ref import TypeRef
    assert spec.value_type == TypeRef.parse("list[int]"), (
        f"generator value_type 恢复失败（应结构化保真）: {spec.value_type}"
    )


def test_declaration_driven_rehydrator_roundtrip():
    """声明驱动还原（S4）：序列化→rehydrator 经 GenericTypeDeclaration 重建。

    serializer 经 payload_fields 统一持久化类型实参（消除 per-kind 手工分支），
    rehydrator 经声明 build 结构化还原。跨引擎 round-trip 结构保真。
    """
    from core.compiler.serialization.serializer import FlatSerializer
    from core.runtime.loader.artifact_rehydrator import ArtifactRehydrator
    from core.kernel.factory import create_default_registry
    from core.kernel.spec.type_ref import TypeRef

    engine = _engine()
    code = (
        "func worker() -> int:\n"
        "    return 1\n"
        "list[list[int]] m = [[1],[2]]\n"
        'dict[str,list[int]] dd = {"a":[1]}\n'
        "thread[int] t = thread(callable=worker, args=[])\n"
    )
    artifact = engine.compile_string(code, silent=True)
    d = FlatSerializer().serialize_artifact(artifact)
    types = d["modules"][artifact.entry_module]["pools"]["types"]
    reg = create_default_registry()
    reh = ArtifactRehydrator(types, reg)
    expect = {
        "list[list[int]]": ("element_type", "list[int]"),
        "dict[str,list[int]]": ("value_type", "list[int]"),
        "thread[int]": ("value_type", "int"),
    }
    for name, (field, want) in expect.items():
        uid = next(k for k, v in types.items() if v.get("name") == name)
        spec = reh.hydrate(uid)
        assert spec.name == name, f"{name} 还原退化: {spec.name}"
        assert getattr(spec, field) == TypeRef.parse(want), (
            f"{name}.{field} 应结构化保真，got {getattr(spec, field)!r}"
        )


def test_thread_value_identity_materialized():
    """thread[int] 值经声明类型 rebind 特化类（S3 句柄类物化覆盖）。

    修复前 thread 值 type() 返回裸名 "thread"；修复后返回 "thread[int]"
    （值身份与声明类型一致，运行时区分 thread[int]/thread[str]）。
    """
    engine = _engine()
    engine.run_string(
        "func f() -> int:\n"
        "    return 1\n"
        "thread[int] t = thread(callable=f, args=[])\n",
        silent=True,
    )
    rc = engine.interpreter.execution_context.runtime_context
    t = rc.get_symbol("t").value
    assert t.ib_class.name == "thread[int]", (
        f"thread[int] 值身份未物化: {t.ib_class.name}"
    )


def test_runtime_rejects_handle_type_mismatch():
    """thread[str] 值赋 thread[int] 变量运行时 RUN_TYPE_MISMATCH（S3）。

    句柄类值物化后运行时值层可区分 thread[int]/thread[str]（any 逃生路径）。
    """
    from core.kernel.issue import InterpreterError

    engine = _engine()
    engine.run_string(
        "func f() -> int:\n"
        "    return 1\n"
        "func g() -> str:\n"
        "    return \"s\"\n"
        "thread[int] t = thread(callable=f, args=[])\n"
        "any x = t\n"
        "thread[int] u = x\n",  # 同型，应通过
        silent=True,
    )
    rc = engine.interpreter.execution_context.runtime_context
    assert rc.get_symbol("u").value.ib_class.name == "thread[int]"

    engine2 = _engine()
    try:
        engine2.run_string(
            "func g() -> str:\n"
            "    return \"s\"\n"
            "thread[str] t2 = thread(callable=g, args=[])\n"
            "any y = t2\n"
            "thread[int] v = y\n",
            silent=True,
        )
        raise AssertionError("thread[str] 值赋 thread[int] 未拦截（S3 运行时校验失效）")
    except InterpreterError as e:
        assert "RUN_TYPE_MISMATCH" in str(e), f"应报 RUN_TYPE_MISMATCH, got {e}"
