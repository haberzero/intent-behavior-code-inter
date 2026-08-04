"""
tests/kernel/test_generic_model.py
==================================

任务 B（统一泛型模型）：内置泛型类型声明正式机制。

锁定统一泛型模型语义：
- 所有内置泛型类型（list/dict/tuple/Optional/fn_callable/behavior/thread）统一声明
  于 ``GenericTypeRegistry``（单一权威源），经 ``resolve_specialization`` 统一创建。
- ``thread[T]`` 为第一个正式消费者：thread[T] 解析、join 返回类型特化、
  thread[T] 可赋值给 thread。
- 序列化/还原（to_typeref / restore）经同一注册表。
- 历史遗留路径已删除：Optional/List/Dict/Tuple Axiom 不再有
  ``resolve_specialization_by_names``。
"""
import pytest

from core.kernel.factory import create_default_registry
from core.kernel.spec.base import TypeKind
from core.kernel.spec.generic import create_generic_registry


def make_registry():
    return create_default_registry()


class TestGenericTypeRegistry:
    def test_all_builtin_generics_declared(self):
        reg = create_generic_registry()
        for name in ("list", "dict", "tuple", "Optional", "fn_callable", "behavior", "thread"):
            assert name in reg, f"generic '{name}' not declared"

    def test_registry_is_single_authority(self):
        """同一注册表实例同时按名与按 kind 索引同一声明。"""
        reg = create_generic_registry()
        by_name = reg.get("list")
        by_kind = reg.get_by_kind(TypeKind.LIST.value)
        assert by_name is by_kind


class TestUnifiedResolve:
    def test_list_int(self):
        reg = make_registry()
        sp = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        assert sp.name == "list[int]"
        assert sp.kind == TypeKind.LIST.value

    def test_dict_str_int(self):
        reg = make_registry()
        sp = reg.resolve_specialization(reg.resolve("dict"), [reg.resolve("str"), reg.resolve("int")])
        assert sp.name == "dict[str,int]"

    def test_tuple_positional(self):
        reg = make_registry()
        sp = reg.resolve_specialization(reg.resolve("tuple"), [reg.resolve("int"), reg.resolve("str")])
        assert sp.name == "tuple[int,str]"

    def test_optional_int(self):
        reg = make_registry()
        sp = reg.resolve_specialization(reg.resolve("Optional"), [reg.resolve("int")])
        assert sp.name == "Optional[int]"
        assert sp.kind == TypeKind.OPTIONAL.value

    def test_cache_second_call_same_object(self):
        reg = make_registry()
        first = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        second = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        assert first is second


class TestThreadGeneric:
    def test_thread_int_resolves(self):
        reg = make_registry()
        sp = reg.resolve_specialization(reg.resolve("thread"), [reg.resolve("int")])
        assert sp.name == "thread[int]"
        assert sp.kind == TypeKind.THREAD.value
        assert sp.get_base_name() == "thread"
        assert sp.value_type.head == "int"

    def test_thread_join_returns_value_type(self):
        reg = make_registry()
        sp = reg.resolve_specialization(reg.resolve("thread"), [reg.resolve("int")])
        join_spec = reg.resolve_member(sp, "join")
        assert join_spec is not None
        # join() 返回 thread_result[T] 容器（任务 C2），T 为线程返回类型。
        assert join_spec.return_type.head == "thread_result[int]"

    def test_thread_result_unwrap_returns_value_type(self):
        reg = make_registry()
        sp = reg.resolve_specialization(reg.resolve("thread_result"), [reg.resolve("int")])
        unwrap_spec = reg.resolve_member(sp, "unwrap")
        assert unwrap_spec is not None
        assert unwrap_spec.return_type.head == "Optional[int]"
        expect_spec = reg.resolve_member(sp, "expect")
        assert expect_spec is not None
        assert expect_spec.return_type.head == "int"

    def test_thread_void_join(self):
        reg = make_registry()
        sp = reg.resolve_specialization(reg.resolve("thread"), [reg.resolve("void")])
        assert sp.value_type.head == "void"

    def test_thread_assignable_to_bare_thread(self):
        reg = make_registry()
        sp = reg.resolve_specialization(reg.resolve("thread"), [reg.resolve("int")])
        assert reg.is_assignable(sp, reg.resolve("thread"))


class TestToTyperef:
    def test_list(self):
        reg = make_registry()
        sp = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        tr = reg.generic_types.get_by_kind(sp.kind).to_typeref(sp)
        assert tr.canonical_name == "list[int]"

    def test_dict(self):
        reg = make_registry()
        sp = reg.resolve_specialization(reg.resolve("dict"), [reg.resolve("str"), reg.resolve("int")])
        tr = reg.generic_types.get_by_kind(sp.kind).to_typeref(sp)
        assert tr.canonical_name == "dict[str,int]"

    def test_optional(self):
        reg = make_registry()
        sp = reg.resolve_specialization(reg.resolve("Optional"), [reg.resolve("int")])
        tr = reg.generic_types.get_by_kind(sp.kind).to_typeref(sp)
        assert tr.canonical_name == "Optional[int]"

    def test_thread(self):
        reg = make_registry()
        sp = reg.resolve_specialization(reg.resolve("thread"), [reg.resolve("int")])
        tr = reg.generic_types.get_by_kind(sp.kind).to_typeref(sp)
        assert tr.canonical_name == "thread[int]"

    def test_thread_result(self):
        reg = make_registry()
        sp = reg.resolve_specialization(reg.resolve("thread_result"), [reg.resolve("int")])
        tr = reg.generic_types.get_by_kind(sp.kind).to_typeref(sp)
        assert tr.canonical_name == "thread_result[int]"


class TestTypeRefFromSpecThreadKinds:
    """G4（阶段 2 D5）：TypeRef.from_spec 对 thread/thread_result 泛型实参的保留。"""

    def test_thread_int_preserves_arg(self):
        from core.kernel.spec.type_ref import TypeRef
        reg = make_registry()
        sp = reg.resolve_specialization(reg.resolve("thread"), [reg.resolve("int")])
        tr = TypeRef.from_spec(sp)
        assert tr.canonical_name == "thread[int]"
        assert tr.head == "thread"

    def test_thread_result_int_preserves_arg(self):
        from core.kernel.spec.type_ref import TypeRef
        reg = make_registry()
        sp = reg.resolve_specialization(reg.resolve("thread_result"), [reg.resolve("int")])
        tr = TypeRef.from_spec(sp)
        assert tr.canonical_name == "thread_result[int]"
        assert tr.head == "thread_result"


class TestLegacyPathRemoved:
    def test_no_resolve_specialization_by_names_on_axioms(self):
        """历史遗留路径已删除：Optional/List/Dict/Tuple Axiom 不再定义该方法。"""
        from core.kernel.axioms.primitives.sentinels import OptionalAxiom
        from core.kernel.axioms.primitives.sequences import ListAxiom, DictAxiom, TupleAxiom
        for axiom in (OptionalAxiom(), ListAxiom(), DictAxiom(), TupleAxiom()):
            assert not hasattr(axiom, "resolve_specialization_by_names"), (
                f"{axiom.name} 不应再有 resolve_specialization_by_names"
            )