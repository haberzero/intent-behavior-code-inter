"""
tests/runtime/test_plugin_implementations.py

Smoke tests for plugin implementations (pure Python, no IBCI engine needed).

Testing strategy: Each plugin gets 3-5 smoke tests to verify basic functionality.
We do NOT exhaustively test Python stdlib functions (math.sqrt, json.dumps, etc).

Coverage:
  - ibci_math: basic operations (smoke test)
  - ibci_json: parse/stringify (smoke test)
  - ibci_time: now/format (smoke test)
  - ibci_schema: validate (smoke test)
  - ibci_net: configuration (smoke test)
"""

import pytest
import time
import json


# ---------------------------------------------------------------------------
# 1. ibci_math (smoke tests)
# ---------------------------------------------------------------------------

class TestMathPlugin:
    @pytest.fixture
    def math_lib(self):
        from ibci_modules.ibci_math.core import MathLib
        return MathLib()

    def test_sqrt_basic(self, math_lib):
        """Smoke test: basic math function works"""
        assert math_lib.sqrt(16.0) == 4.0

    def test_trig_functions(self, math_lib):
        """Smoke test: trigonometric functions accessible"""
        import math
        assert abs(math_lib.sin(math.pi / 2) - 1.0) < 0.0001
        assert abs(math_lib.cos(0.0) - 1.0) < 0.0001

    def test_constants_available(self, math_lib):
        """Smoke test: math constants accessible"""
        import math
        assert math_lib.pi == math.pi
        assert math_lib.e == math.e

    def test_random_in_range(self, math_lib):
        """Smoke test: random number generation works"""
        val = math_lib.random()
        assert 0.0 <= val < 1.0


# ---------------------------------------------------------------------------
# 2. ibci_json (smoke tests)
# ---------------------------------------------------------------------------

class TestJsonPlugin:
    @pytest.fixture
    def json_lib(self):
        from ibci_modules.ibci_json.core import JSONLib
        return JSONLib()

    def test_parse_and_stringify_roundtrip(self, json_lib):
        """Smoke test: parse and stringify work"""
        original = {"key": "value", "number": 42}
        json_str = json_lib.stringify(original)
        parsed = json_lib.parse(json_str)
        assert parsed == original

    def test_merge_objects(self, json_lib):
        """Smoke test: merge combines objects"""
        result = json_lib.merge({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_get_nested_path(self, json_lib):
        """Smoke test: nested path access works"""
        data = {"a": {"b": {"c": 42}}}
        assert json_lib.get_nested(data, "a.b.c") == 42

    def test_keys_values(self, json_lib):
        """Smoke test: keys/values extraction works"""
        data = {"x": 10, "y": 20}
        assert set(json_lib.keys(data)) == {"x", "y"}
        assert set(json_lib.values(data)) == {10, 20}


# ---------------------------------------------------------------------------
# 3. ibci_time (smoke tests)
# ---------------------------------------------------------------------------

class TestTimePlugin:
    @pytest.fixture
    def time_lib(self):
        from ibci_modules.ibci_time.core import TimeLib
        return TimeLib()

    def test_now_returns_timestamp(self, time_lib):
        """Smoke test: now() returns valid timestamp"""
        ts = time_lib.now()
        assert isinstance(ts, float)
        assert ts > 1600000000  # After 2020

    def test_format_timestamp(self, time_lib):
        """Smoke test: format() produces readable string"""
        ts = time.time()
        formatted = time_lib.format(ts, "%Y-%m-%d")
        assert len(formatted) == 10  # YYYY-MM-DD

    def test_date_str_format(self, time_lib):
        """Smoke test: date_str() returns YYYY-MM-DD"""
        result = time_lib.date_str(time.time())
        assert len(result) == 10
        assert result[4] == "-"
        assert result[7] == "-"

    def test_add_seconds(self, time_lib):
        """Smoke test: add_seconds() modifies timestamp correctly"""
        ts = time.time()
        new_ts = time_lib.add_seconds(ts, 3600)
        assert abs(new_ts - ts - 3600) < 0.01


# ---------------------------------------------------------------------------
# 4. ibci_schema (smoke tests)
# ---------------------------------------------------------------------------

class TestSchemaPlugin:
    @pytest.fixture
    def schema_lib(self):
        from ibci_modules.ibci_schema.core import SchemaLib
        return SchemaLib()

    def test_validate_success(self, schema_lib):
        """Smoke test: validate() accepts valid data"""
        schema = {"type": "str", "required": True}
        result = schema_lib.validate("hello", schema)
        assert result is True

    def test_validate_failure(self, schema_lib):
        """Smoke test: validate() rejects invalid data"""
        schema = {"type": "int", "required": True}
        result = schema_lib.validate("not an int", schema)
        assert result is False

    def test_required_fields(self, schema_lib):
        """Smoke test: required_fields() extracts field names"""
        schema = {
            "fields": {
                "name": {"type": "str", "required": True},
                "age": {"type": "int", "required": False}
            }
        }
        result = schema_lib.required_fields(schema)
        assert "name" in result
        assert "age" not in result


# ---------------------------------------------------------------------------
# 5. ibci_net (smoke tests)
# ---------------------------------------------------------------------------

class TestNetPlugin:
    @pytest.fixture
    def net_lib(self):
        from ibci_modules.ibci_net.core import NetLib
        return NetLib()

    def test_set_and_get_base_url(self, net_lib):
        """Smoke test: set_base_url() and get_base_url() work"""
        net_lib.set_base_url("https://api.example.com")
        assert net_lib.get_base_url() == "https://api.example.com"

    def test_set_and_get_timeout(self, net_lib):
        """Smoke test: set_timeout() and get_timeout() work"""
        net_lib.set_timeout(30)
        assert net_lib.get_timeout() == 30

    def test_set_header(self, net_lib):
        """Smoke test: set_header() stores headers"""
        net_lib.set_header("Authorization", "Bearer token")
        headers = net_lib.get_headers()
        assert headers.get("Authorization") == "Bearer token"
