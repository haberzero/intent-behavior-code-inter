"""tests/contracts/test_intent_dispatch_injection.py
=================================================

Intent 一次性/排他意图在 dispatch-before-use（并行预调度赋值）路径的注入契约。

覆盖真实 LLM e2e 暴露的机制缺陷（原被误判为"模型服从性"）：
- INV-INTENT-DISPATCH-*: ``@`` smear / ``@!`` override 意图在赋值 + 并行预调度
  （``dispatch_eager`` → 意图快照）路径下必须进入发送给 LLM 的 system prompt。
  此前 ``_prepare_behavior_call`` 的 captured_intents 分支只取 active/global，
  fork() 移入快照 ``_inherited_smear``/``_inherited_override`` 的一次性意图被丢弃。
"""

import pytest

from tests.conftest import run_ibci, AI_MOCK_PREFIX


def _intent(content):
    """构造一个纯文本内容的一次性意图（无 node_ 段，resolve_content 直返内容）。"""
    from core.kernel.intent_logic import IntentMode, IntentRole
    from core.runtime.objects.intent import IbIntent

    cls = type("Intent", (), {"name": "Intent"})()
    return IbIntent(
        ib_class=cls, content=content, mode=IntentMode.APPEND, role=IntentRole.SMEAR
    )


class TestIntentContextResolveToPrompts:
    """``IbIntentContext.resolve_to_prompts``（修复后的单一权威消解）。"""

    def test_resolve_merges_active_smear_global(self):
        from core.runtime.objects.intent_context import IbIntentContext

        ctx = IbIntentContext()
        ctx.add_smear(_intent("smear-intent"))
        ctx.push(_intent("active-intent"))
        ctx.set_global_intents([_intent("global-intent")])
        result = ctx.resolve_to_prompts(None, None)
        assert result == ["active-intent", "smear-intent", "global-intent"]

    def test_resolve_override_wins_and_discards_smear(self):
        from core.runtime.objects.intent_context import IbIntentContext

        ctx = IbIntentContext()
        ctx.set_override(_intent("override-intent"))
        ctx.add_smear(_intent("smear-intent"))
        ctx.push(_intent("active-intent"))
        assert ctx.resolve_to_prompts(None, None) == ["override-intent"]

    def test_resolve_includes_inherited_smear_without_consuming(self):
        """fork 快照的 _inherited_smear 参与解析但不被消费（跨调用语义）。"""
        from core.runtime.objects.intent_context import IbIntentContext

        ctx = IbIntentContext(inherited_smear=[_intent("inherited-smear")])
        assert ctx.resolve_to_prompts(None, None) == ["inherited-smear"]
        assert ctx.resolve_to_prompts(None, None) == ["inherited-smear"]


@pytest.fixture()
def captured_sys_prompts(monkeypatch):
    """捕获发送给 LLM provider 的 system prompt（MOCK 模式下 provider 仍收到完整 prompt）。"""
    box = []
    from ibci_modules.ibci_ai.core import AIPlugin

    orig_call = AIPlugin.__call__

    def spy(self, sys_prompt, user_prompt, *, target_model=""):
        box.append(sys_prompt)
        return orig_call(self, sys_prompt, user_prompt, target_model=target_model)

    monkeypatch.setattr(AIPlugin, "__call__", spy)
    return box


class TestIntentDispatchPathInjection:
    """一次性意图在赋值 dispatch-before-use 路径下必须进入 system prompt。"""

    def test_smear_intent_injected_in_dispatch_assignment(self, captured_sys_prompts):
        """``@`` 一次性意图 + 赋值（dispatch 路径）：此前意图被丢弃。"""
        code = AI_MOCK_PREFIX + """
@ 用冷酷无感情且极简的口吻回复
str r = @~ MOCK:STR:hi ~
print(r)
"""
        assert run_ibci(code) == ["hi"]
        assert captured_sys_prompts, "LLM provider 应被调用"
        assert "用冷酷无感情且极简的口吻回复" in captured_sys_prompts[0]

    def test_override_intent_injected_in_dispatch_assignment(self, captured_sys_prompts):
        """``@!`` 排他意图 + 赋值（dispatch 路径）：此前意图被丢弃。"""
        code = AI_MOCK_PREFIX + """
@! 只回复一个词
str r = @~ MOCK:STR:hi ~
print(r)
"""
        assert run_ibci(code) == ["hi"]
        assert captured_sys_prompts
        assert "只回复一个词" in captured_sys_prompts[0]

    def test_smear_and_persistent_both_injected(self, captured_sys_prompts):
        """``@`` 一次性 + ``@+`` 持久意图在 dispatch 路径同时注入。"""
        code = AI_MOCK_PREFIX + """
@+ 保持简洁
@ 用冷酷口吻
str r = @~ MOCK:STR:hi ~
print(r)
@- 保持简洁
"""
        assert run_ibci(code) == ["hi"]
        assert captured_sys_prompts
        assert "保持简洁" in captured_sys_prompts[0]
        assert "用冷酷口吻" in captured_sys_prompts[0]


class TestLLMCallTraceObservability:
    """T3：LLM 调用追踪——无需探针即可查看实际发出的完整 prompt。

    区分"LLM 未服从"（prompt 正确但响应不符）vs"内核未注入"（prompt 缺意图）
    的核心调试设施。
    """

    def test_engine_trace_captures_prompt_intents_and_response(self):
        code = AI_MOCK_PREFIX + """
@ 用冷酷无感情且极简的口吻回复
str r = @~ MOCK:STR:hi ~
print(r)
"""
        from core.engine import IBCIEngine

        engine = IBCIEngine(root_dir=".", auto_sniff=False)
        lines = []
        engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
        trace = engine.get_llm_call_trace()
        assert len(trace) == 1
        assert "用冷酷无感情且极简的口吻回复" in trace[0]["sys_prompt"]
        assert "MOCK:STR:hi" in trace[0]["user_prompt"]
        assert trace[0]["response"] == "hi"
        assert "用冷酷无感情且极简的口吻回复" in trace[0]["merged_intents"]

    def test_engine_trace_preserves_history(self):
        code = AI_MOCK_PREFIX + """
str a = @~ MOCK:STR:one ~
str b = @~ MOCK:STR:two ~
print(a, b)
"""
        from core.engine import IBCIEngine

        engine = IBCIEngine(root_dir=".", auto_sniff=False)
        lines = []
        engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
        trace = engine.get_llm_call_trace()
        assert [t["response"] for t in trace] == ["one", "two"]
        assert [t["user_prompt"].strip() for t in trace] == ["MOCK:STR:one", "MOCK:STR:two"]
