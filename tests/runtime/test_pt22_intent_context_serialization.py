"""PT-2.2 regression: IbIntentContext serialization & round-trip.

Coverage:
1. Full ``IbIntentContext`` serialization preserves all 4 slots (persistent
   stack / smear queue / override / global intents).
2. ``intent_context`` IBCI wrapper instance serialization preserves shared
   reference identity with the active context pointer (NS-2b invariant).
3. Round-trip via ``serialize_context`` → ``deserialize_context`` restores
   smear / override semantics that the legacy format lost.
4. Backward-compatible reading of legacy snapshots (only ``intent_stack``).
"""
import os
import pytest

from core.engine import IBCIEngine
from core.runtime.objects.intent_context import IbIntentContext
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole
from core.runtime.serialization.runtime_serializer import (
    RuntimeSerializer, RuntimeDeserializer,
)


@pytest.fixture(scope="module")
def engine():
    e = IBCIEngine(
        root_dir=os.path.dirname(os.path.abspath(__file__)),
        auto_sniff=False,
    )
    # Bootstrap a minimal interpreter (without `ai` module to avoid pre-existing
    # IbModule native-scope serialization gap which is orthogonal to PT-2.2).
    e.run_string('int _bootstrap = 1\n', output_callback=lambda _t: None, silent=True)
    return e


@pytest.fixture(scope="module")
def obj_factory(engine):
    return engine.object_factory


@pytest.fixture(scope="module")
def intent_class(engine):
    return engine.registry.get_class("Intent")


def _intent(content, intent_class, mode=IntentMode.APPEND):
    return IbIntent(
        ib_class=intent_class,
        content=content,
        mode=mode,
        role=IntentRole.STACK,
        tag=None,
    )


class TestIntentContextNativeRoundTrip:
    def test_collect_intent_context_emits_native_entry(self, engine, intent_class):
        ic = IbIntentContext()
        ic.push(_intent("p1", intent_class))
        ic.push(_intent("p2", intent_class))
        ic.add_smear(_intent("s1", intent_class))
        ic.set_override(_intent("ovr", intent_class))

        ser = RuntimeSerializer(engine.registry)
        uid = ser._collect_intent_context(ic)
        assert uid.startswith("intentctx_")
        data = ser.instance_pool[uid]
        assert data["_type"] == "intent_context_native"
        assert data["intent_top_uid"] is not None
        assert len(data["smear_queue"]) == 1
        assert data["override"] is not None

    def test_round_trip_preserves_all_four_slots(self, engine, intent_class, obj_factory):
        ic = IbIntentContext()
        ic.push(_intent("persistent1", intent_class))
        ic.push(_intent("persistent2", intent_class))
        ic.add_smear(_intent("smear1", intent_class))
        ic.set_override(_intent("ovr1", intent_class))

        # Serialize → deserialize.
        ser = RuntimeSerializer(engine.registry)
        uid = ser._collect_intent_context(ic)
        snapshot = {
            "version": "2.1",
            "pools": {
                "instances": ser.instance_pool,
                "intents": ser.intent_pool,
                "runtime_scopes": {},
                "types": ser.type_pool,
                "assets": ser.external_assets,
            },
        }
        deser = RuntimeDeserializer(engine.registry, factory=obj_factory)
        deser.instance_pool = snapshot["pools"]["instances"]
        deser.intent_pool = snapshot["pools"]["intents"]
        deser.runtime_scope_pool = {}
        deser.type_pool = snapshot["pools"]["types"]
        deser.asset_pool = {}
        deser.node_pool = {}
        deser.symbol_pool = {}
        deser.scope_pool = {}

        restored = deser._get_intent_context(uid)
        assert restored is not None
        assert restored is not ic  # Distinct instance.

        # Persistent stack contents preserved (bottom→top order).
        active = [i.content for i in restored.get_active_intents()]
        assert active == ["persistent1", "persistent2"]
        # Smear queue preserved.
        assert [i.content for i in restored._smear_queue] == ["smear1"]
        # Override preserved.
        assert restored._override is not None
        assert restored._override.content == "ovr1"

    def test_shared_identity_preserved(self, engine, intent_class):
        """If the same IbIntentContext is referenced from two places, the
        round-trip must reproduce the shared identity (single Python object).
        """
        ic = IbIntentContext()
        ic.push(_intent("shared", intent_class))

        ser = RuntimeSerializer(engine.registry)
        uid1 = ser._collect_intent_context(ic)
        uid2 = ser._collect_intent_context(ic)  # second call: same uid via memo
        assert uid1 == uid2


