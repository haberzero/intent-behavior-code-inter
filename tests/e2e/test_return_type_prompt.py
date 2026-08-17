"""
tests/e2e/test_return_type_prompt.py
=========================================

命名 LLM 函数的返回类型提示注入验证。

provider 依据请求输出契约中的期望类型，把自身注册的返回类型提示注入最终
系统提示词；注入结果经 ``ai.get_current_call_info()["sys_prompt"]`` 可观测。
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
