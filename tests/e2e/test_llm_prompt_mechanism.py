"""tests/e2e/test_llm_prompt_mechanism.py

IBCI LLM 调用机制整改（P0）判别性回归：

- 枚举 ``__outputhint_prompt__`` 必须注入 behavior 与命名 LLM 函数的 system prompt
  （S2/S5 module 化后注入端 module 感知修复）。
- behavior 基础 system prompt 必须建立程序化调用纪律。
- 期望输出类型必须注入 behavior system prompt（无类型级 hint 时兜底声明）。
- llmexcept/retry 必须自动回喂上一次原始响应与解析错误。
"""

from core.engine import IBCIEngine

from tests.conftest import AI_MOCK_PREFIX, TESTS_ROOT


class _RecordingHooks:
    """记录 on_llm_call 的 system prompt（MOCK provider 仍收到完整 prompt）。"""

    def __init__(self):
        self.sys_prompts = []

    def on_llm_call(self, *, node_uid, sys_prompt, user_prompt, target_model, response):
        self.sys_prompts.append(sys_prompt)

    def on_llm_call_error(self, *, node_uid, error):
        pass

    def on_dispatch(self, *, node_uid):
        pass


def _run_with_hooks(code):
    """执行代码并返回 (输出行, 捕获的 sys_prompt 列表)。"""
    engine = IBCIEngine(root_dir=TESTS_ROOT, auto_sniff=False)
    hooks = _RecordingHooks()
    engine.test_hooks = hooks
    lines = []
    engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
    return lines, hooks.sys_prompts


class TestBehaviorPromptMechanism:
    def test_base_sys_prompt_establishes_programmatic_discipline(self):
        lines, prompts = _run_with_hooks(
            AI_MOCK_PREFIX
            + "str x = @~ MOCK:STR:hi ~\n"
            + "print(x)\n"
        )
        assert lines == ["hi"]
        assert prompts, "LLM provider 应被调用"
        assert "只输出任务要求的结果数据本身" in prompts[0]
        assert "禁止输出任何解释" in prompts[0]
        assert "IBCI" not in prompts[0]

    def test_str_behavior_gets_generic_expected_type_declaration(self):
        lines, prompts = _run_with_hooks(
            AI_MOCK_PREFIX
            + "str x = @~ MOCK:STR:hi ~\n"
            + "print(x)\n"
        )
        assert lines == ["hi"]
        assert prompts
        assert "必须返回一个 str 值" in prompts[0]

    def test_enum_outputhint_injected_for_behavior(self):
        code = AI_MOCK_PREFIX + """
class Status(Enum):
    str ACTIVE = "ACTIVE"
    str INACTIVE = "INACTIVE"
Status c = @~ MOCK:STR:ACTIVE ~
print(c)
"""
        lines, prompts = _run_with_hooks(code)
        assert lines == ["ACTIVE"]
        assert prompts
        assert "[输出格式要求]" in prompts[0]
        assert "ACTIVE, INACTIVE" in prompts[0]

    def test_provider_return_type_prompt_overrides_axiom_hint_for_behavior(self):
        code = (
            AI_MOCK_PREFIX
            + 'ai.set_return_type_prompt("int", "CUSTOM_INT_PROMPT")\n'
            + "int x = @~ MOCK:INT:3 ~\n"
            + "print(x)\n"
        )
        lines, prompts = _run_with_hooks(code)
        assert lines == ["3"]
        assert prompts
        assert "CUSTOM_INT_PROMPT" in prompts[0]
        assert "请仅返回一个整数作为回答" not in prompts[0]


class TestRetryFeedbackMechanism:
    def test_llmexcept_retry_uses_standard_multiturn_messages(self, monkeypatch):
        from ibci_modules.ibci_ai.core import AIPlugin

        captured = []
        orig_call = AIPlugin.call

        def spy(self, request):
            # 捕获 request（含 message_history），并复算组装后的 sys_prompt 供断言
            sys_prompt = self._assemble_provider_sys_prompt(request, is_reasoning_model=False)
            captured.append((sys_prompt, request.message_history))
            return orig_call(self, request)

        monkeypatch.setattr(AIPlugin, "call", spy)

        code = AI_MOCK_PREFIX + """
try:
    str x = @~ MOCK:FAIL boom ~
    llmexcept:
        retry "请只返回纯文本"
except Exception as e:
    print("caught")
"""
        lines, prompts = _run_with_hooks(code)
        assert "caught" in lines
        assert len(captured) >= 2, "llmexcept 重试应产生至少两次 LLM 调用"

        first_sys_prompt, first_history = captured[0]
        assert first_history is None

        retry_sys_prompt, retry_history = captured[1]
        assert retry_history, "重试应携带标准多轮对话历史"
        assert [m["role"] for m in retry_history] == ["assistant", "user"]
        assert "MAYBE_YES_MAYBE_NO_this_is_ambiguous" in retry_history[0]["content"]
        assert "MOCK:FAIL" in retry_history[1]["content"]
        assert "请只返回纯文本" in retry_history[1]["content"]


class TestLLMFunctionPromptMechanism:
    def test_llm_function_llmretry_not_injected_on_first_call(self):
        code = AI_MOCK_PREFIX + """
llm f() -> int:
__sys__
你是数字解析器。
__user__
MOCK:INT:3
__llmretry__
请只返回整数
llmend
int x = f()
print(x)
"""
        lines, prompts = _run_with_hooks(code)
        assert lines == ["3"]
        assert prompts
        assert "[重试提示]" not in prompts[0]
        assert "请只返回整数" not in prompts[0]

    def test_llm_function_returning_enum_gets_outputhint(self):
        code = AI_MOCK_PREFIX + """
class Status(Enum):
    str ACTIVE = "ACTIVE"
    str INACTIVE = "INACTIVE"
llm parse_status() -> Status:
__sys__
你是状态解析器。
__user__
MOCK:STR:ACTIVE
llmend
Status s = parse_status()
print(s)
"""
        lines, prompts = _run_with_hooks(code)
        assert lines == ["ACTIVE"]
        assert prompts
        assert "[输出格式要求]" in prompts[0]
        assert "ACTIVE, INACTIVE" in prompts[0]