class TestSerializeContextWithIntentContext:
    def _build_ctx(self, engine):
        """Build a minimal RuntimeContextImpl bypassing module imports to avoid
        pre-existing issues with native module scope serialization."""
        from core.runtime.interpreter.runtime_context import RuntimeContextImpl
        return RuntimeContextImpl(registry=engine.registry)

    def test_serialize_context_includes_full_intent_ctx(self, engine, intent_class):
        ctx = self._build_ctx(engine)
        ctx._intent_ctx.push(_intent("P", intent_class))
        ctx._intent_ctx.add_smear(_intent("S", intent_class))
        ctx._intent_ctx.set_override(_intent("O", intent_class))

        ser = RuntimeSerializer(engine.registry)
        snapshot = ser.serialize_context(ctx, include_static=False)
        assert "intent_ctx_uid" in snapshot
        assert snapshot["intent_ctx_uid"] is not None
        assert snapshot["intent_ctx_uid"].startswith("intentctx_")
        # Legacy field still present for back-compat.
        assert "intent_stack" in snapshot
        # Native entry exists in the pool.
        native = snapshot["pools"]["instances"].get(snapshot["intent_ctx_uid"])
        assert native is not None
        assert native["_type"] == "intent_context_native"
        assert len(native["smear_queue"]) == 1
        assert native["override"] is not None

    def test_round_trip_restores_smear_and_override(self, engine, intent_class, obj_factory):
        ctx = self._build_ctx(engine)
        ctx._intent_ctx.push(_intent("P", intent_class))
        ctx._intent_ctx.add_smear(_intent("S", intent_class))
        ctx._intent_ctx.set_override(_intent("O", intent_class))

        ser = RuntimeSerializer(engine.registry)
        snapshot = ser.serialize_context(ctx, include_static=False)

        deser = RuntimeDeserializer(engine.registry, factory=obj_factory)
        restored_ctx = deser.deserialize_context(snapshot)

        rsmear = restored_ctx._intent_ctx._smear_queue
        rover = restored_ctx._intent_ctx._override
        ractive = restored_ctx._intent_ctx.get_active_intents()
        assert [i.content for i in rsmear] == ["S"], (
            f"smear queue should be preserved across round-trip; got {[i.content for i in rsmear]}"
        )
        assert rover is not None and rover.content == "O", (
            "override should be preserved across round-trip"
        )
        assert [i.content for i in ractive] == ["P"], (
            "persistent stack should be preserved across round-trip"
        )


class TestIntentContextWrapperSerialization:
    def test_wrapper_instance_round_trip(self, engine, intent_class, obj_factory):
        """``intent_context`` IBCI wrapper round-trips, preserving _ctx identity."""
        # Create an intent_context wrapper via the runtime.
        from core.runtime.objects.kernel import IbObject
        ic_class = engine.registry.get_class("intent_context")
        wrapper = IbObject(ic_class)
        inner = IbIntentContext()
        inner.push(_intent("wrapped", intent_class))
        wrapper.fields["_ctx"] = inner

        ser = RuntimeSerializer(engine.registry)
        uid = ser._collect_instance(wrapper)
        data = ser.instance_pool[uid]
        assert data["_type"] == "intent_context"
        assert data.get("ctx_uid") is not None

        # Deserialize.
        deser = RuntimeDeserializer(engine.registry, factory=obj_factory)
        deser.instance_pool = ser.instance_pool
        deser.intent_pool = ser.intent_pool
        deser.runtime_scope_pool = {}
        deser.type_pool = ser.type_pool
        deser.asset_pool = {}
        deser.node_pool = {}
        deser.symbol_pool = {}
        deser.scope_pool = {}

        restored = deser._get_instance(uid)
        assert restored is not None
        assert restored.ib_class.name == "intent_context"
        restored_ctx = restored.fields.get("_ctx")
        assert restored_ctx is not None
        assert [i.content for i in restored_ctx.get_active_intents()] == ["wrapped"]


class TestBackwardCompatLegacyFormat:
    def test_legacy_intent_stack_only_format(self, engine, intent_class, obj_factory):
        """Old snapshots (only `intent_stack`, no `intent_ctx_uid`) still load."""
        from core.runtime.interpreter.runtime_context import RuntimeContextImpl
        ctx = RuntimeContextImpl(registry=engine.registry)
        ctx._intent_ctx.push(_intent("legacy", intent_class))

        ser = RuntimeSerializer(engine.registry)
        snapshot = ser.serialize_context(ctx, include_static=False)
        # Simulate legacy: strip the new fields.
        snapshot.pop("intent_ctx_uid", None)
        snapshot.pop("active_intent_ibobj_uid", None)
        snapshot["version"] = "2.0"

        deser = RuntimeDeserializer(engine.registry, factory=obj_factory)
        restored_ctx = deser.deserialize_context(snapshot)
        active = restored_ctx._intent_ctx.get_active_intents()
        assert [i.content for i in active] == ["legacy"]
