"""
tests/e2e/test_return_type_prompt.py
=========================================

命名 LLM 函数的返回类型提示注入验证。

LLM 函数执行前，执行器经 ``ILLMProvider.get_return_type_prompt``（协议声明
能力，直接调用）读取该类型的提示词并注入系统提示词；注入结果经
``ai.get_current_call_info()["sys_prompt"]`` 可观测。
"""

from tests.conftest import run_ibci


class TestReturnTypePromptInjection:
    """返回类型提示注入命名 LLM 函数系统提示词。"""

    def test_registered_constraint_injected_into_sys_prompt(self):
        out = run_ibci(
            'ai.set_return_type_prompt("str", "STR_CONSTRAINT_PROMPT")\n'
            'llm f() -> str:\n'
            '__user__\n'
            'say hi\n'
            'llmend\n'
            'str x = f()\n'
            'dict info = ai.get_current_call_info()\n'
            'print("sys_prompt" in info)\n'
            'print("STR_CONSTRAINT_PROMPT" in (str)info["sys_prompt"])\n',
            ai=True,
        )
        assert out == ["True", "True"]

    def test_unregistered_type_skips_injection(self):
        out = run_ibci(
            'ai.set_return_type_prompt("int", "INT_CONSTRAINT_PROMPT")\n'
            'llm f() -> str:\n'
            '__user__\n'
            'say hi\n'
            'llmend\n'
            'str x = f()\n'
            'dict info = ai.get_current_call_info()\n'
            'print("INT_CONSTRAINT_PROMPT" in (str)info["sys_prompt"])\n',
            ai=True,
        )
        assert out == ["False"]
