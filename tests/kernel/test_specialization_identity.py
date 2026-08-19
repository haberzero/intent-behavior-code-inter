"""
tests/kernel/test_specialization_identity.py — 特化身份结构化契约。

- specialization_key 单点生成特化注册键（canonical 形态，嵌套保真）；
- axiom is_compatible 结构化（TypeRef.head family 判定，替代特化名前缀匹配）；
- 特化注册键形态与 TypeRef.canonical_name 一致（生成/解析同源）。
"""

from core.kernel.factory import create_default_registry
from core.kernel.spec.type_ref import TypeRef, specialization_key


class TestSpecializationKey:
    def test_simple(self):
        assert specialization_key("Box", ["int"]) == "Box[int]"

    def test_nested_preserved(self):
        assert specialization_key("Box", ["list[int]"]) == "Box[list[int]]"

    def test_multi_args(self):
        assert specialization_key("Pair", ["str", "int"]) == "Pair[str,int]"

    def test_bare(self):
        assert specialization_key("Box", []) == "Box"

    def test_matches_canonical_name(self):
        """注册键形态与 TypeRef.canonical_name 一致（生成同源）。"""
        ref = TypeRef("Box", (TypeRef("list", (TypeRef("int"),)),))
        assert specialization_key("Box", ["list[int]"]) == ref.canonical_name


class TestIsCompatibleStructural:
    """axiom is_compatible 结构化：TypeRef.head family 判定。"""

    def test_list_family_accepts_specialized(self):
        reg = create_default_registry()
        list_spec = reg.resolve("list")
        assert list_spec is not None
        axiom = reg.get_axiom(list_spec)
        assert axiom is not None
        assert axiom.is_compatible(TypeRef.of("list"))
        assert axiom.is_compatible(TypeRef.parse("list[int]"))
        assert not axiom.is_compatible(TypeRef.of("dict"))

    def test_behavior_family_hierarchy(self):
        reg = create_default_registry()
        behavior_spec = reg.resolve("behavior")
        axiom = reg.get_axiom(behavior_spec)
        assert axiom is not None
        for head in ("behavior", "fn_callable", "callable"):
            assert axiom.is_compatible(TypeRef.of(head)), head
        assert not axiom.is_compatible(TypeRef.of("list"))

    def test_numeric_family(self):
        reg = create_default_registry()
        int_spec = reg.resolve("int")
        axiom = reg.get_axiom(int_spec)
        assert axiom is not None
        assert axiom.is_compatible(TypeRef.of("int"))
        assert not axiom.is_compatible(TypeRef.of("str"))

    def test_assignability_uses_structured_family(self):
        """is_assignable 经 axiom is_compatible 的结构化判定路径（回归）。"""
        reg = create_default_registry()
        # bool isa int（axiom 兼容）
        assert reg.is_assignable(reg.resolve("bool"), reg.resolve("int"))
        # list[int] 可赋 list（协变既有语义）
        list_int = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        assert list_int is not None
        assert reg.is_assignable(list_int, reg.resolve("list"))
        # list[int] 不可赋 dict
        assert not reg.is_assignable(list_int, reg.resolve("dict"))

    def test_fn_callable_bare_vs_specialized_consistent(self):
        """fn_callable 裸名与特化名 family 判定一致。"""
        reg = create_default_registry()
        fn_axiom = reg.get_axiom(reg.resolve("fn_callable"))
        assert fn_axiom is not None
        assert fn_axiom.is_compatible(TypeRef.of("fn_callable"))
        assert fn_axiom.is_compatible(TypeRef.parse("fn_callable[int]"))
        assert not fn_axiom.is_compatible(TypeRef.of("list"))

    def test_optional_case_sensitive_family(self):
        """Optional family 判定大小写敏感（与旧前缀匹配语义一致）。"""
        reg = create_default_registry()
        opt_spec = reg.resolve("Optional")
        axiom = reg.get_axiom(opt_spec)
        assert axiom is not None
        assert axiom.is_compatible(TypeRef.parse("Optional[int]"))
        assert not axiom.is_compatible(TypeRef.of("optional"))
