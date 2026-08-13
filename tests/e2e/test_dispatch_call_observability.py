"""
tests/e2e/test_dispatch_call_observability.py
===============================================

dispatch-before-use 路径下 LLM 调用观测性验证。

dispatch-before-use（赋值 + 并行预调度）把 LLMFuture 写入目标变量、延迟到
变量读取才 resolve。契约：dispatch 时刻即记录调用信息（sys/user prompt +
意图），`idbg.current_llm()` / `ai.get_current_call_info()` 在赋值语句后
立即查询可见（示例 05/06 的 idbg 探查依赖"赋值后立即可观测"）。
"""

from tests.conftest import run_ibci


class TestDispatchCallObservability:
    """dispatch 路径赋值后 LLM 调用信息立即可观测。"""

    def test_current_llm_visible_after_assignment(self):
        out = run_ibci(
            'import idbg\n'
            'str r = @~ MOCK:STR:BLUE ~\n'
            'dict info = idbg.current_llm()\n'
            'print("user_prompt" in info)\n'
            'print("MOCK:STR:BLUE" in (str)info["user_prompt"])\n'
        )
        assert out == ["True", "True"]

    def test_current_call_info_visible_after_typed_assignment(self):
        out = run_ibci(
            'class Color(Enum):\n'
            '    str RED = "RED"\n'
            '    str BLUE = "BLUE"\n'
            'Color c = @~ MOCK:STR:BLUE ~\n'
            'dict info = ai.get_current_call_info()\n'
            'print("sys_prompt" in info)\n'
            'print(len(info["sys_prompt"]) > 0)\n',
            ai=True,
        )
        assert out == ["True", "True"]

    def test_dispatch_info_overwritten_at_resolve(self):
        out = run_ibci(
            'str r = @~ MOCK:STR:BLUE ~\n'
            'str val = r\n'
            'dict info = ai.get_current_call_info()\n'
            'print("response" in info)\n'
            'print(val)\n',
            ai=True,
        )
        assert out == ["True", "BLUE"]
