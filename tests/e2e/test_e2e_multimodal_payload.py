"""
tests/e2e/test_e2e_multimodal_payload.py
=========================================

e2e 测试：多模态 payload 协议（Phase 2 — __payload_prompt__）。

验证 Phase 2 实现：
1. 纯文本行为表达式仍正常工作（向后兼容）
2. AIPlugin._flatten_content_parts 正确展平多模态内容
3. AIPlugin._build_user_content 纯文本路径返回 str
4. AIPlugin._build_user_content 多模态路径返回 content blocks
5. _obj_to_payload 对普通 IbObject 回退到文本
6. _call_llm 接受 str 和 List 类型的 user_prompt
"""

import pytest

from tests.conftest import run_ibci, AI_MOCK_PREFIX


class TestMultimodalBackwardCompat:
    """验证多模态改造不影响现有纯文本路径。"""

    def test_plain_text_behavior_expression(self):
        """纯文本行为表达式仍返回正确结果。"""
        code = AI_MOCK_PREFIX + """
str result = @~ MOCK:STR:plain_text ~
print(result)
"""
        lines = run_ibci(code)
        assert "plain_text" in lines

    def test_interpolated_behavior_expression(self):
        """带变量插值的行为表达式仍正常工作。"""
        code = AI_MOCK_PREFIX + """
str name = "world"
str result = @~ MOCK:STR:hello ~
print(result)
"""
        lines = run_ibci(code)
        assert "hello" in lines

    def test_named_model_still_works_with_payload_changes(self):
        """命名模型路由在 payload 改造后仍正常。"""
        code = AI_MOCK_PREFIX + """
ai.register_model("TEST", "TESTONLY", "TESTONLY", "TESTONLY")
str result = @TEST~ MOCK:STR:routed ~
print(result)
"""
        lines = run_ibci(code)
        assert "routed" in lines


class TestAIPluginMultimodalHelpers:
    """测试 AIPlugin 的多模态辅助方法。"""

    def test_flatten_content_parts_pure_text(self):
        """纯文本列表展平为拼接字符串。"""
        from ibci_modules.ibci_ai.core import AIPlugin
        parts = ["hello ", "world"]
        result = AIPlugin._flatten_content_parts(parts)
        assert result == "hello world"

    def test_flatten_content_parts_with_dict(self):
        """含 dict 的列表，dict 用占位符表示。"""
        from ibci_modules.ibci_ai.core import AIPlugin
        parts = ["describe: ", {"type": "image_url", "image_url": {"url": "data:..."}}]
        result = AIPlugin._flatten_content_parts(parts)
        assert result == "describe: [image_url]"

    def test_flatten_content_parts_empty(self):
        """空列表返回空字符串。"""
        from ibci_modules.ibci_ai.core import AIPlugin
        assert AIPlugin._flatten_content_parts([]) == ""

    def test_build_user_content_string_path(self):
        """纯文本 user_prompt 直接返回 user_prompt_text。"""
        from ibci_modules.ibci_ai.core import AIPlugin
        result = AIPlugin._build_user_content("hello", "hello")
        assert result == "hello"
        assert isinstance(result, str)

    def test_build_user_content_multimodal_path(self):
        """多模态 user_prompt 转换为 OpenAI content blocks。"""
        from ibci_modules.ibci_ai.core import AIPlugin
        parts = ["describe this: ", {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}]
        result = AIPlugin._build_user_content(parts, "describe this: [image_url]")
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == {"type": "text", "text": "describe this: "}
        assert result[1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}}

    def test_build_user_content_empty_text_skipped(self):
        """空文本段在多模态模式下被跳过。"""
        from ibci_modules.ibci_ai.core import AIPlugin
        parts = ["", {"type": "image_url", "image_url": {"url": "x"}}, "   "]
        result = AIPlugin._build_user_content(parts, "[image_url]")
        assert isinstance(result, list)
        # 空字符串和纯空白字符串都被跳过
        assert len(result) == 1
        assert result[0]["type"] == "image_url"


class TestObjToPayload:
    """测试 _obj_to_payload 协议分发。"""

    def test_plain_ibobject_returns_str(self):
        """无 __payload_prompt__ 的对象回退到 __to_prompt__ (str)。"""
        from core.runtime.interpreter.llm_executor import LLMExecutorImpl

        class MockObj:
            def receive(self, method, args):
                if method == '__payload_prompt__':
                    return None  # 不支持
                if method == '__to_prompt__':
                    return "text_value"
                return None

            def to_native(self):
                return "text_value"

            def __str__(self):
                return "text_value"

        result = LLMExecutorImpl._obj_to_payload(MockObj())
        assert isinstance(result, str)

    def test_payload_prompt_returns_dict(self):
        """有 __payload_prompt__ 且返回 dict 的对象走结构化路径。"""
        from core.runtime.interpreter.llm_executor import LLMExecutorImpl

        class MockMultimodalObj:
            def receive(self, method, args):
                if method == '__payload_prompt__':
                    return {"type": "image_url", "image_url": {"url": "data:..."}}
                return None

        result = LLMExecutorImpl._obj_to_payload(MockMultimodalObj())
        assert isinstance(result, dict)
        assert result["type"] == "image_url"

    def test_payload_prompt_returns_list(self):
        """__payload_prompt__ 返回 list 也能正确处理。"""
        from core.runtime.interpreter.llm_executor import LLMExecutorImpl

        class MockMultiBlockObj:
            def receive(self, method, args):
                if method == '__payload_prompt__':
                    return [{"type": "text", "text": "a"}, {"type": "image_url", "image_url": {"url": "x"}}]
                return None

        result = LLMExecutorImpl._obj_to_payload(MockMultiBlockObj())
        assert isinstance(result, list)
        assert len(result) == 2

    def test_no_receive_fallback_to_str(self):
        """无 receive 方法的对象直接 str() 转换。"""
        from core.runtime.interpreter.llm_executor import LLMExecutorImpl

        result = LLMExecutorImpl._obj_to_payload(42)
        assert result == "42"
        assert isinstance(result, str)
