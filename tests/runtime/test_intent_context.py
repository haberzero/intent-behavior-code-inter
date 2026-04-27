"""
tests/runtime/test_intent_context.py

Unit tests for intent handling in RuntimeContextImpl.

Coverage:
  - @ (SMEAR) single-line intent is one-shot: consumed after get_resolved_prompt_intents()
  - @ does NOT accumulate in the persistent intent stack
  - @! (OVERRIDE) still works as before: exclusive, one-shot, clears smear queue
  - @+ persists in the stack across get_resolved_prompt_intents() calls
  - lambda captured_intents=None uses call-time context (not empty list)
"""

import os
import pytest
from core.engine import IBCIEngine
from core.runtime.interpreter.runtime_context import RuntimeContextImpl
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole


# ---------------------------------------------------------------------------
# Fixture: minimal KernelRegistry via IBCIEngine
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def registry():
    engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
    return engine.registry


@pytest.fixture
def ctx(registry):
    return RuntimeContextImpl(registry=registry)


def make_intent(registry, content: str, mode: IntentMode = IntentMode.APPEND, role: IntentRole = IntentRole.SMEAR) -> IbIntent:
    return IbIntent(
        ib_class=registry.get_class("Intent"),
        content=content,
        mode=mode,
        role=role,
    )


# ---------------------------------------------------------------------------
# add_smear_intent / get_resolved_prompt_intents
# ---------------------------------------------------------------------------

class TestSmearIntent:
    def test_smear_appears_in_resolved(self, ctx, registry):
        """@ 意图应出现在 get_resolved_prompt_intents() 返回值中。"""
        ctx.add_smear_intent(make_intent(registry, "be concise"))
        resolved = ctx.get_resolved_prompt_intents(None)
        assert "be concise" in resolved

    def test_smear_is_cleared_after_resolution(self, ctx, registry):
        """@ 意图在 get_resolved_prompt_intents() 调用后应自动清除（一次性语义）。"""
        ctx.add_smear_intent(make_intent(registry, "one shot hint"))
        ctx.get_resolved_prompt_intents(None)
        # 第二次调用不再包含该意图
        resolved2 = ctx.get_resolved_prompt_intents(None)
        assert "one shot hint" not in resolved2

    def test_smear_does_not_touch_persistent_stack(self, ctx, registry):
        """@ 意图不应修改持久意图栈（get_active_intents 应不包含 @ 意图）。"""
        ctx.add_smear_intent(make_intent(registry, "transient"))
        # 持久栈应为空
        assert ctx.get_active_intents() == []
        # 消费后依然为空
        ctx.get_resolved_prompt_intents(None)
        assert ctx.get_active_intents() == []

    def test_at_plus_persists_across_resolution(self, ctx, registry):
        """@+ 意图应在多次 get_resolved_prompt_intents() 调用后仍保留在栈中。"""
        ctx.push_intent(make_intent(registry, "persistent hint", role=IntentRole.STACK))
        first = ctx.get_resolved_prompt_intents(None)
        second = ctx.get_resolved_prompt_intents(None)
        assert "persistent hint" in first
        assert "persistent hint" in second
        # 清理
        ctx.pop_intent()

    def test_smear_appended_after_stack(self, ctx, registry):
        """@ 意图应排列在持久栈意图之后（更高优先级，位于 Prompt 末尾）。"""
        ctx.push_intent(make_intent(registry, "stack intent", role=IntentRole.STACK))
        ctx.add_smear_intent(make_intent(registry, "smear intent"))
        resolved = ctx.get_resolved_prompt_intents(None)
        stack_idx = resolved.index("stack intent")
        smear_idx = resolved.index("smear intent")
        assert smear_idx > stack_idx, "smear intent should appear after stack intent"
        ctx.pop_intent()

    def test_multiple_smear_intents_all_consumed(self, ctx, registry):
        """多个 @ 意图（如多次 add_smear_intent）应在一次解析后全部清除。"""
        ctx.add_smear_intent(make_intent(registry, "hint A"))
        ctx.add_smear_intent(make_intent(registry, "hint B"))
        resolved = ctx.get_resolved_prompt_intents(None)
        assert "hint A" in resolved
        assert "hint B" in resolved
        resolved2 = ctx.get_resolved_prompt_intents(None)
        assert "hint A" not in resolved2
        assert "hint B" not in resolved2


# ---------------------------------------------------------------------------
# @! (override) interaction with smear
# ---------------------------------------------------------------------------

class TestOverrideWithSmear:
    def test_override_takes_priority_and_clears_smear(self, ctx, registry):
        """@! 排他意图应优先返回，同时清除待处理的 @ 涂抹意图。"""
        override_intent = make_intent(registry, "override only", mode=IntentMode.OVERRIDE)
        ctx.set_pending_override_intent(override_intent)
        ctx.add_smear_intent(make_intent(registry, "should be discarded"))

        resolved = ctx.get_resolved_prompt_intents(None)
        # @! 排他：只返回 override 内容
        assert resolved == ["override only"]
        # smear 应被清除
        assert ctx._intent_ctx._smear_queue == []

    def test_override_consumed_after_resolution(self, ctx, registry):
        """@! 排他意图在 get_resolved_prompt_intents() 后应被清除。"""
        ctx.set_pending_override_intent(make_intent(registry, "exclusive", mode=IntentMode.OVERRIDE))
        ctx.get_resolved_prompt_intents(None)
        # 第二次不再有 @! 效果
        resolved2 = ctx.get_resolved_prompt_intents(None)
        assert "exclusive" not in resolved2


# ---------------------------------------------------------------------------
# lambda captured_intents=None correctness
# ---------------------------------------------------------------------------

class TestLambdaCapturedIntents:
    def test_none_captured_intents_uses_current_stack(self, ctx, registry):
        """lambda 的 captured_intents=None 应在执行时使用当前 intent 栈。"""
        from core.runtime.interpreter.llm_executor import IntentResolver

        # 模拟：调用时有持久意图
        ctx.push_intent(make_intent(registry, "call-time intent", role=IntentRole.STACK))

        # captured_intents=None → get_resolved_prompt_intents (current stack)
        resolved = ctx.get_resolved_prompt_intents(None)
        assert "call-time intent" in resolved

        ctx.pop_intent()

    def test_empty_list_captured_intents_ignores_stack(self, ctx, registry):
        """[] 意图（旧 lambda bug）应忽略当前栈，只保留全局意图（regression guard）。"""
        from core.kernel.intent_resolver import IntentResolver

        ctx.push_intent(make_intent(registry, "should be ignored", role=IntentRole.STACK))

        # 模拟旧 bug 路径（captured_intents=[]）
        active_list = []  # 空列表
        resolved = IntentResolver.resolve(
            active_intents=active_list,
            global_intents=ctx.get_global_intents(),
            context=ctx,
            execution_context=None,
        )
        # 空 captured_intents 不包含持久栈意图（这是旧 bug 的行为，此测试仅记录差异）
        assert "should be ignored" not in resolved

        ctx.pop_intent()
