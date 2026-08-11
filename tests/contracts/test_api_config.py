"""tests/contracts/test_api_config.py - api_config.json 加载与校验契约测试。

覆盖 ApiConfig（load/validate/env 引用/诊断码）+ AIPlugin（apply_config/set_mock_mode/
引擎自动加载）。
"""
import json

import pytest

from core.kernel.issue import InterpreterError
from core.base.diagnostics.codes import (
    CFG_CONFIG_ENV_VAR_MISSING,
    CFG_CONFIG_INVALID_FIELD_TYPE,
    CFG_CONFIG_INVALID_JSON,
    CFG_CONFIG_MISSING_DEFAULT,
    CFG_CONFIG_MISSING_FIELD,
    CFG_CONFIG_NOT_FOUND,
    CFG_CONFIG_NOT_OBJECT,
    CFG_CONFIG_UNKNOWN_MODEL_REF,
    CFG_CONFIG_UNKNOWN_PROVIDER,
)
from ibci_modules.ibci_ai.config_loader import ApiConfig
from ibci_modules.ibci_ai.core import AIPlugin


class TestApiConfigValidate:
    def test_legacy_default_model_object(self):
        data = {"default_model": {"base_url": "http://x/v1", "api_key": "k", "model": "m"}}
        result = ApiConfig.validate(data)
        assert result["default_model"]["base_url"] == "http://x/v1"
        assert result["default_model"]["timeout"] == 30.0
        assert result["default_model"]["reasoning"] is False
        assert result["models"] == {}
        assert result["defaults"]["mock"] is False

    def test_full_schema_providers_models_defaults(self):
        data = {
            "defaults": {"timeout": 60.0, "retry": 5, "mock": False},
            "providers": {"p1": {"base_url": "http://x/v1", "api_key": "k"}},
            "models": {
                "default": {"provider": "p1", "model": "m", "reasoning": False},
                "fast": {"provider": "p1", "model": "m2", "timeout": 15.0},
            },
            "default_model": "default",
        }
        result = ApiConfig.validate(data)
        assert result["default_model"]["base_url"] == "http://x/v1"
        assert result["default_model"]["timeout"] == 60.0
        assert result["models"]["fast"]["timeout"] == 15.0

    def test_default_model_string_ref(self):
        data = {
            "models": {"local": {"base_url": "http://x/v1", "api_key": "k", "model": "m"}},
            "default_model": "local",
        }
        result = ApiConfig.validate(data)
        assert result["default_model"]["model"] == "m"

    def test_env_reference_resolved(self, monkeypatch):
        monkeypatch.setenv("TEST_API_KEY", "secret123")
        data = {
            "providers": {"p": {"base_url": "http://x/v1", "api_key": "{env:TEST_API_KEY}"}},
            "models": {"default": {"provider": "p", "model": "m"}},
            "default_model": "default",
        }
        result = ApiConfig.validate(data)
        assert result["default_model"]["api_key"] == "secret123"

    def test_not_object(self):
        with pytest.raises(InterpreterError) as exc:
            ApiConfig.validate([])
        assert exc.value.error_code == CFG_CONFIG_NOT_OBJECT

    def test_missing_default(self):
        with pytest.raises(InterpreterError) as exc:
            ApiConfig.validate({"models": {}})
        assert exc.value.error_code == CFG_CONFIG_MISSING_DEFAULT

    def test_default_model_invalid_type(self):
        with pytest.raises(InterpreterError) as exc:
            ApiConfig.validate({"default_model": 123})
        assert exc.value.error_code == CFG_CONFIG_INVALID_FIELD_TYPE

    def test_missing_field(self):
        with pytest.raises(InterpreterError) as exc:
            ApiConfig.validate({"default_model": {"base_url": "x", "api_key": "y"}})
        assert exc.value.error_code == CFG_CONFIG_MISSING_FIELD

    def test_invalid_field_type(self):
        with pytest.raises(InterpreterError) as exc:
            ApiConfig.validate({"default_model": {"base_url": 123, "api_key": "y", "model": "m"}})
        assert exc.value.error_code == CFG_CONFIG_INVALID_FIELD_TYPE

    def test_unknown_model_ref(self):
        with pytest.raises(InterpreterError) as exc:
            ApiConfig.validate({"default_model": "nonexistent"})
        assert exc.value.error_code == CFG_CONFIG_UNKNOWN_MODEL_REF

    def test_unknown_provider(self):
        with pytest.raises(InterpreterError) as exc:
            ApiConfig.validate({
                "models": {"default": {"provider": "nope", "model": "m"}},
                "default_model": "default",
            })
        assert exc.value.error_code == CFG_CONFIG_UNKNOWN_PROVIDER

    def test_env_var_missing(self, monkeypatch):
        monkeypatch.delenv("NEVER_SET_VAR", raising=False)
        with pytest.raises(InterpreterError) as exc:
            ApiConfig.validate({
                "default_model": {"base_url": "{env:NEVER_SET_VAR}", "api_key": "k", "model": "m"},
            })
        assert exc.value.error_code == CFG_CONFIG_ENV_VAR_MISSING


