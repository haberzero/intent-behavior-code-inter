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


# ---------------------------------------------------------------------------
# 帧级活跃 intent_context IBCI 实例指针
# ---------------------------------------------------------------------------

class TestNS2bActiveIntentIbobj:
    """
    ``RuntimeContextImpl._active_intent_ibobj`` 指针语义。

    核心不变量：
    - 初始状态指针为 None（裸 RuntimeContext，无命名策略）
    - ``use_intent_context(ibobj)`` 后指针指向一个**新封装**，其 ``_ctx`` 与
      帧的 ``_intent_ctx`` 共享引用（同一 IbIntentContext Python 对象）
    - ``clear_inherited_intents()`` 后指针同样指向新封装且共享引用
    - 指针与帧 ``_intent_ctx`` 共享引用：通过指针调用 ``push()`` 等价于 ``@+``
    """

    def test_initial_pointer_is_none(self, ctx):
        """裸 RuntimeContext 初始无命名策略，指针应为 None。"""
        assert ctx.get_active_intent_ibobj() is None

    def test_use_sets_active_pointer_with_shared_ctx(self, ctx, registry):
        """``use_intent_context`` 后，指针的 _ctx 与帧 _intent_ctx 共享引用。"""
        from core.runtime.objects.intent_context import IbIntentContext
        from core.runtime.objects.kernel import IbObject

        intent_context_class = registry.get_class("intent_context")
        src = IbObject(intent_context_class)
        src.fields['_ctx'] = IbIntentContext()
        src.fields['_ctx'].push(make_intent(registry, "src intent", role=IntentRole.STACK))

        assert ctx.use_intent_context(src) is True

        active = ctx.get_active_intent_ibobj()
        assert active is not None
        # 关键：指针的 _ctx 必须与帧的 _intent_ctx 是同一个 Python 对象（共享引用）
        assert active.fields['_ctx'] is ctx._intent_ctx
        # use() 是 fork 拷贝语义：源对象与帧底层不共享
        assert src.fields['_ctx'] is not ctx._intent_ctx
        # 内容已迁移
        active_contents = [i.content for i in ctx._intent_ctx.get_active_intents()]
        assert "src intent" in active_contents

    def test_clear_inherited_resets_with_shared_pointer(self, ctx, registry):
        """``clear_inherited_intents`` 清空持久栈并建立共享引用的新封装。"""
        ctx.push_intent(make_intent(registry, "inherited", role=IntentRole.STACK))
        assert ctx.get_active_intents() != []

        ctx.clear_inherited_intents()
        # 持久栈清空
        assert ctx.get_active_intents() == []
        # 活跃指针重建为共享 _ctx 的新封装
        active = ctx.get_active_intent_ibobj()
        assert active is not None
        assert active.fields['_ctx'] is ctx._intent_ctx

    def test_syntax_and_oop_paths_share_underlying_ctx(self, ctx, registry):
        """关键：``@+`` 修改帧 _intent_ctx 后，通过活跃指针应可观察到该修改。"""
        from core.runtime.objects.intent_context import IbIntentContext
        from core.runtime.objects.kernel import IbObject

        intent_context_class = registry.get_class("intent_context")
        src = IbObject(intent_context_class)
        src.fields['_ctx'] = IbIntentContext()
        ctx.use_intent_context(src)

        # 模拟 @+ 语法路径：直接 push 到帧 _intent_ctx
        ctx.push_intent(make_intent(registry, "syntax intent", role=IntentRole.STACK))

        # OOP 路径：通过活跃指针读取
        active = ctx.get_active_intent_ibobj()
        contents = [i.content for i in active.fields['_ctx'].get_active_intents()]
        assert "syntax intent" in contents

    def test_use_preserves_global_intents(self, ctx, registry):
        """``use_intent_context`` 不应丢失帧上的全局意图。"""
        from core.runtime.objects.intent_context import IbIntentContext
        from core.runtime.objects.kernel import IbObject

        ctx.set_global_intent("engine global")

        intent_context_class = registry.get_class("intent_context")
        src = IbObject(intent_context_class)
        src.fields['_ctx'] = IbIntentContext()
        ctx.use_intent_context(src)

        # 全局意图保留
        globals_after = [i.content for i in ctx.get_global_intents()]
        assert "engine global" in globals_after


