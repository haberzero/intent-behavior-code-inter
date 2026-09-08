"""
tests/runtime/test_llm_reasoning_capture.py

C5 思考抑制重估——reasoning 捕获记录判别测试：

- 强制思考场景（思考抑制对该模型无效——模型仍输出 reasoning）：
  reasoning 内容记录进 provider_meta（``meta["reasoning"]``——调试时可见
  模型实际思考过程；此前仅告警、思考内容丢弃）；
- 空内容 + reasoning 非空 = 模型只思考未作答——RUN_LLM_EMPTY_CONTENT
  确定性诊断（既有语义回归）；
- 无 reasoning 响应：provider_meta 无 reasoning 键（正常路径不变）。
"""

import pytest

from core.base.llm_protocol import LLMCallRequest
from ibci_modules.ibci_ai.provider_impl import LLMProviderError, RecommendedProvider


def _base_cfg():
    return {
        "defaults": {"timeout": 30, "retry": 3},
        "providers": {"p1": {"base_url": "http://127.0.0.1:1/v1", "api_key": "k"}},
        "models": {},
        "default_model": {"model": "m", "provider": "p1"},
    }


def _make_provider():
    from ibci_modules.ibci_ai.config_loader import ApiConfig
    from ibci_modules.ibci_ai.config_normalize import to_llm_config

    prov = RecommendedProvider()
    prov.apply_config(to_llm_config(ApiConfig.validate(_base_cfg())))
    return prov


class _Msg:
    def __init__(self, content, reasoning_content=None, finish_reason="stop"):
        self.content = content
        self.reasoning_content = reasoning_content
        self.finish_reason = finish_reason


class _Choice:
    def __init__(self, message, finish_reason="stop"):
        self.message = message
        self.finish_reason = finish_reason


class _Completion:
    def __init__(self, message, finish_reason="stop"):
        self.choices = [_Choice(message, finish_reason)]


class _Completions:
    def __init__(self, completion):
        self._completion = completion

    def create(self, **kwargs):
        return self._completion


class _Chat:
    def __init__(self, completion):
        self.completions = _Completions(completion)


class _FakeClient:
    def __init__(self, completion):
        self.chat = _Chat(completion)


def _call_with_reasoning(provider, reasoning_content, content="ok-answer"):
    """驱动 provider 真实调用路径（fake client + 已探测非推理模型）。"""
    provider._model_capabilities.update({"probed": True, "is_reasoning": False})
    completion = _Completion(_Msg(content, reasoning_content))
    provider._resolve_client = lambda target_model, require=True: (
        _FakeClient(completion), target_model
    )
    req = LLMCallRequest(node_uid="t", user_prompt="x", target_model="m")
    return provider.call(req)


class TestReasoningCapture:
    def test_reasoning_recorded_in_provider_meta(self):
        """reasoning 非空 → provider_meta 记录（强制思考可观测面）。"""
        provider = _make_provider()
        result = _call_with_reasoning(provider, reasoning_content="step1; step2")
        meta = result.provider_meta
        assert meta.get("reasoning") == "step1; step2"

    def test_empty_content_with_reasoning_fail_fast(self):
        """空内容 + reasoning = 只思考未作答 → RUN_LLM_EMPTY_CONTENT（既有）。"""
        provider = _make_provider()
        with pytest.raises(LLMProviderError) as exc:
            _call_with_reasoning(provider, reasoning_content="only thinking",
                                 content="")
        assert exc.value.code == "RUN_LLM_EMPTY_CONTENT"

    def test_no_reasoning_no_meta_key(self):
        """无 reasoning 响应 → provider_meta 无 reasoning 键（正常路径不变）。"""
        provider = _make_provider()
        result = _call_with_reasoning(provider, reasoning_content=None)
        assert "reasoning" not in result.provider_meta