class TestApiConfigLoad:
    def test_load_success(self, tmp_path):
        config_file = tmp_path / "api_config.json"
        config_file.write_text(json.dumps({
            "default_model": {"base_url": "http://x/v1", "api_key": "k", "model": "m"}
        }), encoding="utf-8")
        result = ApiConfig.load(str(config_file))
        assert result["default_model"]["model"] == "m"

    def test_load_not_found(self):
        with pytest.raises(InterpreterError) as exc:
            ApiConfig.load("/nonexistent/path/api_config.json")
        assert exc.value.error_code == CFG_CONFIG_NOT_FOUND

    def test_load_invalid_json(self, tmp_path):
        config_file = tmp_path / "api_config.json"
        config_file.write_text("{invalid json", encoding="utf-8")
        with pytest.raises(InterpreterError) as exc:
            ApiConfig.load(str(config_file))
        assert exc.value.error_code == CFG_CONFIG_INVALID_JSON


class TestAIPluginConfig:
    def test_apply_config_mock_mode(self):
        """apply_config defaults.mock=true -> set_mock_mode（不调 openai）。"""
        plugin = AIPlugin()
        plugin.apply_config({
            "defaults": {"mock": True},
            "default_model": {"base_url": "http://x/v1", "api_key": "k", "model": "m"},
        })
        assert plugin._is_test_mode() is True
        assert plugin.has_api_key() is True

    def test_apply_config_registers_named_models(self):
        """apply_config 注册 models（供 @NAME~ 路由）。"""
        plugin = AIPlugin()
        plugin.apply_config({
            "defaults": {"mock": True},
            "default_model": {"base_url": "http://x/v1", "api_key": "k", "model": "m"},
            "models": {
                "local": {"base_url": "http://ollama/v1", "api_key": "o", "model": "qwen"},
            },
        })
        assert "local" in plugin._model_registry
        assert plugin._model_registry["local"]["model"] == "qwen"

    def test_set_mock_mode(self):
        plugin = AIPlugin()
        plugin.set_mock_mode()
        assert plugin._is_test_mode() is True
        assert plugin.has_api_key() is True

    def test_set_config_exits_mock(self):
        """set_config 显式退出 mock 模式（_config["mock"]=False）。"""
        plugin = AIPlugin()
        plugin.set_mock_mode()
        assert plugin._is_test_mode() is True
        try:
            plugin.set_config("http://x/v1", "k", "m")
        except RuntimeError:
            pass  # openai 未安装时 _init_client 失败，但 mock 标志已清
        assert plugin._config.get("mock") is False

    def test_mock_mode_llm_call(self):
        """MOCK 模式下 __call__ 走 MockScenarioEngine（不发起网络请求）。"""
        plugin = AIPlugin()
        plugin.set_mock_mode()
        result = plugin("sys", "MOCK:STR:hello")
        assert result == "hello"


class TestEngineAutoLoad:
    def test_engine_auto_loads_api_config(self, tmp_path, monkeypatch):
        """引擎启动时自动加载 project_root/api_config.json（mock 配置）。"""
        from core.engine import IBCIEngine

        config_file = tmp_path / "api_config.json"
        config_file.write_text(json.dumps({
            "defaults": {"mock": True},
            "default_model": {"base_url": "http://x/v1", "api_key": "k", "model": "m"},
        }), encoding="utf-8")

        script = tmp_path / "probe.ibci"
        script.write_text(
            "import ai\n"
            "if ai.has_api_key():\n"
            "    print(\"auto-loaded\")\n"
            "else:\n"
            "    print(\"not-loaded\")\n",
            encoding="utf-8",
        )

        outputs = []
        engine = IBCIEngine(root_dir=str(tmp_path))
        engine.run(str(script), output_callback=lambda s: outputs.append(s))
        assert "auto-loaded" in "".join(outputs)
