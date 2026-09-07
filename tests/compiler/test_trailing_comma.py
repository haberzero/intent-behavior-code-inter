"""
tests/compiler/test_trailing_comma.py

容器字面量尾逗号（A3）判别测试：

- list/dict 字面量尾逗号接受（单行/多行形态）；
- 多行容器字面量惯例（尾逗号是"最后一个元素"的显式标记——diff 友好）；
- 正常形态（无尾逗号）与空容器行为不变。
"""

import os

import pytest

from core.engine import IBCIEngine


@pytest.fixture
def engine():
    return IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)))


class TestListTrailingComma:
    def test_single_line(self, engine):
        out = []
        engine.run_string("list l = [1, 2, 3,]\nprint(l)\n",
                          output_callback=out.append, silent=True)
        assert out and "[1, 2, 3]" in out[0]

    def test_multi_line(self, engine):
        out = []
        engine.run_string(
            "list l = [\n"
            "    1,\n"
            "    2,\n"
            "    3,\n"
            "]\n"
            "print(l)\n",
            output_callback=out.append, silent=True)
        assert out and "[1, 2, 3]" in out[0]

    def test_without_trailing_comma(self, engine):
        out = []
        engine.run_string("list l = [\n    1,\n    2\n]\nprint(l)\n",
                          output_callback=out.append, silent=True)
        assert out and "[1, 2]" in out[0]

    def test_single_element_trailing(self, engine):
        out = []
        engine.run_string("list l = [1,]\nprint(l)\n",
                          output_callback=out.append, silent=True)
        assert out and "[1]" in out[0]


class TestDictTrailingComma:
    def test_single_line(self, engine):
        out = []
        engine.run_string('dict d = {"a": 1,}\nprint(d)\n',
                          output_callback=out.append, silent=True)
        assert out and '"a": 1' in out[0]

    def test_multi_line(self, engine):
        out = []
        engine.run_string(
            'dict d = {\n'
            '    "a": 1,\n'
            '    "b": 2,\n'
            '}\n'
            "print(d)\n",
            output_callback=out.append, silent=True)
        assert out and '"b": 2' in out[0]

    def test_single_entry_trailing(self, engine):
        out = []
        engine.run_string('dict d = {"k": 7,}\nint v = (int)d["k"]\nprint(v)\n',
                          output_callback=out.append, silent=True)
        assert out and out[0].strip() == "7"


class TestEmptyContainersUnchanged:
    def test_empty_list(self, engine):
        out = []
        engine.run_string("list l = []\nprint(l)\n",
                          output_callback=out.append, silent=True)
        assert out and "[]" in out[0]

    def test_empty_dict(self, engine):
        out = []
        engine.run_string("dict d = {}\nprint(d)\n",
                          output_callback=out.append, silent=True)
        assert out and "{}" in out[0]
