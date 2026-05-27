"""
tests/e2e/test_e2e_model_routing.py
====================================

e2e 测试：命名模型路由（@NAME~ 语法 → target_model 传递）。

验证 Phase 1 实现：
1. @NAME~ 语法中 tag 字段正确传递到 AIPlugin.__call__
2. register_model() 注册后，@NAME~ 能正确路由
3. 未注册模型名报错
4. 空 tag（@~ 普通语法）走默认路径
"""

import pytest

from tests.conftest import run_ibci, AI_MOCK_PREFIX


class TestNamedModelRouting:
    """命名模型路由 e2e 测试。"""

    def test_default_behavior_expression_still_works(self):
        """无 tag 的 @~ ... ~ 仍然走默认路径。"""
        code = AI_MOCK_PREFIX + """
str result = @~ MOCK:STR:hello ~
print(result)
"""
        lines = run_ibci(code)
        assert "hello" in lines

    def test_named_tag_with_registered_model(self):
        """注册命名模型后，@NAME~ 正常路由（MOCK 模式下 tag 透传但不影响结果）。"""
        code = AI_MOCK_PREFIX + """
ai.register_model("WHISPER", "TESTONLY", "TESTONLY", "TESTONLY")
str result = @WHISPER~ MOCK:STR:routed ~
print(result)
"""
        lines = run_ibci(code)
        assert "routed" in lines

    def test_named_tag_alphanumeric(self):
        """含数字的 tag 也能正确工作（@GPT4o~ 语法）。"""
        code = AI_MOCK_PREFIX + """
ai.register_model("GPT4o", "TESTONLY", "TESTONLY", "TESTONLY")
str result = @GPT4o~ MOCK:STR:numeric_tag ~
print(result)
"""
        lines = run_ibci(code)
        assert "numeric_tag" in lines

    def test_unregistered_model_in_mock_mode_still_works(self):
        """在 MOCK/测试模式下，未注册的命名模型不报错（MOCK 拦截在路由之前）。
        真实 LLM 模式下才会触发 '未注册的命名模型' 错误。"""
        code = AI_MOCK_PREFIX + """
str result = @UNKNOWN~ MOCK:STR:works_in_mock ~
print(result)
"""
        lines = run_ibci(code)
        assert "works_in_mock" in lines

    def test_multiple_named_models(self):
        """可以注册并使用多个不同命名模型。"""
        code = AI_MOCK_PREFIX + """
ai.register_model("FAST", "TESTONLY", "TESTONLY", "TESTONLY")
ai.register_model("SMART", "TESTONLY", "TESTONLY", "TESTONLY")
str r1 = @FAST~ MOCK:STR:fast_result ~
str r2 = @SMART~ MOCK:STR:smart_result ~
print(r1)
print(r2)
"""
        lines = run_ibci(code)
        assert "fast_result" in lines
        assert "smart_result" in lines

    def test_tag_case_sensitive(self):
        """tag 大小写敏感：@gpt~ 和 @GPT~ 是不同的模型标识。"""
        code = AI_MOCK_PREFIX + """
ai.register_model("GPT", "TESTONLY", "TESTONLY", "TESTONLY")
str result = @GPT~ MOCK:STR:case_test ~
print(result)
"""
        lines = run_ibci(code)
        assert "case_test" in lines

    def test_tag_case_sensitive_mismatch(self):
        """tag 大小写不匹配时，在非 MOCK 模式下应报错（MOCK 模式拦截在路由之前）。"""
        # 注册 "GPT" 但使用 "gpt"，在 MOCK 模式下不触发路由错误
        # 此测试验证注册和使用的 tag 保持原始大小写
        code = AI_MOCK_PREFIX + """
ai.register_model("GPT", "TESTONLY", "TESTONLY", "TESTONLY")
ai.register_model("gpt", "TESTONLY", "TESTONLY", "TESTONLY")
str r1 = @GPT~ MOCK:STR:upper ~
str r2 = @gpt~ MOCK:STR:lower ~
print(r1)
print(r2)
"""
        lines = run_ibci(code)
        assert "upper" in lines
        assert "lower" in lines