# ---------------------------------------------------------------------------
# LLMExceptFrame 意图恢复采用 fork-and-replace 而非 merge
# ---------------------------------------------------------------------------

class TestNS2cLlmExceptIntentRestore:
    """
    ``LLMExceptFrame.restore_context()`` 应以 ``_intent_ctx = saved.fork()``
    直接替换底层 IbIntentContext，而不是 ``merge()`` 叠加（旧行为）。

    关键差异：
    - merge 会保留快照之后产生的 ``_smear_queue`` / ``_override`` 修改
    - fork-and-replace 是干净还原，与变量/loop_context 的恢复语义对齐
    """

    def test_restore_resets_smear_added_after_snapshot(self, ctx, registry):
        """快照后追加的 smear 意图应被 restore 抹除（不再叠加）。"""
        from core.runtime.interpreter.llm_except_frame import LLMExceptFrame

        # 进入快照前：仅有一条持久意图
        ctx.push_intent(make_intent(registry, "base persistent", role=IntentRole.STACK))

        frame = LLMExceptFrame(target_uid="t1", node_type="IbExprStmt")
        frame.save_context(ctx)

        # llmexcept body 模拟：追加 smear 意图（在旧 merge 语义下会泄漏到 restore 之后）
        ctx.add_smear_intent(make_intent(registry, "body smear", role=IntentRole.SMEAR))

        frame.restore_context(ctx)

        # restore 之后：base persistent 应保留，body smear 必须消失
        resolved = ctx.get_resolved_prompt_intents(None)
        assert "base persistent" in resolved
        assert "body smear" not in resolved

    def test_restore_resets_persistent_stack_modifications(self, ctx, registry):
        """body 内 @+/@- 的修改应被 restore 完全还原。"""
        from core.runtime.interpreter.llm_except_frame import LLMExceptFrame

        ctx.push_intent(make_intent(registry, "baseline", role=IntentRole.STACK))

        frame = LLMExceptFrame(target_uid="t2", node_type="IbExprStmt")
        frame.save_context(ctx)

        # body 内 @+
        ctx.push_intent(make_intent(registry, "body extra", role=IntentRole.STACK))
        ctx.push_intent(make_intent(registry, "body extra 2", role=IntentRole.STACK))
        assert len(ctx.get_active_intents()) == 3

        frame.restore_context(ctx)

        # 干净还原到 1 条 baseline
        remaining = [i.content for i in ctx.get_active_intents()]
        assert remaining == ["baseline"]

    def test_restore_rebuilds_active_intent_ibobj_pointer(self, ctx, registry):
        """restore 后活跃实例指针被重建且与新 _intent_ctx 共享引用。"""
        from core.runtime.interpreter.llm_except_frame import LLMExceptFrame
        from core.runtime.objects.intent_context import IbIntentContext
        from core.runtime.objects.kernel import IbObject

        intent_context_class = registry.get_class("intent_context")
        src = IbObject(intent_context_class)
        src.fields['_ctx'] = IbIntentContext()
        ctx.use_intent_context(src)
        active_before = ctx.get_active_intent_ibobj()
        assert active_before is not None

        frame = LLMExceptFrame(target_uid="t3", node_type="IbExprStmt")
        frame.save_context(ctx)

        # body 内切换到另一个策略
        other = IbObject(intent_context_class)
        other.fields['_ctx'] = IbIntentContext()
        other.fields['_ctx'].push(make_intent(registry, "other strategy", role=IntentRole.STACK))
        ctx.use_intent_context(other)

        frame.restore_context(ctx)

        # restore 后：活跃指针指向新封装（不是 active_before，也不是 other 自身）
        active_after = ctx.get_active_intent_ibobj()
        assert active_after is not None
        assert active_after is not active_before  # 新封装实例
        assert active_after is not other
        # 关键不变量：新封装的 _ctx 必须与帧 _intent_ctx 共享引用
        assert active_after.fields['_ctx'] is ctx._intent_ctx
        # "other strategy" 在 restore 后不存在
        contents = [i.content for i in ctx.get_active_intents()]
        assert "other strategy" not in contents
