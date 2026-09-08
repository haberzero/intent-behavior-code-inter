"""
tests/runtime/test_rate_limit_backoff.py

429 限流退避（round3 R3-⑪ R-7）白箱契约：

- backoff_s 配置落地（api_config defaults → CallDefaults → provider _config）；
- _is_rate_limit_error：429 检测（openai.RateLimitError / status_code==429）；
- _apply_rate_limit_backoff：backoff_s>0 记录退避事件（call_info）；0 = 不记录
  （零侵入）；
- 集成：call() 遇 429 → 退避事件入 call_info + 上抛（供重试层退避后重试）。
"""
import pytest

from core.base.llm_protocol.llm_call import LLMCallRequest
from ibci_modules.ibci_ai.core import AIPlugin


def _make_plugin(backoff_s=0.0):
    plugin = AIPlugin()
    plugin.apply_config({
        "defaults": {"mock": False, "backoff_s": backoff_s},
        "default_model": {"base_url": "http://x/v1", "api_key": "k", "model": "m"},
    })
    plugin._config["model"] = "m"
    plugin._model_capabilities["probed"] = True
    plugin._model_capabilities["is_reasoning"] = False
    return plugin


class _FakeReq:
    pass


class _FakeResp:
    status_code = 429
    request = _FakeReq()
    headers = {}


class _Fake429(RuntimeError):
    """RuntimeError 子类（∈ _PROVIDER_ERRORS）+ status_code=429。

    真实 429 = openai.RateLimitError（⊂ OpenAIError ∈ _PROVIDER_ERRORS）；
    此处以 RuntimeError 子类 + status_code 属性模拟（走 status_code 检测支）。
    """
    def __init__(self):
        super().__init__("Error code: 429 - rate limit exceeded")
        self.status_code = 429
        self.response = _FakeResp()


class _FakeCompletions:
    def create(self, **kw):
        raise _Fake429()


class _FakeChat:
    completions = _FakeCompletions()


class _FakeClient:
    chat = _FakeChat()


class TestBackoffConfig:
    def test_backoff_s_lands_in_provider(self):
        p = _make_plugin(backoff_s=1.5)
        assert p._config.get("backoff_s") == 1.5

    def test_backoff_s_default_zero(self):
        p = _make_plugin()
        assert p._config.get("backoff_s") == 0.0


class TestIsRateLimitError:
    def test_detects_status_429(self):
        p = _make_plugin()
        assert p._is_rate_limit_error(_Fake429()) is True

    def test_detects_via_response_status(self):
        class E(Exception):
            def __init__(self):
                super().__init__("x")
                self.response = _FakeResp()
        p = _make_plugin()
        assert p._is_rate_limit_error(E()) is True

    def test_rejects_non_429(self):
        class E500(Exception):
            status_code = 500
        p = _make_plugin()
        assert p._is_rate_limit_error(E500()) is False

    def test_rejects_generic(self):
        p = _make_plugin()
        assert p._is_rate_limit_error(RuntimeError("boom")) is False

    def test_detects_real_openai_ratelimit_error(self):
        """真实 openai.RateLimitError（isinstance 支）检测。"""
        pytest.importorskip("openai")
        import openai
        # isinstance(openai.RateLimitError) 命中即 True（无需构造完整 response）
        err = openai.RateLimitError("rate limited", response=_FakeResp(), body=None)
        p = _make_plugin()
        assert p._is_rate_limit_error(err) is True


class TestApplyBackoff:
    def test_records_event_when_positive(self):
        p = _make_plugin(backoff_s=0.01)
        p._last_call_info = {}
        p._apply_rate_limit_backoff(_Fake429())
        info = p._last_call_info
        assert "last_backoff" in info
        assert info["last_backoff"]["delay_s"] == 0.01
        assert info["last_backoff"]["reason"] == "rate_limit_429"

    def test_no_event_when_zero(self):
        p = _make_plugin(backoff_s=0.0)
        p._last_call_info = {}
        p._apply_rate_limit_backoff(_Fake429())
        assert "last_backoff" not in p._last_call_info


class TestCallIntegration:
    def test_429_triggers_backoff_and_raises(self):
        """call() 遇 429 → 退避事件入 call_info + 上抛 RuntimeError。"""
        p = _make_plugin(backoff_s=0.02)
        p._client = _FakeClient()  # 注入 fake client（bypass _init_client）
        p._last_call_info = {}
        req = LLMCallRequest(node_uid="n", user_prompt="hi")
        with pytest.raises(Exception) as ei:
            p.call(req)
        # 上抛（包装为泛化调用失败）
        assert "429" in str(ei.value) or "rate" in str(ei.value).lower()
        # 退避事件已记录
        assert "last_backoff" in p._last_call_info
        assert p._last_call_info["last_backoff"]["delay_s"] == 0.02

    def test_no_backoff_when_zero(self):
        """backoff_s=0（缺省）→ 429 上抛但无退避事件（零侵入）。"""
        p = _make_plugin(backoff_s=0.0)
        p._client = _FakeClient()
        p._last_call_info = {}
        req = LLMCallRequest(node_uid="n", user_prompt="hi")
        with pytest.raises(Exception):
            p.call(req)
        assert "last_backoff" not in p._last_call_info
