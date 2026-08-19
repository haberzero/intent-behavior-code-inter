"""
tests/e2e/test_return_type_prompt.py
=========================================

llm 可调用类的返回类型提示注入验证（命名 LLM 函数 → llm 可调用类）。

provider 依据请求输出契约中的期望类型（``expected_type``），把自身注册的返回
类型提示注入最终系统提示词；注入结果经 ``ai.get_current_call_info()["sys_prompt"]``
可观测。
"""

from tests.conftest import run_ibci


class TestReturnTypePromptInjection:
    """返回类型提示注入 llm 可调用类系统提示词。"""

    def test_registered_constraint_injected_into_sys_prompt(self):
        out = run_ibci(
            'ai.set_return_type_prompt("str", "STR_CONSTRAINT_PROMPT")\n'
            'class F:\n'
            '    func __llm_call__(self) -> dict:\n'
            '        return {"user_prompt": "say hi", "expected_type": "str"}\n'
            'F f = F()\n'
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
            'class F:\n'
            '    func __llm_call__(self) -> dict:\n'
            '        return {"user_prompt": "say hi", "expected_type": "str"}\n'
            'F f = F()\n'
            'str x = f()\n'
            'dict info = ai.get_current_call_info()\n'
            'print("INT_CONSTRAINT_PROMPT" in (str)info["sys_prompt"])\n',
            ai=True,
        )
        assert out == ["False"]
