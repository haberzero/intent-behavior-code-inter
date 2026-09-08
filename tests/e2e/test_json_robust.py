"""
tests/e2e/test_json_robust.py

json 模块鲁棒面（round3 R3-⑨ D-10）：

- parse 返回实际值（对象→dict / 数组→list / 原始值→标量；无包装键）；
- malformed parse = 可捕获异常（RUN_JSON_PARSE_ERROR，fail-fast，无 print
  副作用、不静默空值）；
- parse_or_none = 显式宽松形态（malformed = None，无副作用）；
- stringify/pretty 失败 = 异常（无 print、无 "{}" 静默回退）。
"""
import pytest

from tests.conftest import run_ibci, compile_ibci


class TestParseActualValue:
    def test_object_to_dict(self):
        out = run_ibci('import json\ndict d = json.parse(\'{"a": 1}\')\nprint(d["a"])\n')
        assert out == ["1"]

    def test_array_to_list(self):
        # 数组直 parse（无 _list 包装）
        out = run_ibci('import json\nlist l = json.parse("[1,2,3]")\nprint(l[0])\nprint(len(l))\n')
        assert out == ["1", "3"]

    def test_scalar_to_int(self):
        out = run_ibci('import json\nint n = json.parse("42")\nprint(n)\n')
        assert out == ["42"]

    def test_scalar_to_str(self):
        out = run_ibci('import json\nstr s = json.parse(\'"hello"\')\nprint(s)\n')
        assert out == ["hello"]

    def test_null_to_none(self):
        out = run_ibci('import json\nany x = json.parse("null")\nif x == None:\n    print("none")\n')
        assert out == ["none"]


class TestParseFailFast:
    def test_malformed_raises_catchable(self):
        # malformed = 可捕获异常（RUN_JSON_PARSE_ERROR），无 print 副作用
        out = run_ibci(
            'import json\n'
            'try:\n'
            '    any x = json.parse("{bad")\n'
            'except Exception:\n'
            '    print("caught")\n'
            'print("alive")\n'
        )
        assert out == ["caught", "alive"]

    def test_malformed_uncaught_terminates(self):
        # 未捕获 = run 终止（fail-fast，非静默空值）
        with pytest.raises(Exception) as ei:
            run_ibci('import json\nany x = json.parse("{bad")\nprint(x)\n')
        assert "RUN_JSON_PARSE_ERROR" in str(ei.value)

    def test_parse_error_code_surfaces(self):
        from core.engine import IBCIEngine
        from tests.conftest import TESTS_ROOT
        try:
            IBCIEngine(root_dir=TESTS_ROOT).run_string(
                'import json\nany x = json.parse("{bad")\n', silent=True)
            pytest.fail("应运行期失败")
        except Exception as e:
            assert getattr(e, "error_code", None) == "RUN_JSON_PARSE_ERROR", str(e)


class TestParseOrNone:
    def test_malformed_returns_none(self):
        out = run_ibci(
            'import json\n'
            'any x = json.parse_or_none("{bad")\n'
            'if x == None:\n'
            '    print("none")\n'
        )
        assert out == ["none"]

    def test_valid_returns_value(self):
        out = run_ibci('import json\nint x = json.parse_or_none("7")\nprint(x)\n')
        assert out == ["7"]

    def test_no_side_effects(self):
        # 无 print 副作用（输出恰为数据行）
        out = run_ibci(
            'import json\n'
            'any a = json.parse_or_none("{bad")\n'
            'any b = json.parse_or_none("[1]")\n'
            'print("done")\n'
        )
        assert out == ["done"]


class TestStringifyFailFast:
    def test_stringify_normal(self):
        out = run_ibci('import json\nstr s = json.stringify({"a": 1})\nprint(s)\n')
        assert out == ['{"a": 1}']

    def test_stringify_circular_raises(self):
        # 循环引用 = 异常（无 "{}" 静默回退）
        with pytest.raises(Exception):
            run_ibci(
                'import json\n'
                'list l = [1]\n'
                'l.append(l)\n'
                'str s = json.stringify(l)\n'
                'print(s)\n'
            )
