"""
tests/plugins/test_idbg_show_environment.py

D1 idbg 增强——show_environment 环境可视化面判别测试（B3/E2 延伸）：

- 空环境输出（"(空)"）；
- 有值环境输出（key=value 行 + 键数/帧数统计）；
- use 替换后输出反映新当前环境。

注：show_environment 经 Python print（sys.stdout）输出——测试用 capsys
捕获（idbg 可视化面先例，同 show_intents/show_protection_map）。
"""

import pytest

from core.engine import IBCIEngine


@pytest.fixture
def engine():
    return IBCIEngine(root_dir=".")


class TestShowEnvironment:
    def test_empty_environment(self, engine, capsys):
        engine.run_string(
            "import idbg\n"
            "idbg.show_environment()\n",
            silent=True)
        text = capsys.readouterr().out
        assert "[IDBG] 当前环境" in text and "(空)" in text

    def test_populated_environment(self, engine, capsys):
        engine.run_string(
            "import idbg\n"
            "environment e = environment()\n"
            'e.set("mode", "draft")\n'
            'e.set("world", "garden")\n'
            "environment.use(e)\n"
            "idbg.show_environment()\n",
            silent=True)
        text = capsys.readouterr().out
        assert "mode='draft'" in text and "world='garden'" in text
        assert "键数(去重遮蔽后): 2" in text and "帧数: 1" in text

    def test_use_replace_reflected(self, engine, capsys):
        engine.run_string(
            "import idbg\n"
            "environment e = environment()\n"
            'e.set("k", 1)\n'
            "environment.use(e)\n"
            "environment empty = environment()\n"
            "environment.use(empty)\n"
            "idbg.show_environment()\n",
            silent=True)
        text = capsys.readouterr().out
        assert "(空)" in text and "k=1" not in text
