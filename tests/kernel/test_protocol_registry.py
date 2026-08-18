"""
tests/kernel/test_protocol_registry.py — Protocol kernel model tests.

This test file validates the first protocol-kernel step:
- built-in protocols are registered per SpecRegistry;
- protocol membership is derived from axiom capabilities and class members;
- dynamic types satisfy every protocol (gradual permissiveness).
"""

from core.kernel.factory import create_default_registry
from core.kernel.spec import TypeDef, TypeKind, MethodMemberSpec
from core.kernel.spec.type_ref import TypeRef
from core.kernel.protocol import ProtocolDef


def _make_class(name, methods):
    spec = TypeDef(
        name=name,
        kind=TypeKind.CLASS.value,
        provenance="USER_DEFINED",
    )
    for m in methods:
        spec.members[m] = MethodMemberSpec(
            name=m,
            kind="method",
            return_type=TypeRef.of("str"),
            param_types=[],
        )
    return spec


class TestBuiltinProtocolRegistry:
    def test_builtins_registered(self):
        reg = create_default_registry()
        assert "callable" in reg.protocols
        assert "from_prompt" in reg.protocols
        assert "output_hint" in reg.protocols
        assert "payload_prompt" in reg.protocols
        assert "snapshotable" in reg.protocols
        assert "llm_callable" in reg.protocols

    def test_protocol_names_sorted(self):
        reg = create_default_registry()
        names = reg.protocol_names()
        assert names == tuple(sorted(names))

    def test_duplicate_same_protocol_ok(self):
        reg = create_default_registry()
        p = reg.get_protocol("callable")
        reg.register_protocol(p)
        assert reg.get_protocol("callable") is p

    def test_duplicate_conflicting_protocol_rejected(self):
        reg = create_default_registry()
        try:
            reg.register_protocol(ProtocolDef(name="callable", methods=("__call__", "__x__")))
        except ValueError:
            return
        raise AssertionError("conflicting duplicate protocol should be rejected")


class TestProtocolMembership:
    def test_int_from_prompt(self):
        reg = create_default_registry()
        assert reg.satisfies_protocol(reg.resolve("int"), "from_prompt")
        assert reg.satisfies_protocol(reg.resolve("int"), "output_hint")
        assert reg.satisfies_protocol(reg.resolve("int"), "operator")

    def test_to_prompt_satisfaction_matches_render_capability(self):
        """D2 to_prompt 激活：内置类型（经 axiom 通用渲染能力）与含
        __to_prompt__ 的用户类满足 to_prompt；无 __to_prompt__ 的用户类不满足。
        """
        reg = create_default_registry()
        # 内置经 axiom_cap has_to_prompt_cap（BaseAxiom 通用渲染路径默认 True）
        assert reg.satisfies_protocol(reg.resolve("int"), "to_prompt")
        assert reg.satisfies_protocol(reg.resolve("str"), "to_prompt")
        assert reg.satisfies_protocol(reg.resolve("list"), "to_prompt")
        # 用户类：结构判定
        with_p = _make_class("Point", ["__from_prompt__", "__to_prompt__"])
        reg.register(with_p)
        assert reg.satisfies_protocol(with_p, "to_prompt") is True
        without = _make_class("NoPrompt", ["foo"])
        reg.register(without)
        assert reg.satisfies_protocol(without, "to_prompt") is False

    def test_llm_callable_satisfaction_requires_llm_call(self):
        """LLMCallable（P4a 地基）：__llm_call__ 是必需方法——用户类实现则满足，
        不实现则不满足（satisfies 成为"能否被 LLM 消费"的唯一判定）。"""
        reg = create_default_registry()
        with_llm_call = _make_class("Llama", ["__llm_call__"])
        reg.register(with_llm_call)
        assert reg.satisfies_protocol(with_llm_call, "llm_callable") is True
        without = _make_class("Plain", ["__call__"])
        reg.register(without)
        assert reg.satisfies_protocol(without, "llm_callable") is False

    def test_list_iterable_subscriptable(self):
        reg = create_default_registry()
        list_spec = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        assert reg.satisfies_protocol(list_spec, "iterable")
        assert reg.satisfies_protocol(list_spec, "subscriptable")

    def test_dynamic_satisfies_everything(self):
        reg = create_default_registry()
        for name in reg.protocol_names():
            assert reg.satisfies_protocol(reg.resolve("any"), name)
            assert reg.satisfies_protocol(reg.resolve("auto"), name)

    def test_user_class_from_prompt(self):
        reg = create_default_registry()
        spec = _make_class("Point", ["__from_prompt__", "__to_prompt__"])
        reg.register(spec)
        assert reg.satisfies_protocol(spec, "from_prompt")
        assert reg.satisfies_protocol(spec, "payload_prompt") is False

    def test_user_class_snapshotable_requires_both(self):
        reg = create_default_registry()
        spec = _make_class("Snap", ["__snapshot__"])
        reg.register(spec)
        assert reg.satisfies_protocol(spec, "snapshotable") is False
        spec2 = _make_class("Snap2", ["__snapshot__", "__restore__"])
        reg.register(spec2)
        assert reg.satisfies_protocol(spec2, "snapshotable") is True


class TestCustomProtocolStructuralSatisfaction:
    def test_custom_protocol_satisfied_by_methods(self):
        from core.kernel.protocol import ProtocolDef
        reg = create_default_registry()
        reg.register_protocol(ProtocolDef(name="Serializable", methods=("to_dict",)))
        spec = _make_class("JsonModel", ["to_dict", "from_dict"])
        reg.register(spec)
        assert reg.satisfies_protocol(spec, "Serializable") is True

    def test_custom_protocol_not_satisfied_when_method_missing(self):
        from core.kernel.protocol import ProtocolDef
        reg = create_default_registry()
        reg.register_protocol(ProtocolDef(name="Dumpable", methods=("dump",)))
        spec = _make_class("NoDump", ["load"])
        reg.register(spec)
        assert reg.satisfies_protocol(spec, "Dumpable") is False


class TestProtocolSpecBridge:
    def test_create_protocol_spec_and_register(self):
        from core.kernel.protocol import ProtocolDef
        reg = create_default_registry()
        proto_spec = reg.factory.create_protocol("MyProto")
        proto_spec.members["do_it"] = MethodMemberSpec(
            name="do_it",
            kind="method",
            return_type=TypeRef.of("str"),
            param_types=[],
        )
        reg.register(proto_spec)
        reg.register_protocol(ProtocolDef(name="MyProto", methods=("do_it",)))
        assert reg.satisfies_protocol(reg.resolve("MyProto"), "MyProto") is False
        # A class implementing the method satisfies structurally.
        impl = _make_class("MyImpl", ["do_it"])
        reg.register(impl)
        assert reg.satisfies_protocol(impl, "MyProto") is True


class TestGetProtocolCap:
    def test_get_protocol_cap_for_int_from_prompt(self):
        reg = create_default_registry()
        assert reg.get_protocol_cap(reg.resolve("int"), "from_prompt") is not None
        assert reg.get_protocol_cap(reg.resolve("int"), "to_prompt") is not None

    def test_get_protocol_cap_missing(self):
        reg = create_default_registry()
        assert reg.get_protocol_cap(reg.resolve("int"), "snapshotable") is None
