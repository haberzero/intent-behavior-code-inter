"""tests/contracts/test_api_config.py - api_config.json 加载与校验契约测试。

覆盖 ApiConfig（load/validate/env 引用/诊断码）+ AIPlugin（apply_config/set_mock_mode/
显式 load_project_config）。配置加载为显式动作（F9）：引擎启动不自动加载。
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


def _mcreq(sys_prompt="sys", user_prompt="user"):
    """把 scalar (sys, user) 转为一次 ``LLMCallRequest``（provider.call 消费）。"""
    from core.base.llm_protocol import LLMCallRequest, OutputContract
    from core.base.llm_protocol.llm_call import PromptSlot
    return LLMCallRequest(
        node_uid="",
        user_prompt=user_prompt,
        prompt_slots=[PromptSlot(kind="user_sys", text=sys_prompt)] if sys_prompt else [],
        output_contract=OutputContract(),
    )


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
        """MOCK 模式下 call() 走 MockScenarioEngine（不发起网络请求）。"""
        plugin = AIPlugin()
        plugin.set_mock_mode()
        result = plugin.call(_mcreq("sys", "MOCK:STR:hello"))
        assert result.content == "hello"


class TestEngineExplicitConfigLoad:
    def test_engine_no_auto_load_without_explicit_call(self, tmp_path):
        """引擎启动不自动加载 api_config.json——脚本不显式调用则无配置（F9）。"""
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
        assert "not-loaded" in "".join(outputs)

    def test_engine_loads_config_via_explicit_call(self, tmp_path):
        """脚本显式调用 ai.load_project_config() 后配置生效（F9）。"""
        from core.engine import IBCIEngine

        config_file = tmp_path / "api_config.json"
        config_file.write_text(json.dumps({
            "defaults": {"mock": True},
            "default_model": {"base_url": "http://x/v1", "api_key": "k", "model": "m"},
        }), encoding="utf-8")

        script = tmp_path / "probe.ibci"
        script.write_text(
            "import ai\n"
            "ai.load_project_config()\n"
            "if ai.has_api_key():\n"
            "    print(\"loaded\")\n"
            "else:\n"
            "    print(\"not-loaded\")\n",
            encoding="utf-8",
        )

        outputs = []
        engine = IBCIEngine(root_dir=str(tmp_path))
        engine.run(str(script), output_callback=lambda s: outputs.append(s))
        assert "loaded" in "".join(outputs)


class TestDocumentedAiApiReachable:
    """docs/syntax/11_modules.md §11.3 文档化的 ai API 语言级可达性。

    get_retry/is_auto_intent_injection_enabled 必须经 vtable 注册、IBCI 侧可调用
    （与 §11.3 其余文档化 API 一致）。
    """

    def _run(self, tmp_path, code):
        from core.engine import IBCIEngine

        script = tmp_path / "probe.ibci"
        script.write_text("import ai\n" + code, encoding="utf-8")
        outputs = []
        engine = IBCIEngine(root_dir=str(tmp_path))
        engine.run(str(script), output_callback=lambda s: outputs.append(s))
        return "".join(outputs)

    def test_get_retry_roundtrip(self, tmp_path):
        out = self._run(tmp_path, "ai.set_retry(7)\nprint((str)ai.get_retry())\n")
        assert "7" in out

    def test_is_auto_intent_injection_enabled(self, tmp_path):
        out = self._run(tmp_path, "print((str)ai.is_auto_intent_injection_enabled())\n")
        assert "True" in out

    def test_documented_api_swarm(self, tmp_path):
        """§11.3 文档化查询类 API 全部可调用（防漏注册再发）。"""
        out = self._run(
            tmp_path,
            "print((str)ai.has_api_key())\n"
            "print((str)ai.get_global_intents())\n"
            "print((str)ai.get_current_intent_stack())\n"
            "ai.set_return_type_prompt(\"int\", \"x\")\n"
            "print((str)ai.get_return_type_prompt(\"int\"))\n"
            "print((str)ai.get_current_call_info())\n"
            "ai.set_mock_mode()\n"
            "print((str)ai.get_retry())\n",
        )
        # 每行都应正常输出（无 VM: Call failed / None has no method）
        assert "None has no method" not in out
        assert "VM: Call failed" not in out

    def test_load_project_config_language_level(self, tmp_path):
        """语言级 ai.load_project_config() 可调用（无配置 no-op 合法态）。

        tmp 内立 ``.git`` 边界，向上发现止步于此（不触及仓库真实根配置）。
        """
        (tmp_path / ".git").mkdir()
        out = self._run(tmp_path, "ai.load_project_config()\nprint(\"ok\")\n")
        assert "ok" in out


class TestLoadProjectConfigContract:
    """F9：ai.load_project_config 显式加载契约（fail-fast 语义 + 路径规范化）。

    原 AIPlugin.setup 自动加载契约迁移至此——配置加载成为显式动作，契约
    （ec/project_root 注入 fail-fast、配置不存在 no-op、符号链接规范化）保留。
    """

    @staticmethod
    def _caps(ec):
        from core.extension.capabilities import PluginCapabilities
        return PluginCapabilities(execution_context=ec)

    @staticmethod
    def _ec(root):
        class _EC:
            def __init__(self, root):
                self._root = root

            def get_project_root(self):
                return self._root
        return _EC(root)

    def test_fails_fast_without_execution_context(self):
        """execution_context 未注入 = 注入异常 → fail-fast（不静默跳过）。"""
        plugin = AIPlugin()
        with pytest.raises(InterpreterError):
            plugin.load_project_config()

    def test_fails_fast_without_project_root(self):
        """execution_context 已注入但未确立 project_root = 注入异常 → fail-fast。"""
        plugin = AIPlugin()
        plugin.setup(self._caps(self._ec(None)))
        with pytest.raises(InterpreterError):
            plugin.load_project_config()

    def test_skips_silently_when_config_absent(self, tmp_path):
        """搜索界内无 api_config.json = 合法状态（用户无配置）→ no-op 静默跳过。

        tmp 内立 ``.git`` 边界：向上发现止步于此，不触及仓库真实根配置。
        """
        (tmp_path / ".git").mkdir()
        plugin = AIPlugin()
        plugin.setup(self._caps(self._ec(str(tmp_path))))
        plugin.load_project_config()
        assert plugin.has_api_key() is False
        assert plugin._is_test_mode() is False

    def test_loads_config_via_canonicalized_path(self, tmp_path):
        """project_root 经符号链接时仍能读到配置（canonicalize_for_security 生效）。"""
        import os
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        (real_dir / "api_config.json").write_text(json.dumps({
            "defaults": {"mock": True},
            "default_model": {"base_url": "http://x/v1", "api_key": "k", "model": "m"},
        }), encoding="utf-8")
        link_dir = tmp_path / "link"
        os.symlink(str(real_dir), str(link_dir))
        plugin = AIPlugin()
        plugin.setup(self._caps(self._ec(str(link_dir))))
        plugin.load_project_config()
        assert plugin._is_test_mode() is True
        assert plugin.has_api_key() is True

    def test_idempotent(self, tmp_path):
        """重复调用覆盖式应用，无累积副作用。"""
        (tmp_path / "api_config.json").write_text(json.dumps({
            "defaults": {"mock": True, "retry": 3},
            "default_model": {"base_url": "http://x/v1", "api_key": "k", "model": "m"},
        }), encoding="utf-8")
        plugin = AIPlugin()
        plugin.setup(self._caps(self._ec(str(tmp_path))))
        plugin.load_project_config()
        plugin.load_project_config()
        assert plugin._is_test_mode() is True
        assert plugin._config.get("retry") == 3


class TestConfigFailFastHardening:
    """配置机制 fail-fast 硬化。"""

    def test_env_ref_malformed_fails_fast(self):
        """`{env:lower}` 格式非法（非大写下划线）不得静默透传为字面量。"""
        with pytest.raises(InterpreterError) as ei:
            ApiConfig.validate({
                "default_model": {"base_url": "{env:lower_url}", "api_key": "k", "model": "m"}
            })
        assert "env" in str(ei.value)

    def test_empty_credentials_fail_fast(self):
        """F6：空/空白 base_url/api_key/model 不得通过校验（静默到调用期才报错）。"""
        for dm in (
            {"base_url": "", "api_key": "k", "model": "m"},
            {"base_url": "http://x", "api_key": "  ", "model": "m"},
            {"base_url": "http://x", "api_key": "k", "model": "  "},
        ):
            with pytest.raises(InterpreterError):
                ApiConfig.validate({"default_model": dm})

    def test_env_test_mode_does_not_override_explicit_config(self, monkeypatch):
        """环境变量 IBC_TEST_MODE 不得静默压过显式 set_config（mock 显式化）。"""
        monkeypatch.setenv("IBC_TEST_MODE", "1")
        plugin = AIPlugin()
        try:
            plugin.set_config("http://real/v1", "real-key", "real-model")
        except RuntimeError:
            pass  # openai 未安装时 _init_client 失败，但 mock 标志须已清
        assert plugin._is_test_mode() is False
        assert plugin._config.get("mock") is False

    def test_reasoning_true_declared_symmetrically(self):
        """reasoning:true 声明与 false 对称落 probed/is_reasoning（无误导告警）。"""
        plugin = AIPlugin()
        plugin.apply_config({
            "defaults": {},
            "default_model": {"base_url": "http://x/v1", "api_key": "k", "model": "m", "reasoning": True},
        })
        assert plugin._model_capabilities["probed"] is True
        assert plugin._model_capabilities["is_reasoning"] is True

    def test_dead_capability_fields_removed(self):
        """extract_strategy/supports_system 死字段不存在（写而不读的预留策略字段）。"""
        plugin = AIPlugin()
        assert "extract_strategy" not in plugin._model_capabilities
        assert "supports_system" not in plugin._model_capabilities


class TestConfigDiscovery:
    """api_config.json 向上发现契约（ProjectApiConfigAdapter.discover_config_path）。

    仓库根单源 + 子目录就近覆盖：自 project_root 向上找最近配置，搜索上界 =
    含 ``.git`` 的仓库根（不拾取仓库外配置）。
    """

    @staticmethod
    def _write_config(directory, **overrides):
        base = {
            "defaults": {"mock": True},
            "default_model": {"base_url": "http://x/v1", "api_key": "k", "model": "m"},
        }
        base.update(overrides)
        (directory / "api_config.json").write_text(json.dumps(base), encoding="utf-8")

    def test_finds_config_at_project_root_itself(self, tmp_path):
        from ibci_modules.ibci_ai.config_source_adapter import discover_config_path
        self._write_config(tmp_path)
        assert discover_config_path(str(tmp_path)) == str(tmp_path / "api_config.json")

    def test_finds_nearest_config_from_nested_dir(self, tmp_path):
        """两层配置时最近者胜（就近覆盖）。"""
        from ibci_modules.ibci_ai.config_source_adapter import discover_config_path
        inner = tmp_path / "inner" / "deeper"
        inner.mkdir(parents=True)
        self._write_config(tmp_path, defaults={"mock": False})
        self._write_config(tmp_path / "inner", defaults={"mock": True})
        assert discover_config_path(str(inner)) == str(tmp_path / "inner" / "api_config.json")

    def test_ancestor_config_serves_nested_project(self, tmp_path):
        """仓库根单源配置服务嵌套子目录（trial 体系收敛基础）。"""
        from ibci_modules.ibci_ai.config_source_adapter import discover_config_path
        nested = tmp_path / "repo" / "trials" / "T01"
        nested.mkdir(parents=True)
        self._write_config(tmp_path / "repo")
        assert discover_config_path(str(nested)) == str(tmp_path / "repo" / "api_config.json")

    def test_git_boundary_stops_walk(self, tmp_path):
        """搜索上界 = 含 .git 的目录：其上层的配置不可达。"""
        from ibci_modules.ibci_ai.config_source_adapter import discover_config_path
        repo = tmp_path / "outer" / "repo"
        inner = repo / "inner"
        inner.mkdir(parents=True)
        (repo / ".git").mkdir()
        self._write_config(tmp_path / "outer")
        assert discover_config_path(str(inner)) is None

    def test_repo_root_config_found_before_boundary_stop(self, tmp_path):
        """含 .git 的目录自身仍参与匹配（仓库根配置可达）。"""
        from ibci_modules.ibci_ai.config_source_adapter import discover_config_path
        repo = tmp_path / "repo"
        inner = repo / "trials" / "T01"
        inner.mkdir(parents=True)
        (repo / ".git").mkdir()
        self._write_config(repo)
        assert discover_config_path(str(inner)) == str(repo / "api_config.json")

    def test_no_config_within_boundary_returns_none(self, tmp_path):
        from ibci_modules.ibci_ai.config_source_adapter import discover_config_path
        (tmp_path / ".git").mkdir()
        assert discover_config_path(str(tmp_path / "sub")) is None

    def test_load_project_config_resolves_ancestor_config(self, tmp_path):
        """引擎级集成：嵌套 project_root 显式加载命中祖先配置。"""
        from core.engine import IBCIEngine
        repo = tmp_path / "repo"
        nested = repo / "trials" / "T01"
        nested.mkdir(parents=True)
        (repo / ".git").mkdir()
        self._write_config(repo, defaults={"mock": True})

        script = nested / "probe.ibci"
        script.write_text(
            "import ai\n"
            "ai.load_project_config()\n"
            "if ai.has_api_key():\n"
            "    print(\"loaded\")\n"
            "else:\n"
            "    print(\"not-loaded\")\n",
            encoding="utf-8",
        )
        outputs = []
        engine = IBCIEngine(root_dir=str(nested))
        engine.run(str(script), output_callback=lambda s: outputs.append(s))
        assert "loaded" in "".join(outputs)


class TestMaxTokensConfig:
    """per-model max_tokens 配置面（api_config 模型条目 → ModelSpec → provider 消费）。"""

    _BASE = {"base_url": "http://x/v1", "api_key": "k", "model": "m"}

    def test_validate_carries_max_tokens(self):
        """模型条目 max_tokens 经校验透传（正整数）。"""
        cfg = ApiConfig.validate({
            "default_model": {**self._BASE, "max_tokens": 2048},
        })
        assert cfg["default_model"]["max_tokens"] == 2048

    def test_validate_rejects_bad_max_tokens(self):
        """max_tokens 非正整数 fail-fast（CFG_CONFIG_INVALID_FIELD_TYPE）。"""
        for bad in (0, -1, "x", 1.5, True):
            with pytest.raises(InterpreterError):
                ApiConfig.validate({
                    "default_model": {**self._BASE, "max_tokens": bad},
                })

    def test_absent_max_tokens_not_in_validated(self):
        """未声明 max_tokens → 校验结果不含该键（provider 走内置默认）。"""
        cfg = ApiConfig.validate({"default_model": dict(self._BASE)})
        assert "max_tokens" not in cfg["default_model"]

    def test_apply_config_sets_max_tokens(self):
        """apply_config 落 max_tokens 到默认配置；_resolve_max_tokens 消费。"""
        from ibci_modules.ibci_ai.provider_impl import _MAX_TOKENS_DEFAULT
        plugin = AIPlugin()
        plugin.apply_config({
            "defaults": {},
            "default_model": {**self._BASE, "max_tokens": 2048},
        })
        assert plugin._config["max_tokens"] == 2048
        assert plugin._resolve_max_tokens("") == 2048

    def test_default_max_tokens_fallback(self):
        """未配置 max_tokens → 内置默认 4096。"""
        from ibci_modules.ibci_ai.provider_impl import _MAX_TOKENS_DEFAULT
        plugin = AIPlugin()
        plugin.apply_config({"defaults": {}, "default_model": dict(self._BASE)})
        assert "max_tokens" not in plugin._config or plugin._config["max_tokens"] is None
        assert plugin._resolve_max_tokens("") == _MAX_TOKENS_DEFAULT

    def test_named_model_max_tokens_override(self):
        """命名模型条目 max_tokens 覆盖默认（@NAME~ 路由消费注册项）。"""
        from ibci_modules.ibci_ai.provider_impl import _MAX_TOKENS_DEFAULT
        plugin = AIPlugin()
        plugin.apply_config({
            "defaults": {},
            "default_model": dict(self._BASE),
            "models": {"big": {**self._BASE, "model": "m2", "max_tokens": 8192}},
        })
        assert plugin._resolve_max_tokens("big") == 8192
        assert plugin._resolve_max_tokens("") == _MAX_TOKENS_DEFAULT
