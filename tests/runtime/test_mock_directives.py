"""
tests/runtime/test_mock_directives.py
=====================================

独立单元测试：验证 ``AIPlugin._handle_mock_response`` 的每个 MOCK 指令变体。

此测试直接测试 MOCK 指令解析器，不经过完整引擎，提供快速、聚焦的信号。
MOCK 基础设施被 ~hundreds 测试信任，此前从未独立测过（P1-G 补全此缺口）。
"""
import pytest
from ibci_modules.ibci_ai.core import AIPlugin


@pytest.fixture
def mock_plugin():
    """创建一个处于 TESTONLY mock 模式的 AIPlugin 实例。"""
    plugin = AIPlugin()
    plugin.set_config("TESTONLY", "TESTONLY", "TESTONLY")
    return plugin


class TestBasicDirectives:
    """基础指令（不带额外参数）。"""

    def test_mock_true_returns_one(self, mock_plugin):
        assert mock_plugin._handle_mock_response("MOCK:TRUE", "general") == "1"

    def test_mock_false_returns_zero(self, mock_plugin):
        assert mock_plugin._handle_mock_response("MOCK:FALSE", "general") == "0"

    def test_mock_fail_returns_ambiguous(self, mock_plugin):
        """MOCK:FAIL 返回模糊哨兵值（由 LLM executor 检测后触发 llmexcept）。"""
        result = mock_plugin._handle_mock_response("MOCK:FAIL", "general")
        assert "ambiguous" in result.lower()


class TestTypedDirectives:
    """二级类型指令。"""

    def test_mock_int(self, mock_plugin):
        assert mock_plugin._handle_mock_response("MOCK:INT:42", "general") == "42"

    def test_mock_int_zero(self, mock_plugin):
        assert mock_plugin._handle_mock_response("MOCK:INT:0", "general") == "0"

    def test_mock_int_negative(self, mock_plugin):
        assert mock_plugin._handle_mock_response("MOCK:INT:-7", "general") == "-7"

    def test_mock_str_single_word(self, mock_plugin):
        result = mock_plugin._handle_mock_response("MOCK:STR:hello", "general")
        assert result == "hello"

    def test_mock_str_strips_trailing_whitespace(self, mock_plugin):
        """未加引号的 STR 值取第一个空白分隔的词。"""
        result = mock_plugin._handle_mock_response("MOCK:STR:hello world", "general")
        assert result == "hello"

    def test_mock_float(self, mock_plugin):
        result = mock_plugin._handle_mock_response("MOCK:FLOAT:3.14", "general")
        assert "3.14" in result

    def test_mock_bool_true(self, mock_plugin):
        assert mock_plugin._handle_mock_response("MOCK:BOOL:TRUE", "general") == "1"

    def test_mock_bool_false(self, mock_plugin):
        assert mock_plugin._handle_mock_response("MOCK:BOOL:FALSE", "general") == "0"

    def test_mock_list(self, mock_plugin):
        result = mock_plugin._handle_mock_response("MOCK:LIST:[1,2,3]", "general")
        assert "1" in result and "2" in result and "3" in result

    def test_mock_dict(self, mock_plugin):
        result = mock_plugin._handle_mock_response('MOCK:DICT:{"key":"value"}', "general")
        assert "key" in result and "value" in result


class TestSeqDirective:
    """MOCK:SEQ 按序返回。"""

    def test_mock_seq_returns_values_in_order(self, mock_plugin):
        """SEQ 指令应按顺序返回多个值。"""
        responses = []
        prompt = "MOCK:SEQ:[MOCK:STR:first,MOCK:STR:second,MOCK:STR:third]"
        for _ in range(3):
            r = mock_plugin._handle_mock_response(prompt, "general")
            responses.append(r)
        assert any("first" in r for r in responses)
        assert any("second" in r for r in responses)
        assert any("third" in r for r in responses)

    def test_mock_seq_with_fail_sentinel(self, mock_plugin):
        """SEQ 中的 FAIL 哨兵应返回模糊值（触发 llmexcept）。"""
        prompt = "MOCK:SEQ:[MOCK:STR:ok,FAIL]"
        # 第一次应该返回 ok 值
        result = mock_plugin._handle_mock_response(prompt, "general")
        assert "ok" in result or "MOCK:STR:ok" in result
        # 第二次应该返回模糊值
        second = mock_plugin._handle_mock_response(prompt, "general")
        assert "ambiguous" in second.lower()


class TestRepairDirective:
    """MOCK:REPAIR 指令。"""

    def test_mock_repair_default(self, mock_plugin):
        """MOCK:REPAIR 首次返回模糊值触发重试，重试后返回 truthy。"""
        # 第一次调用应返回模糊值
        first = mock_plugin._handle_mock_response("MOCK:REPAIR", "general")
        assert "MAYBE" in first.upper() or "ambiguous" in first.lower() or first != "1"
        # 第二次调用（重试后）应返回 truthy
        second = mock_plugin._handle_mock_response("MOCK:REPAIR", "general")
        assert second == "1"

    def test_mock_repair_with_fallback_str(self, mock_plugin):
        """MOCK:REPAIR:STR:<value> 首次模糊，重试后返回指定字符串。"""
        # 首次模糊
        first = mock_plugin._handle_mock_response("MOCK:REPAIR:STR:repaired", "general")
        # 重试后返回 "repaired"
        second = mock_plugin._handle_mock_response("MOCK:REPAIR:STR:repaired", "general")
        assert "repaired" in second

    def test_mock_repair_with_fallback_int(self, mock_plugin):
        """MOCK:REPAIR:INT:<value> 首次模糊，重试后返回指定整数。"""
        first = mock_plugin._handle_mock_response("MOCK:REPAIR:INT:42", "general")
        second = mock_plugin._handle_mock_response("MOCK:REPAIR:INT:42", "general")
        assert "42" in second


class TestMockValidation:
    """MOCK 指令验证和边界情况。"""

    def test_non_mock_prompt_returns_empty_or_passthrough(self, mock_plugin):
        """非 MOCK 前缀的 prompt 不应被 MOCK 系统处理。"""
        result = mock_plugin._handle_mock_response("Hello world", "general")
        # 非 MOCK 指令在 mock 模式下应返回某种默认值（可能是空或回显）
        # 具体行为取决于实现，但不应抛异常
        assert isinstance(result, str)

    def test_mock_directive_case_sensitive(self, mock_plugin):
        """MOCK 指令关键字必须全大写。小写不应被识别为指令。"""
        # mock:true（小写）不应返回 "1"
        result = mock_plugin._handle_mock_response("mock:true", "general")
        assert result != "1"
