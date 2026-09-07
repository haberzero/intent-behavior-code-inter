"""
tests/e2e/test_error_object_rendering.py

语言级异常值对象的字符串化渲染契约：
- ``str(e)``（类调用 __call__ 的 __to_prompt__ 通道）渲染
  ``<类型名>: <message>``——非默认 fallback ``<Instance of T>``（后者丢失
  类型之外的全部信息）；
- ``int(e)`` 等无法转换的 cast_to 目标 → fail-fast 报错（非静默返回自身
  ——异常对象不是 int，静默回落 = 类型谎言）。
"""
import os

import pytest

from core.engine import IBCIEngine
from core.kernel.issue import InterpreterError


@pytest.fixture
def engine():
    return IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)))


class TestErrorObjectRendering:
    def test_str_of_llmparseerror_renders_message(self, engine):
        src = (
            "import ai\n"
            "ai.load_project_config()\n"
            "ai.set_mock_mode()\n"
            "try:\n"
            "    str r = @~ MOCK:FAIL bad ~\n"
            '    print("unexpected=" + r)\n'
            "except LLMParseError as e:\n"
            '    print("R=" + str(e))\n'
            "print(\"DONE\")\n"
        )
        out = []
        engine.run_string(src, output_callback=lambda s: out.append(s))
        rendered = next(l for l in out if l.startswith("R="))
        # 结构化渲染：类型名前缀 + message（非 <Instance of ...>）
        assert "LLMParseError:" in rendered
        assert "<Instance of" not in rendered
        assert "MOCK:FAIL" in rendered  # message 字段可见

    def test_str_of_base_exception_renders_message(self, engine):
        src = (
            "import ai\n"
            "ai.load_project_config()\n"
            "ai.set_mock_mode()\n"
            "try:\n"
            "    str r = @~ MOCK:FAIL bad ~\n"
            '    print("unexpected=" + r)\n'
            "except Exception as e:\n"
            '    print("R=" + str(e))\n'
            "print(\"DONE\")\n"
        )
        out = []
        engine.run_string(src, output_callback=lambda s: out.append(s))
        rendered = next(l for l in out if l.startswith("R="))
        assert "LLMParseError:" in rendered  # 基类捕获仍按实际类型名渲染
        assert "<Instance of" not in rendered

    def test_int_cast_of_exception_fails_fast(self, engine):
        # int(e) 无法转换 → 显式 RUN_TYPE_MISMATCH（原静默返回异常自身）
        src = (
            "import ai\n"
            "ai.load_project_config()\n"
            "ai.set_mock_mode()\n"
            "try:\n"
            "    str r = @~ MOCK:FAIL bad ~\n"
            '    print("unexpected=" + r)\n'
            "except LLMParseError as e:\n"
            "    int n = int(e)\n"
            '    print("n=" + (str)n)\n'
            "print(\"DONE\")\n"
        )
        with pytest.raises(InterpreterError) as exc:
            engine.run_string(src)
        assert exc.value.error_code == "RUN_TYPE_MISMATCH"
        assert "Cannot cast" in exc.value.message

    def test_str_cast_of_exception_returns_message(self, engine):
        # str(e) 的语义 = 字符串化（经 __to_prompt__ 通道，非 cast_to）；
        # cast_to(str) 路径（如 (str)e 强转）返回 message 字段（既有契约）
        src = (
            "import ai\n"
            "ai.load_project_config()\n"
            "ai.set_mock_mode()\n"
            "try:\n"
            "    str r = @~ MOCK:FAIL bad ~\n"
            '    print("unexpected=" + r)\n'
            "except LLMParseError as e:\n"
            '    print("R=" + (str)e)\n'
            "print(\"DONE\")\n"
        )
        out = []
        engine.run_string(src, output_callback=lambda s: out.append(s))
        rendered = next(l for l in out if l.startswith("R="))
        assert "MOCK:FAIL" in rendered
