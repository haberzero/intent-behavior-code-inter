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
