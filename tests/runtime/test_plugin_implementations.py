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
        """Smoke test: validate() accepts valid data (JSON-Schema-subset dict input)."""
        schema = {
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer", "min": 0},
            },
        }
        assert schema_lib.validate({"name": "Alice", "age": 30}, schema) is True

    def test_validate_failure(self, schema_lib):
        """Smoke test: validate() rejects invalid data (type mismatch + missing required)."""
        schema = {
            "required": ["age"],
            "properties": {"age": {"type": "integer"}},
        }
        # Missing required field
        assert schema_lib.validate({"name": "Bob"}, schema) is False
        # Wrong type
        assert schema_lib.validate({"age": "thirty"}, schema) is False

    def test_required_fields(self, schema_lib):
        """Smoke test: required_fields() extracts the JSON-Schema 'required' list."""
        schema = {
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
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

    def test_set_timeout(self, net_lib):
        """Smoke test: set_timeout() updates the internal timeout field."""
        net_lib.set_timeout(30)
        assert net_lib._timeout == 30

    def test_set_default_headers(self, net_lib):
        """Smoke test: set_default_headers() stores headers used in subsequent requests."""
        net_lib.set_default_headers({"X-App": "ibci"})
        merged = net_lib._merge_headers()
        assert merged.get("X-App") == "ibci"

    def test_set_bearer_token_and_clear(self, net_lib):
        """Smoke test: bearer-token auth helper installs Authorization header; clear removes it."""
        net_lib.set_bearer_token("abc123")
        merged = net_lib._merge_headers()
        assert merged.get("Authorization") == "Bearer abc123"
        net_lib.clear_auth()
        merged = net_lib._merge_headers()
        assert "Authorization" not in merged
