"""
tests/runtime/test_llm_generation_params.py

生成参数面与采样姿态审计（N1 思考模型支持 + N4 finish_reason 暴露）单元测试：

- 配置层（model 条目标准生成参数 + extra_body 透传口子 + 未知字段严格性）；
- provider 参数解析（标准参数/ vendor 扩展参数路由——top_k 经 extra_body；
  缺省 = 不发送）；
- 空内容确定性处理（content 空 + reasoning 非空 = RUN_LLM_EMPTY_CONTENT
  fail-fast——不再静默以 reasoning 替代 content）；
- 注册/配置参数面 fail-fast（未知参数/范围违约）；
- call_info 采样姿态审计闭环（finish_reason + generation 有效值）。
"""

import json

import pytest

from core.base.diagnostics.codes import (
    CFG_CONFIG_INVALID_FIELD_TYPE,
    CFG_CONFIG_UNKNOWN_FIELD,
)
from core.base.llm_protocol import LLMCallRequest
from core.kernel.issue import InterpreterError
from ibci_modules.ibci_ai.config_loader import ApiConfig
from ibci_modules.ibci_ai.provider_impl import RecommendedProvider


def _base_cfg(models=None, defaults=None):
    return {
        "defaults": defaults or {"timeout": 30, "retry": 3},
        "providers": {"p1": {"base_url": "http://127.0.0.1:1/v1", "api_key": "k"}},
        "models": models or {},
        "default_model": {"model": "m", "provider": "p1"},
    }


def _make_provider(cfg_dict=None):
    prov = RecommendedProvider()
    if cfg_dict is not None:
        from ibci_modules.ibci_ai.config_normalize import to_llm_config
        prov.apply_config(to_llm_config(ApiConfig.validate(cfg_dict)))
    return prov


class TestConfigGenerationFields:
    def test_standard_fields_passthrough(self):
        r = ApiConfig.validate(_base_cfg({
            "g": {"model": "gm", "provider": "p1", "temperature": 0.7,
                  "top_p": 0.9, "top_k": 40, "seed": 42,
                  "extra_body": {"enable_thinking": False}}}))
        m = r["models"]["g"]
        assert m["temperature"] == 0.7
        assert m["top_p"] == 0.9
        assert m["top_k"] == 40
        assert m["seed"] == 42
        assert m["extra_body"] == {"enable_thinking": False}

    def test_unknown_field_fail_fast(self):
        with pytest.raises(InterpreterError) as exc:
            ApiConfig.validate(_base_cfg({
                "x": {"model": "m2", "provider": "p1", "temprature": 0.7}}))
        assert exc.value.error_code == CFG_CONFIG_UNKNOWN_FIELD

    @pytest.mark.parametrize("field,value", [
        ("temperature", 3.0), ("temperature", -0.1),
        ("top_p", 1.5), ("top_p", -1),
        ("top_k", 0), ("top_k", -3),
        ("seed", -1),
    ])
    def test_range_fail_fast(self, field, value):
        with pytest.raises(InterpreterError) as exc:
            ApiConfig.validate(_base_cfg({
                "x": {"model": "m2", "provider": "p1", field: value}}))
        assert exc.value.error_code == CFG_CONFIG_INVALID_FIELD_TYPE

    def test_extra_body_must_be_object(self):
        with pytest.raises(InterpreterError) as exc:
            ApiConfig.validate(_base_cfg({
                "x": {"model": "m2", "provider": "p1", "extra_body": [1, 2]}}))
        assert exc.value.error_code == CFG_CONFIG_INVALID_FIELD_TYPE


