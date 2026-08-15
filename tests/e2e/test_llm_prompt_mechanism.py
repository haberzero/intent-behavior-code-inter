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
        assert "被 IBCI 程序调用的函数" in prompts[0]
        assert "禁止输出问候语" in prompts[0]

    def test_str_behavior_gets_generic_expected_type_declaration(self):
        lines, prompts = _run_with_hooks(
            AI_MOCK_PREFIX
            + "str x = @~ MOCK:STR:hi ~\n"
            + "print(x)\n"
        )
        assert lines == ["hi"]
        assert prompts
        assert "[期望输出类型]" in prompts[0]
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
    def test_llmexcept_retry_feeds_back_previous_response_and_parse_error(self):
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
        assert len(prompts) >= 2, "llmexcept 重试应产生至少两次 LLM 调用"
        retry_prompt = prompts[1]
        assert "[重试反馈]" in retry_prompt
        assert "上一次调用返回的内容" in retry_prompt
        assert "MAYBE_YES_MAYBE_NO_this_is_ambiguous" in retry_prompt
        assert "MOCK:FAIL" in retry_prompt
        assert "请只返回纯文本" in retry_prompt


class TestLLMFunctionPromptMechanism:
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
