"""PT-2.1 regression: intent_context 高级 OOP 场景。

Coverage:
1. `IbIntentContext.combine(other)`: 加法式合并，保留 self 原意图并追加 other 的。
2. `IbIntentContext.to_prompt()`: 渲染为提示词文本（用于 `$ctx` 段插值）。
3. `try_deep_clone` 识别 `IbIntentContext` Python 值并 fork：使 `intent_context`
   作为类字段时，llmexcept 快照/恢复获得正确独立副本。
4. IBCI 端集成：`@~ context: $ctx ~` 中 `$ctx` 通过 `__to_prompt__` 渲染。
"""
import os
import pytest

from core.engine import IBCIEngine
from core.runtime.objects.intent_context import IbIntentContext
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole


@pytest.fixture(scope="module")
def intent_class():
    engine = IBCIEngine(
        root_dir=os.path.dirname(os.path.abspath(__file__)),
        auto_sniff=False,
    )
    return engine.registry.get_class("intent")


def _intent(content, intent_class, mode=IntentMode.APPEND):
    return IbIntent(
        ib_class=intent_class,
        content=content,
        mode=mode,
        role=IntentRole.STACK,
        tag=None,
    )


class TestCombineSemantics:
    def test_combine_appends_other_persistent_stack(self, intent_class):
        a = IbIntentContext()
        a.push(_intent("A1", intent_class))
        a.push(_intent("A2", intent_class))  # bottom→top: [A1, A2]

        b = IbIntentContext()
        b.push(_intent("B1", intent_class))
        b.push(_intent("B2", intent_class))  # bottom→top: [B1, B2]

        a.combine(b)
        # Bottom→top after combine: A stays at bottom, B appended on top.
        active = [i.content for i in a.get_active_intents()]
        assert active == ["A1", "A2", "B1", "B2"]

    def test_combine_smear_queue_appended(self, intent_class):
        a = IbIntentContext()
        a.add_smear(_intent("AS", intent_class))
        b = IbIntentContext()
        b.add_smear(_intent("BS", intent_class))
        a.combine(b)
        assert [i.content for i in a._smear_queue] == ["AS", "BS"]

    def test_combine_override_other_wins_when_set(self, intent_class):
        a = IbIntentContext()
        a.set_override(_intent("A_OV", intent_class))
        b = IbIntentContext()
        b.set_override(_intent("B_OV", intent_class))
        a.combine(b)
        assert a._override.content == "B_OV"

    def test_combine_override_keeps_self_when_other_unset(self, intent_class):
        a = IbIntentContext()
        a.set_override(_intent("A_OV", intent_class))
        b = IbIntentContext()  # no override
        a.combine(b)
        assert a._override.content == "A_OV"

    def test_merge_vs_combine_semantics_differ(self, intent_class):
        """merge = REPLACE; combine = ADDITIVE — explicit regression."""
        a1 = IbIntentContext()
        a1.push(_intent("A", intent_class))
        b = IbIntentContext()
        b.push(_intent("B", intent_class))
        a1.merge(b)
        # After merge: a1 only contains b's intents
        assert [i.content for i in a1.get_active_intents()] == ["B"]

        a2 = IbIntentContext()
        a2.push(_intent("A", intent_class))
        b2 = IbIntentContext()
        b2.push(_intent("B", intent_class))
        a2.combine(b2)
        # After combine: bottom→top = [A, B] (B appended on top).
        assert [i.content for i in a2.get_active_intents()] == ["A", "B"]


class TestToPromptRendering:
    def test_to_prompt_empty(self):
        ctx = IbIntentContext()
        assert ctx.to_prompt() == ""

    def test_to_prompt_lists_active_intents(self, intent_class):
        ctx = IbIntentContext()
        ctx.push(_intent("用中文回复", intent_class))
        ctx.push(_intent("保持简洁", intent_class))
        out = ctx.to_prompt()
        assert "意图上下文" in out
        assert "用中文回复" in out
        assert "保持简洁" in out
        # Stack-bottom should be listed before stack-top.
        assert out.index("用中文回复") < out.index("保持简洁")

    def test_to_prompt_includes_smear_and_override(self, intent_class):
        ctx = IbIntentContext()
        ctx.add_smear(_intent("once", intent_class))
        ctx.set_override(_intent("must", intent_class))
        out = ctx.to_prompt()
        assert "once" in out
        assert "must" in out


