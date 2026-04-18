"""
tests/runtime/test_plugin_implementations.py

Unit tests for non-invasive plugin implementations (pure Python, no IBCI engine needed).

Coverage:
  - ibci_math: all math operations
  - ibci_json: parse, stringify, merge, get_nested, set_nested, keys, values, pretty
  - ibci_time: now, format, parse, date_str, datetime_str, add_seconds, diff_seconds
  - ibci_schema: validate, required_fields, infer, coerce
  - ibci_net: configuration methods (no actual HTTP in tests)
"""

import pytest
import time
import json


# ---------------------------------------------------------------------------
# 1. ibci_math
# ---------------------------------------------------------------------------

class TestMathPlugin:
    @pytest.fixture
    def math_lib(self):
        from ibci_modules.ibci_math.core import MathLib
        return MathLib()

    def test_sqrt(self, math_lib):
        assert math_lib.sqrt(16.0) == 4.0

    def test_pow(self, math_lib):
        assert math_lib.pow(2.0, 10.0) == 1024.0

    def test_abs(self, math_lib):
        assert math_lib.abs(-5.0) == 5.0

    def test_floor(self, math_lib):
        assert math_lib.floor(3.7) == 3

    def test_ceil(self, math_lib):
        assert math_lib.ceil(3.2) == 4

    def test_round(self, math_lib):
        assert math_lib.round(3.14159, 2) == 3.14

    def test_clamp(self, math_lib):
        assert math_lib.clamp(15.0, 0.0, 10.0) == 10.0
        assert math_lib.clamp(-5.0, 0.0, 10.0) == 0.0
        assert math_lib.clamp(5.0, 0.0, 10.0) == 5.0

    def test_min(self, math_lib):
        assert math_lib.min(3.0, 7.0) == 3.0

    def test_max(self, math_lib):
        assert math_lib.max(3.0, 7.0) == 7.0

    def test_exp(self, math_lib):
        result = math_lib.exp(1.0)
        assert abs(result - 2.71828) < 0.001

    def test_log(self, math_lib):
        result = math_lib.log(2.71828)
        assert abs(result - 1.0) < 0.001

    def test_sin_cos(self, math_lib):
        import math
        assert abs(math_lib.sin(math.pi / 2) - 1.0) < 0.0001
        assert abs(math_lib.cos(0.0) - 1.0) < 0.0001

    def test_pi_e_inf_constants(self, math_lib):
        import math
        assert math_lib.pi == math.pi
        assert math_lib.e == math.e
        assert math_lib.inf == math.inf

    def test_random_range(self, math_lib):
        val = math_lib.random()
        assert 0.0 <= val < 1.0

    def test_randint(self, math_lib):
        val = math_lib.randint(1, 10)
        assert 1 <= val <= 10

    def test_degrees_radians(self, math_lib):
        import math
        assert abs(math_lib.degrees(math.pi) - 180.0) < 0.001
        assert abs(math_lib.radians(180.0) - math.pi) < 0.001


# ---------------------------------------------------------------------------
# 2. ibci_json
# ---------------------------------------------------------------------------

