"""
tests/runtime/test_prompt_renderer.py — unified PromptRenderer tests.

These tests ensure the shared renderer preserves the legacy behaviour of
the previous scattered prompt-rendering helpers.
"""

from core.runtime.shared.prompt_renderer import PromptRenderer


class MockPromptObj:
    def receive(self, method, args):
        if method == "__to_prompt__":
            return "text_value"
        if method == "__payload_prompt__":
            return {"type": "image_url", "image_url": {"url": "data:..."}}
        return None

    def to_native(self):
        return "text_value"

    def __str__(self):
        return "text_value"


class MockPayloadObj:
    def receive(self, method, args):
        if method == "__payload_prompt__":
            return [{"type": "text", "text": "a"}]
        return None

    def to_native(self):
        return "text_value"

    def __str__(self):
        return "text_value"


class TestPromptRenderer:
    def test_to_prompt_str_uses_to_prompt(self):
        assert PromptRenderer.to_prompt_str(MockPromptObj()) == "text_value"

    def test_to_prompt_str_fallback_native(self):
        class NativeObj:
            def to_native(self):
                return "native_value"

        assert PromptRenderer.to_prompt_str(NativeObj()) == "native_value"

    def test_to_prompt_str_fallback_str(self):
        assert PromptRenderer.to_prompt_str(42) == "42"

    def test_to_prompt_str_builtin_renders_through_protocol_gate(self, engine_session):
        """D2 激活：内置类型经 satisfies/方法存在 前置门后仍经 receive 渲染
        为 __to_prompt__ 文本（gate 不改返回内容，仅激活 to_prompt 协议判定）。"""
        from core.runtime.shared.prompt_renderer import PromptRenderer
        v = engine_session.registry.box(5)
        assert PromptRenderer.to_prompt_str(v) == "5"

    def test_to_payload_returns_dict(self):
        result = PromptRenderer.to_payload(MockPromptObj())
        assert isinstance(result, dict)
        assert result["type"] == "image_url"

    def test_to_payload_returns_list(self):
        result = PromptRenderer.to_payload(MockPayloadObj())
        assert isinstance(result, list)
        assert result[0]["type"] == "text"

    def test_to_payload_fallback_to_text(self):
        class PlainObj:
            def receive(self, method, args):
                if method == "__payload_prompt__":
                    return None
                if method == "__to_prompt__":
                    return "plain"
                return None

            def to_native(self):
                return "plain"

        assert PromptRenderer.to_payload(PlainObj()) == "plain"
