"""
tests/contracts/test_mock_scenario.py

MOCK 指令语言契约测试（MockScenarioEngine）：

- ``MOCK:STR`` 全量语义：指令后的完整内容原样回显（空格/冒号/JSON 对象
  忠实保留）；显式引号包裹形式去引号（兼容形态）；
- 结构化指令（INT/FLOAT/BOOL/LIST/DICT）既有语义回归（首 token /
  窗口提取）。
"""

import pytest

from ibci_modules.ibci_ai.mock_scenario import MockScenarioEngine


@pytest.fixture
def engine():
    return MockScenarioEngine()


class TestMockStrFullSemantics:
    """MOCK:STR 全量语义（含空格/冒号/JSON 内容忠实回显）。"""

    def test_plain_word(self, engine):
        assert engine.handle("MOCK:STR:hello").content == "hello"

    def test_with_spaces(self, engine):
        assert engine.handle("MOCK:STR:mocked 测试").content == "mocked 测试"

    def test_json_object_with_colon_space(self, engine):
        # JSON 对象（冒号 + 空格）——此前截断为首 token（`{"a":`），
        # 全量语义下忠实回显完整 JSON
        assert engine.handle('MOCK:STR:{"a": 1}').content == '{"a": 1}'

    def test_json_array(self, engine):
        assert engine.handle("MOCK:STR:[1, 2, 3]").content == "[1, 2, 3]"

    def test_quoted_form_strips_quotes(self, engine):
        # 显式引号包裹 = 去引号（兼容形态，既有语义保持）
        assert engine.handle('MOCK:STR:"hello world"').content == "hello world"

    def test_single_quoted(self, engine):
        assert engine.handle("MOCK:STR:'a b'").content == "a b"


class TestMockStructuredDirectives:
    """结构化指令既有语义回归（首 token / 窗口提取）。"""

    def test_int(self, engine):
        assert engine.handle("MOCK:INT:42").content == "42"

    def test_int_ignores_trailing(self, engine):
        assert engine.handle("MOCK:INT:7 now").content == "7"

    def test_float(self, engine):
        assert engine.handle("MOCK:FLOAT:3.14").content == "3.14"

    def test_bool_true(self, engine):
        assert engine.handle("MOCK:BOOL:TRUE").content == "1"

    def test_bool_false(self, engine):
        assert engine.handle("MOCK:BOOL:FALSE").content == "0"

    def test_list_window(self, engine):
        assert engine.handle("MOCK:LIST:[1,2,3]").content == "[1,2,3]"

    def test_dict_window(self, engine):
        assert engine.handle('MOCK:DICT:{"a":1}').content == '{"a":1}'

    def test_non_mock_passthrough(self, engine):
        assert engine.handle("plain prompt").content == "[MOCK] plain prompt"
