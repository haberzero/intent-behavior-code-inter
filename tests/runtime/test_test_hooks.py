"""tests/runtime/test_test_hooks.py — ServiceContext.test_hooks 测试钩子（LLM 调用观测）。

验证内核 LLM 执行流对测试侧的结构化事件回调：
- on_llm_call：provider 调用成功后触发（含响应）
- on_llm_call_error：provider 失败后触发
- 未注入 hooks 时零回调（生产默认路径）
"""

import pytest

from tests.conftest import AI_MOCK_PREFIX, TESTS_ROOT


class _RecordingHooks:
    """记录所有回调参数的 TestHooks 实现。"""

    def __init__(self):
        self.calls = []
        self.errors = []
        self.dispatches = []

    def on_llm_call(self, *, node_uid, sys_prompt, user_prompt, target_model, response):
        self.calls.append((node_uid, sys_prompt, user_prompt, target_model, response))

    def on_llm_call_error(self, *, node_uid, error):
        self.errors.append((node_uid, error))

    def on_dispatch(self, *, node_uid):
        self.dispatches.append(node_uid)


class TestOnLLMCallHook:
    def test_behavior_expression_fires_on_llm_call(self):
        from core.engine import IBCIEngine

        hooks = _RecordingHooks()
        eng = IBCIEngine(root_dir=TESTS_ROOT)
        eng.test_hooks = hooks
        eng.run_string(
            AI_MOCK_PREFIX + 'str x = @~ MOCK:STR:hello ~\nprint(x)\n',
            silent=True,
        )
        assert len(hooks.calls) == 1
        node_uid, sys_prompt, user_prompt, target_model, response = hooks.calls[0]
        assert response == "hello"
        assert isinstance(node_uid, str) and node_uid
        assert "MOCK:STR:hello" in user_prompt

    def test_llm_function_fires_on_llm_call(self):
        from core.engine import IBCIEngine

        hooks = _RecordingHooks()
        eng = IBCIEngine(root_dir=TESTS_ROOT)
        eng.test_hooks = hooks
        eng.run_string(
            AI_MOCK_PREFIX
            + "llm greet(str name) -> str:\n"
            + "    __sys__\n    Greet the user.\n    __user__\n    MOCK:STR:hello $name\n    llmend\n"
            + 'str r = greet("ibci")\nprint(r)\n',
            silent=True,
        )
        assert len(hooks.calls) == 1
        node_uid, sys_prompt, user_prompt, target_model, response = hooks.calls[0]
        assert response == "hello"
        assert "MOCK:STR:hello" in user_prompt

    def test_no_hooks_means_no_callbacks(self):
        from core.engine import IBCIEngine

        eng = IBCIEngine(root_dir=TESTS_ROOT)
        eng.run_string(AI_MOCK_PREFIX + 'str x = @~ MOCK:STR:hi ~\nprint(x)\n', silent=True)
        assert eng.test_hooks is None
        assert eng.interpreter.service_context.test_hooks is None


class TestOnLLMCallErrorHook:
    def test_provider_failure_fires_on_llm_call_error(self):
        from core.engine import IBCIEngine
        from core.runtime.capability_registry import CapabilityRegistry

        class _FailingProvider:
            def call(self, request):
                raise RuntimeError("provider boom")

            def stream(self, request):
                raise RuntimeError("provider boom")

            def get_current_call_info(self):
                return {}

            def get_retry(self):
                return 3

            def is_auto_intent_injection_enabled(self):
                return True

        hooks = _RecordingHooks()
        eng = IBCIEngine(root_dir=TESTS_ROOT)
        eng.test_hooks = hooks
        eng.capability_registry.register(
            CapabilityRegistry.CAP_LLM_PROVIDER, _FailingProvider(), plugin_id="test"
        )
        with pytest.raises(Exception):
            # print(x) 强制 resolve 惰性 future，使 provider 错误在调用点暴露
            eng.run_string('str x = @~ 随便 ~\nprint(x)\n', silent=True)
        assert len(hooks.errors) == 1
        assert "provider boom" in hooks.errors[0][1]
