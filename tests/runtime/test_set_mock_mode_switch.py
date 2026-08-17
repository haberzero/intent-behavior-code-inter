"""
tests/runtime/test_set_mock_mode_switch.py
============================================

``ai.set_mock_mode(enable: bool = True)`` 对称开关判别性回归（T05 §六.4）。

锁定语义：
- ``set_mock_mode()``（默认 True）进入 MOCK 模式，``@~ MOCK:STR:~`` 生效。
- ``set_mock_mode(False)`` 退出 MOCK 模式（重建真实客户端）；未配置 url/key
  时 fail-fast（不静默停留半配置状态）。
- mock → 真实（配置后）→ mock 往返切换可用。
- 单向旧用法（无参调用）保持兼容（默认进入）。
"""
import pytest

from core.engine import IBCIEngine
from tests.conftest import REPO_ROOT


def _run(code: str, root_dir=REPO_ROOT):
    engine = IBCIEngine(root_dir=root_dir)
    lines = []
    engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
    return lines


class TestSetMockModeSwitch:
    def test_enter_mock_default_true(self):
        """无参 set_mock_mode() 默认进入 MOCK 模式（单向旧用法兼容）。"""
        code = (
            "import ai\n"
            "ai.set_mock_mode()\n"
            "str m = @~ MOCK:STR:hello ~\n"
            "print(m)\n"
        )
        assert _run(code) == ["hello"]

    def test_exit_mock_without_config_fails_fast(self):
        """set_mock_mode(False) 未配置 url/key 时 fail-fast。"""
        code = (
            "import ai\n"
            "ai.set_mock_mode()\n"
            "str m = @~ MOCK:STR:hello ~\n"
            "print(m)\n"
            "ai.set_mock_mode(False)\n"
        )
        with pytest.raises(Exception, match="LLM 配置缺失|base_url"):
            _run(code)

    def test_mock_real_mock_roundtrip_with_config(self, tmp_path):
        """mock → 真实（配置后）→ mock 往返切换（判别性回归）。"""
        api_config = (
            '{\n'
            '  "defaults": { "timeout": 30.0, "retry": 1, "auto_intent_injection": true, "mock": false },\n'
            '  "providers": { "local": { "base_url": "http://127.0.0.1:1234/v1", "api_key": "lm-studio" } },\n'
            '  "models": { "default": { "provider": "local", "model": "mock", "reasoning": false } },\n'
            '  "default_model": "default"\n'
            '}\n'
        )
        (tmp_path / "api_config.json").write_text(api_config, encoding="utf-8")
        code = (
            "import ai\n"
            "ai.load_project_config()\n"
            "ai.set_mock_mode()\n"
            "str m1 = @~ MOCK:STR:mock1 ~\n"
            "print(m1)\n"
            "ai.set_mock_mode(False)\n"
            "print('exited')\n"
            "ai.set_mock_mode()\n"
            "str m2 = @~ MOCK:STR:mock2 ~\n"
            "print(m2)\n"
        )
        lines = _run(code, root_dir=str(tmp_path))
        assert lines == ["mock1", "exited", "mock2"]