class TestJsonPlugin:
    @pytest.fixture
    def json_lib(self):
        from ibci_modules.ibci_json.core import JSONLib
        return JSONLib()

    def test_parse_object(self, json_lib):
        result = json_lib.parse('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_array(self, json_lib):
        result = json_lib.parse('[1, 2, 3]')
        assert "_list" in result
        assert result["_list"] == [1, 2, 3]

    def test_parse_invalid(self, json_lib):
        result = json_lib.parse("not json")
        assert result == {}

    def test_stringify(self, json_lib):
        result = json_lib.stringify({"key": "value"})
        parsed = json.loads(result)
        assert parsed == {"key": "value"}

    def test_merge(self, json_lib):
        result = json_lib.merge({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_merge_override(self, json_lib):
        result = json_lib.merge({"a": 1}, {"a": 2})
        assert result == {"a": 2}

    def test_keys(self, json_lib):
        result = json_lib.keys({"a": 1, "b": 2})
        assert set(result) == {"a", "b"}

    def test_values(self, json_lib):
        result = json_lib.values({"a": 1, "b": 2})
        assert sorted(result) == [1, 2]

    def test_get_nested(self, json_lib):
        data = {"a": {"b": {"c": 42}}}
        assert json_lib.get_nested(data, "a.b.c") == 42

    def test_get_nested_missing(self, json_lib):
        data = {"a": 1}
        assert json_lib.get_nested(data, "a.b.c") is None

    def test_set_nested(self, json_lib):
        data = {"a": {"b": 1}}
        result = json_lib.set_nested(data, "a.b", 42)
        assert result["a"]["b"] == 42

    def test_pretty(self, json_lib):
        result = json_lib.pretty({"key": "value"})
        assert isinstance(result, str)
        assert "key" in result
        # Should contain indentation
        assert "\n" in result


# ---------------------------------------------------------------------------
# 3. ibci_time
# ---------------------------------------------------------------------------

class TestTimePlugin:
    @pytest.fixture
    def time_lib(self):
        from ibci_modules.ibci_time.core import TimeLib
        return TimeLib()

    def test_now_is_float(self, time_lib):
        result = time_lib.now()
        assert isinstance(result, float)
        assert result > 0

    def test_now_ms_is_int(self, time_lib):
        result = time_lib.now_ms()
        assert isinstance(result, int)
        assert result > 0

    def test_utcnow_is_string(self, time_lib):
        result = time_lib.utcnow()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_localtime_is_string(self, time_lib):
        result = time_lib.localtime()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_date_str(self, time_lib):
        ts = time_lib.now()
        result = time_lib.date_str(ts)
        assert isinstance(result, str)
        # Should contain date separators
        assert "-" in result

    def test_datetime_str(self, time_lib):
        ts = time_lib.now()
        result = time_lib.datetime_str(ts)
        assert isinstance(result, str)

    def test_add_seconds(self, time_lib):
        ts = 1000.0
        result = time_lib.add_seconds(ts, 60.0)
        assert result == 1060.0

    def test_diff_seconds(self, time_lib):
        result = time_lib.diff_seconds(1060.0, 1000.0)
        assert result == 60.0

    def test_add_days(self, time_lib):
        ts = 0.0
        result = time_lib.add_days(ts, 1.0)
        assert result == 86400.0

    def test_diff_days(self, time_lib):
        result = time_lib.diff_days(86400.0, 0.0)
        assert abs(result - 1.0) < 0.001


# ---------------------------------------------------------------------------
# 4. ibci_schema
# ---------------------------------------------------------------------------

class TestSchemaPlugin:
    @pytest.fixture
    def schema_lib(self):
        from ibci_modules.ibci_schema.core import SchemaLib
        return SchemaLib()

    def test_validate_passes(self, schema_lib):
        data = {"name": "Alice", "age": 30}
        rules = {
            "required": ["name", "age"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            }
        }
        assert schema_lib.validate(data, rules) is True

    def test_validate_fails_wrong_type(self, schema_lib):
        data = {"name": "Alice", "age": "thirty"}
        rules = {
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            }
        }
        assert schema_lib.validate(data, rules) is False

    def test_validate_fails_missing_required(self, schema_lib):
        data = {"name": "Alice"}
        rules = {
            "required": ["name", "age"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            }
        }
        assert schema_lib.validate(data, rules) is False

    def test_required_fields(self, schema_lib):
        rules = {"required": ["name", "age"], "properties": {}}
        result = schema_lib.required_fields(rules)
        assert isinstance(result, list)
        assert set(result) == {"name", "age"}

    def test_infer_types(self, schema_lib):
        data = {"name": "Alice", "age": 30, "active": True}
        result = schema_lib.infer(data)
        assert isinstance(result, dict)
        # infer returns JSON Schema style: {"required": [...], "properties": {...}}
        assert "properties" in result
        assert result["properties"]["name"]["type"] == "string"
        assert result["properties"]["age"]["type"] == "integer"
        assert result["properties"]["active"]["type"] == "boolean"

    def test_coerce(self, schema_lib):
        data = {"age": "30", "score": "3.14"}
        rules = {
            "properties": {
                "age": {"type": "int"},
                "score": {"type": "float"},
            }
        }
        result = schema_lib.coerce(data, rules)
        assert result["age"] == 30
        assert abs(result["score"] - 3.14) < 0.001


# ---------------------------------------------------------------------------
# 5. ibci_net (configuration only, no real HTTP)
# ---------------------------------------------------------------------------

class TestNetPlugin:
    @pytest.fixture
    def net_lib(self):
        from ibci_modules.ibci_net.core import NetLib
        return NetLib()

    def test_default_timeout(self, net_lib):
        assert net_lib._timeout == 10.0

    def test_set_timeout(self, net_lib):
        net_lib.set_timeout(30.0)
        assert net_lib._timeout == 30.0

    def test_set_timeout_minimum(self, net_lib):
        net_lib.set_timeout(0.0)
        assert net_lib._timeout == 0.1

    def test_set_default_headers(self, net_lib):
        net_lib.set_default_headers({"X-Custom": "value"})
        assert net_lib._default_headers == {"X-Custom": "value"}

    def test_set_bearer_token(self, net_lib):
        net_lib.set_bearer_token("my_token")
        assert net_lib._default_headers["Authorization"] == "Bearer my_token"

    def test_set_basic_auth(self, net_lib):
        net_lib.set_basic_auth("user", "pass")
        assert "Authorization" in net_lib._default_headers
        assert "Basic" in net_lib._default_headers["Authorization"]


# ---------------------------------------------------------------------------
# 6. ibci_ai mock system
# ---------------------------------------------------------------------------

class TestAIMockSystem:
    @pytest.fixture
    def ai_plugin(self):
        from ibci_modules.ibci_ai.core import AIPlugin
        p = AIPlugin()
        p.set_config("TESTONLY", "TESTONLY", "TESTONLY")
        return p

    def test_mock_true(self, ai_plugin):
        result = ai_plugin._handle_mock_response("MOCK:TRUE test", "expr")
        assert result == "1"

    def test_mock_false(self, ai_plugin):
        result = ai_plugin._handle_mock_response("MOCK:FALSE test", "expr")
        assert result == "0"

    def test_mock_fail(self, ai_plugin):
        result = ai_plugin._handle_mock_response("MOCK:FAIL test", "expr")
        assert "ambiguous" in result.lower() or "maybe" in result.lower()

    def test_mock_repair_first_fails(self, ai_plugin):
        result = ai_plugin._handle_mock_response("MOCK:REPAIR test_key", "expr")
        assert result == "__MOCK_REPAIR__"

    def test_mock_repair_second_succeeds(self, ai_plugin):
        ai_plugin._handle_mock_response("MOCK:REPAIR test_key2", "expr")
        result = ai_plugin._handle_mock_response("MOCK:REPAIR test_key2", "expr")
        assert result == "1"

    def test_mock_direct_list(self, ai_plugin):
        result = ai_plugin._handle_mock_response('MOCK:["a","b"]', "expr")
        assert result == '["a","b"]'

    def test_mock_direct_dict(self, ai_plugin):
        result = ai_plugin._handle_mock_response('MOCK:{"key":"val"}', "expr")
        assert result == '{"key":"val"}'

    def test_mock_int_type(self, ai_plugin):
        result = ai_plugin._handle_mock_response("MOCK:INT:42", "expr")
        assert result == "42"

    def test_mock_float_type(self, ai_plugin):
        result = ai_plugin._handle_mock_response("MOCK:FLOAT:3.14", "expr")
        assert result == "3.14"

    def test_mock_bool_true_type(self, ai_plugin):
        result = ai_plugin._handle_mock_response("MOCK:BOOL:TRUE", "expr")
        assert result == "1"

    def test_mock_bool_false_type(self, ai_plugin):
        result = ai_plugin._handle_mock_response("MOCK:BOOL:FALSE", "expr")
        assert result == "0"

    def test_mock_str_type(self, ai_plugin):
        result = ai_plugin._handle_mock_response("MOCK:STR:hello", "expr")
        assert result == "hello"

    def test_mock_str_double_quoted_value(self, ai_plugin):
        """MOCK:STR 的二级值若被双引号包裹，应自动剥除引号 (behavior-expression 解析器会重新加引号)"""
        result = ai_plugin._handle_mock_response('MOCK:STR:"hello"', "expr")
        assert result == "hello"

    def test_mock_str_double_quoted_with_spaces(self, ai_plugin):
        result = ai_plugin._handle_mock_response('MOCK:STR:"hello world"', "expr")
        assert result == "hello world"

    def test_mock_str_single_quoted_value(self, ai_plugin):
        result = ai_plugin._handle_mock_response("MOCK:STR:'hi there'", "expr")
        assert result == "hi there"

    def test_mock_list_already_bracketed(self, ai_plugin):
        """MOCK:LIST 的值若已含方括号，不应再次包裹"""
        result = ai_plugin._handle_mock_response('MOCK:LIST:["a","b"]', "expr")
        assert result == '["a","b"]'

    def test_mock_list_plain_value(self, ai_plugin):
        """MOCK:LIST 的值若无方括号，自动包裹"""
        result = ai_plugin._handle_mock_response("MOCK:LIST:a,b,c", "expr")
        assert result == "[a,b,c]"

    def test_mock_dict_already_braced(self, ai_plugin):
        """MOCK:DICT 的值若已含花括号，不应再次包裹"""
        result = ai_plugin._handle_mock_response('MOCK:DICT:{"key":"val"}', "expr")
        assert result == '{"key":"val"}'

    def test_non_mock_branch_returns_one(self, ai_plugin):
        result = ai_plugin._handle_mock_response("some user text", "branch")
        assert result == "1"

    def test_non_mock_expr_returns_mock_prefix(self, ai_plugin):
        result = ai_plugin._handle_mock_response("some user text", "expr")
        assert "[MOCK]" in result

    def test_reset_mock_state(self, ai_plugin):
        ai_plugin._mock_state["key"] = 1
        ai_plugin._mock_retry_counts["key"] = 2
        ai_plugin._mock_seq_counters["_seq_key"] = 3
        ai_plugin.reset_mock_state()
        assert len(ai_plugin._mock_state) == 0
        assert len(ai_plugin._mock_retry_counts) == 0
        assert len(ai_plugin._mock_seq_counters) == 0


# ---------------------------------------------------------------------------
# 7. MOCK:SEQ 序列化回放指令单元测试
# ---------------------------------------------------------------------------

class TestAIMockSEQ:
    """MOCK:SEQ 按调用序列回放值的单元测试。"""

    @pytest.fixture
    def ai_plugin(self):
        from ibci_modules.ibci_ai.core import AIPlugin
        p = AIPlugin()
        p.set_config("TESTONLY", "TESTONLY", "TESTONLY")
        return p

    def test_seq_returns_values_in_order(self, ai_plugin):
        """MOCK:SEQ 按调用顺序逐一返回序列中的值。"""
        assert ai_plugin._handle_mock_response("MOCK:SEQ:a:b:c mykey", "expr") == "a"
        assert ai_plugin._handle_mock_response("MOCK:SEQ:a:b:c mykey", "expr") == "b"
        assert ai_plugin._handle_mock_response("MOCK:SEQ:a:b:c mykey", "expr") == "c"

    def test_seq_repeats_last_value_when_exhausted(self, ai_plugin):
        """序列耗尽后重复最后一个值。"""
        ai_plugin._handle_mock_response("MOCK:SEQ:x:y mykey", "expr")
        ai_plugin._handle_mock_response("MOCK:SEQ:x:y mykey", "expr")
        assert ai_plugin._handle_mock_response("MOCK:SEQ:x:y mykey", "expr") == "y"
        assert ai_plugin._handle_mock_response("MOCK:SEQ:x:y mykey", "expr") == "y"

    def test_seq_fail_returns_ambiguous_sentinel(self, ai_plugin):
        """FAIL 值触发歧义哨兵（驱动 llmexcept）。"""
        result = ai_plugin._handle_mock_response("MOCK:SEQ:FAIL:ok fkey", "expr")
        assert "ambiguous" in result.lower() or "maybe" in result.lower()
        assert ai_plugin._handle_mock_response("MOCK:SEQ:FAIL:ok fkey", "expr") == "ok"

    def test_seq_true_false_aliases(self, ai_plugin):
        """TRUE/FALSE 别名正确解析为 '1'/'0'。"""
        assert ai_plugin._handle_mock_response("MOCK:SEQ:TRUE:FALSE tf_key", "expr") == "1"
        assert ai_plugin._handle_mock_response("MOCK:SEQ:TRUE:FALSE tf_key", "expr") == "0"

    def test_seq_independent_keys(self, ai_plugin):
        """不同 key 的 SEQ 计数器互相独立。"""
        assert ai_plugin._handle_mock_response("MOCK:SEQ:a:b key1", "expr") == "a"
        assert ai_plugin._handle_mock_response("MOCK:SEQ:x:y key2", "expr") == "x"
        assert ai_plugin._handle_mock_response("MOCK:SEQ:a:b key1", "expr") == "b"
        assert ai_plugin._handle_mock_response("MOCK:SEQ:x:y key2", "expr") == "y"

    def test_seq_reset_clears_counter(self, ai_plugin):
        """reset_mock_state() 将 SEQ 计数器清零，使序列从头开始。"""
        ai_plugin._handle_mock_response("MOCK:SEQ:a:b reset_key", "expr")
        ai_plugin.reset_mock_state()
        assert ai_plugin._handle_mock_response("MOCK:SEQ:a:b reset_key", "expr") == "a"

    def test_seq_no_key(self, ai_plugin):
        """无 key 的 SEQ 指令共享同一计数器，可正常使用。"""
        assert ai_plugin._handle_mock_response("MOCK:SEQ:p:q:r", "expr") == "p"
        assert ai_plugin._handle_mock_response("MOCK:SEQ:p:q:r", "expr") == "q"
        assert ai_plugin._handle_mock_response("MOCK:SEQ:p:q:r", "expr") == "r"

    def test_seq_mixed_sentinels_in_sequence(self, ai_plugin):
        """序列中混合普通值与 FAIL/TRUE/FALSE 哨兵。"""
        p = ai_plugin
        r0 = p._handle_mock_response("MOCK:SEQ:ok:FAIL:TRUE:FALSE:done mix_key", "expr")
        assert r0 == "ok"
        r1 = p._handle_mock_response("MOCK:SEQ:ok:FAIL:TRUE:FALSE:done mix_key", "expr")
        assert "ambiguous" in r1.lower() or "maybe" in r1.lower()
        assert p._handle_mock_response("MOCK:SEQ:ok:FAIL:TRUE:FALSE:done mix_key", "expr") == "1"
        assert p._handle_mock_response("MOCK:SEQ:ok:FAIL:TRUE:FALSE:done mix_key", "expr") == "0"
        assert p._handle_mock_response("MOCK:SEQ:ok:FAIL:TRUE:FALSE:done mix_key", "expr") == "done"