class TestProviderParamResolution:
    def test_default_no_generation_params(self):
        prov = _make_provider(_base_cfg())
        assert prov._resolve_generation_params("") == {}, "缺省 = 不发送（vendor 默认）"
        assert prov._resolve_extra_body("") == {}, "无 extra_body 声明 = 空（不发送）"

    def test_named_model_params(self):
        prov = _make_provider(_base_cfg({
            "v": {"model": "vm", "provider": "p1", "temperature": 0.3,
                  "top_p": 0.8, "top_k": 20, "seed": 7,
                  "extra_body": {"enable_thinking": False}}}))
        params = prov._resolve_generation_params("v")
        assert params == {"temperature": 0.3, "top_p": 0.8, "seed": 7}, \
            "top_k 走 vendor 扩展通道（extra_body），不进 SDK kwarg 面"
        eb = prov._resolve_extra_body("v")
        assert eb["top_k"] == 20
        assert eb["enable_thinking"] is False, "配置 extra_body 原样合并"

    def test_named_overrides_default(self):
        prov = _make_provider(_base_cfg({
            "v": {"model": "vm", "provider": "p1", "temperature": 0.1},
        }))
        prov._config["temperature"] = 0.9
        assert prov._resolve_generation_field("v", "temperature") == 0.1
        assert prov._resolve_generation_field("", "temperature") == 0.9


class TestEmptyContentDeterministic:
    """空内容确定性处理：content 空 + reasoning 非空 = 显式诊断，不静默替代。"""

    def _mock_client(self, content, reasoning_content):
        class _Msg:
            def __init__(self):
                self.content = content
                self.reasoning_content = reasoning_content

        class _Choice:
            def __init__(self):
                self.message = _Msg()
                self.finish_reason = "stop"

        class _Completion:
            def __init__(self):
                self.choices = [_Choice()]

        class _Completions:
            def create(self, **kwargs):
                return _Completion()

        class _Chat:
            completions = _Completions()

        class _Client:
            chat = _Chat()

        return _Client()

    def test_empty_content_reasoning_only_raises(self):
        prov = _make_provider(_base_cfg())
        prov._client = self._mock_client(content=None, reasoning_content="思考中…")
        prov._model_capabilities["is_reasoning"] = True
        prov._model_capabilities["probed"] = True
        req = LLMCallRequest(node_uid="t", user_prompt="x", target_model="")
        with pytest.raises(Exception) as exc:
            prov.call(req)
        assert getattr(exc.value, "code", None) == "RUN_LLM_EMPTY_CONTENT"

    def test_empty_content_empty_reasoning_ok(self):
        prov = _make_provider(_base_cfg())
        prov._client = self._mock_client(content="", reasoning_content=None)
        prov._model_capabilities["is_reasoning"] = False
        prov._model_capabilities["probed"] = True
        req = LLMCallRequest(node_uid="t", user_prompt="x", target_model="")
        result = prov.call(req)
        assert result.content == ""
        assert result.finish_reason == "stop", "finish_reason 契约面暴露"

    def test_finish_reason_in_call_result(self):
        prov = _make_provider(_base_cfg())
        prov._client = self._mock_client(content="答案", reasoning_content=None)
        prov._model_capabilities["is_reasoning"] = False
        prov._model_capabilities["probed"] = True
        req = LLMCallRequest(node_uid="t", user_prompt="x", target_model="")
        result = prov.call(req)
        assert result.finish_reason == "stop"
        # 观测面：provider_meta 单通道回填（内核 _call_info merge 面）
        assert result.provider_meta.get("finish_reason") == "stop"
        assert "max_tokens" in result.provider_meta.get("generation", {})


class TestRegistrationFailFast:
    def test_register_model_range_fail_fast(self):
        prov = _make_provider(_base_cfg())
        with pytest.raises(TypeError):
            prov.register_model("v", "u", "k", "m", temperature=99.0)

    def test_register_model_extra_body_must_be_dict(self):
        prov = _make_provider(_base_cfg())
        with pytest.raises(TypeError):
            prov.register_model("v", "u", "k", "m", extra_body=[1])

    def test_set_config_unknown_silence_removed(self):
        # set_config 参数面显式声明——未知参数面不再存在（**kwargs 已移除；
        # 语言面经 spec SEM_UNKNOWN_KEYWORD 编译期拦截，Python 面经 TypeError）
        prov = _make_provider(_base_cfg())
        with pytest.raises(TypeError):
            prov.set_config("u", "k", "m", unknown_param=1)