class TestDeepCloneIntentContext:
    def test_try_deep_clone_forks_intent_context(self, intent_class):
        from core.runtime.objects.deep_clone import try_deep_clone

        original = IbIntentContext()
        original.push(_intent("orig", intent_class))
        cloned = try_deep_clone(original)
        assert cloned is not None
        assert cloned is not original
        assert isinstance(cloned, IbIntentContext)
        # Independent: mutating clone does NOT affect original.
        cloned.push(_intent("added", intent_class))
        assert [i.content for i in original.get_active_intents()] == ["orig"]
        # bottom→top: [orig, added] in the clone (added pushed on top of orig).
        assert [i.content for i in cloned.get_active_intents()] == [
            "orig", "added",
        ]


class TestIBCIIntegration:
    """End-to-end via IBCI script: `combine`, `__to_prompt__` accessible from IBCI."""

    @pytest.fixture
    def engine(self):
        return IBCIEngine(
            root_dir=os.path.dirname(os.path.abspath(__file__)),
            auto_sniff=False,
        )

    def test_ibci_combine_works(self, engine):
        # ctx_a has "意图A"; combine ctx_b which has "意图B"; combined.resolve()
        # should produce both contents.
        captured = {}

        def out_cb(text):
            captured.setdefault("lines", []).append(text)

        # Use intent_context directly in IBCI.
        engine.run_string(
            'import ai\n'
            'ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'
            'intent_context a = intent_context()\n'
            'a.push("意图A")\n'
            'intent_context b = intent_context()\n'
            'b.push("意图B")\n'
            'a.combine(b)\n'
            'any r = a.resolve()\n'
            'print(r)\n',
            output_callback=out_cb,
            silent=True,
        )
        joined = "\n".join(captured.get("lines", []))
        assert "意图A" in joined
        assert "意图B" in joined

    def test_ibci_to_prompt_via_str_cast(self, engine):
        """``(str)ctx`` should trigger __to_prompt__ rendering."""
        captured = {}

        def out_cb(text):
            captured.setdefault("lines", []).append(text)

        engine.run_string(
            'import ai\n'
            'ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'
            'intent_context c = intent_context()\n'
            'c.push("用中文回复")\n'
            'str s = (str)c\n'
            'print(s)\n',
            output_callback=out_cb,
            silent=True,
        )
        joined = "\n".join(captured.get("lines", []))
        assert "用中文回复" in joined
        assert "意图上下文" in joined


class TestIntentContextAsClassField:
    """PT-2.1(c): intent_context as a persistent class field that participates in
    llmexcept snapshot/restore via auto deep_clone."""

    def test_class_field_isolated_clone(self, intent_class):
        """When a user class has an intent_context field, deep_clone produces an
        independent fork — mutations after clone don't bleed across.
        """
        from core.runtime.objects.deep_clone import try_deep_clone
        from core.runtime.objects.kernel import IbObject, IbClass

        # Build a minimal user IbClass with an intent_context-bearing field.
        engine = IBCIEngine(
            root_dir=os.path.dirname(os.path.abspath(__file__)),
            auto_sniff=False,
        )
        registry = engine.registry
        user_class = IbClass(name="Holder", registry=registry)
        holder = IbObject(user_class)
        ctx = IbIntentContext()
        ctx.push(_intent("policy:strict", intent_class))
        holder.fields["policy"] = ctx

        cloned_holder = try_deep_clone(holder)
        assert cloned_holder is not None
        cloned_ctx = cloned_holder.fields["policy"]
        assert cloned_ctx is not ctx, (
            "intent_context field must be forked, not aliased, when class instance "
            "is deep-cloned for llmexcept snapshot"
        )
        # Mutating clone leaves the original snapshot intact.
        cloned_ctx.push(_intent("retry_extra", intent_class))
        assert [i.content for i in ctx.get_active_intents()] == ["policy:strict"]
        # bottom→top after push: ["policy:strict", "retry_extra"]
        assert [i.content for i in cloned_ctx.get_active_intents()] == [
            "policy:strict", "retry_extra",
        ]
