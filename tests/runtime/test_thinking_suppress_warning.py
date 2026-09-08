"""
tests/runtime/test_thinking_suppress_warning.py

思考抑制失败警告（round3 R3-⑩ F-2）白箱契约：

- 可配置静默：``defaults.accept_forced_thinking = true`` = 用户已知晓后端
  强制思考为已知行为 → 警告静默；
- 警告通道 = stderr（stdout 是数据面——审计/适配警告不入数据面）；
- 语义澄清（reasoning 隔离字段 + 思考预算消耗 + 观测面）入警告文本；
- 一次性去重（每进程一次）保持；
- 配置落地：apply_config 将 defaults.accept_forced_thinking 落地 _config。
"""
import pytest

from ibci_modules.ibci_ai.core import AIPlugin


def _make_plugin(accept=False):
    plugin = AIPlugin()
    plugin.apply_config({
        "defaults": {
            "mock": True,
            "accept_forced_thinking": accept,
        },
        "default_model": {"base_url": "http://x/v1", "api_key": "k", "model": "m"},
    })
    plugin._config["model"] = "m"
    return plugin


class TestAcceptForcedThinking:
    def test_config_lands_in_provider(self):
        p = _make_plugin(accept=True)
        assert p._config.get("accept_forced_thinking") is True

    def test_config_default_false(self):
        p = _make_plugin(accept=False)
        assert p._config.get("accept_forced_thinking") is False

    def test_silenced_when_accepted(self, capsys):
        """accept_forced_thinking=true → 警告静默（无输出）。"""
        p = _make_plugin(accept=True)
        p._warn_thinking_suppress_failed(config_declared_non_reasoning=True)
        out = capsys.readouterr()
        assert out.out == "" and out.err == ""

    def test_warns_to_stderr_when_not_accepted(self, capsys):
        """未确认 → 警告走 stderr（非 stdout 数据面）。"""
        p = _make_plugin(accept=False)
        p._warn_thinking_suppress_failed(config_declared_non_reasoning=True)
        out = capsys.readouterr()
        assert out.out == ""  # stdout 数据面干净
        assert "思考" in out.err
        assert "accept_forced_thinking" in out.err

    def test_semantic_clarification_present(self, capsys):
        """语义澄清：reasoning 隔离 + 思考预算消耗 + 观测面。"""
        p = _make_plugin(accept=False)
        p._warn_thinking_suppress_failed()
        err = capsys.readouterr().err
        assert "reasoning_content" in err
        assert "tokens" in err
        assert "provider_meta" in err or "journal" in err

    def test_declared_non_reasoning_noted(self, capsys):
        """配置声明 reasoning:false 的失配提示。"""
        p = _make_plugin(accept=False)
        p._warn_thinking_suppress_failed(config_declared_non_reasoning=True)
        err = capsys.readouterr().err
        assert "reasoning:false" in err

    def test_once_per_process_dedup(self, capsys):
        """一次性去重：同进程第二次调用不再输出。"""
        p = _make_plugin(accept=False)
        p._warn_thinking_suppress_failed()
        first = capsys.readouterr().err
        p._warn_thinking_suppress_failed()
        second = capsys.readouterr().err
        assert "思考" in first
        assert second == ""
