"""tests/contracts/test_intent_dispatch_injection.py
=================================================

Intent 一次性/排他意图在 dispatch-before-use（并行预调度赋值）路径的注入契约。

覆盖 dispatch 路径下意图必须进入发送给 LLM 的 system prompt 的行为：
- INV-INTENT-DISPATCH-*: ``@`` smear / ``@!`` override 意图在赋值 + 并行预调度
  （``dispatch_eager`` → 意图快照）路径下必须进入发送给 LLM 的 system prompt，
  含 fork() 移入快照 ``_inherited_smear``/``_inherited_override`` 的一次性意图。
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
    """``IbIntentContext.resolve_to_prompts``（单一权威消解）。"""

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
    """捕获发送给 LLM provider 的 system prompt（MOCK 模式下 provider 仍收到完整 prompt）。

    provider 内部组装最终系统提示词（推荐模板），经 ``LLMCallResult.provider_meta`` 暴露。
    """
    box = []
    from ibci_modules.ibci_ai.core import AIPlugin

    orig_call = AIPlugin.call

    def spy(self, request):
        result = orig_call(self, request)
        box.append((result.provider_meta or {}).get("sys_prompt", ""))
        return result

    monkeypatch.setattr(AIPlugin, "call", spy)
    return box


class TestIntentDispatchPathInjection:
    """一次性意图在赋值 dispatch-before-use 路径下必须进入 system prompt。"""

    def test_smear_intent_injected_in_dispatch_assignment(self, captured_sys_prompts):
        """``@`` 一次性意图 + 赋值（dispatch 路径）：意图须注入 system prompt。"""
        code = AI_MOCK_PREFIX + """
@ 用冷酷无感情且极简的口吻回复
str r = @~ MOCK:STR:hi ~
print(r)
"""
        assert run_ibci(code) == ["hi"]
        assert captured_sys_prompts, "LLM provider 应被调用"
        assert "用冷酷无感情且极简的口吻回复" in captured_sys_prompts[0]

    def test_override_intent_injected_in_dispatch_assignment(self, captured_sys_prompts):
        """``@!`` 排他意图 + 赋值（dispatch 路径）：意图须注入 system prompt。"""
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


class TestRunBatchIntentInjection:
    """``ai.run_batch`` 内每个 LLM 调用都必须看到语句级 ``@!`` 意图。"""

    def test_override_intent_injected_for_every_batch_call(self, captured_sys_prompts):
        code = AI_MOCK_PREFIX + """
fn q = lambda(str word) -> str: @~ MOCK:STR:ok ~
@! 只输出：UNKNOWN
list res = ai.run_batch(q, ["苹果", "香蕉"])
print(res.len())
list res2 = ai.run_batch(q, ["橙子"])
print(res2.len())
"""
        assert run_ibci(code) == ["2", "1"]
        assert len(captured_sys_prompts) == 3, "批内两个调用 + 对照一个调用"
        assert "只输出：UNKNOWN" in captured_sys_prompts[0]
        assert "只输出：UNKNOWN" in captured_sys_prompts[1]
        assert "只输出：UNKNOWN" not in captured_sys_prompts[2]


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

        engine = IBCIEngine(root_dir=".")
        lines = []
        engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
        trace = engine.get_llm_call_trace()
        assert len(trace) == 1
        assert "用冷酷无感情且极简的口吻回复" in trace[0]["sys_prompt"]
        assert "MOCK:STR:hi" in trace[0]["user_prompt"]
        assert trace[0]["response"] == "hi"
        assert "用冷酷无感情且极简的口吻回复" in trace[0]["intents"]["merged"]

    def test_engine_trace_preserves_history(self):
        code = AI_MOCK_PREFIX + """
str a = @~ MOCK:STR:one ~
str b = @~ MOCK:STR:two ~
print(a, b)
"""
        from core.engine import IBCIEngine

        engine = IBCIEngine(root_dir=".")
        lines = []
        engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
        trace = engine.get_llm_call_trace()
        assert [t["response"] for t in trace] == ["one", "two"]
        assert [t["user_prompt"].strip() for t in trace] == ["MOCK:STR:one", "MOCK:STR:two"]
