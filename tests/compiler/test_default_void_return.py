"""
tests/compiler/test_default_void_return.py

A4 缺省 void（返回类型标注可选）判别测试：

- 函数无返回类型标注 = 缺省 void（副作用函数声明简化——消 `-> void`
  样板；与 `-> void` 同语义）；
- void 缺省函数体内 return 值丢弃（与 `-> void` 一致）；
- void 缺省函数返回值不可赋给非 void 变量（SEM_TYPE_MISMATCH——
  void 语义正确）；
- 显式标注（`-> void` / `-> auto` / `-> TYPE` / `-> any`）行为不变；
- lambda 保持显式标注要求（值表达式语义——A4 仅声明函数）。
"""

import pytest

from core.engine import IBCIEngine
from core.kernel.issue import CompilerError


@pytest.fixture
def engine():
    return IBCIEngine(root_dir=".")


class TestDefaultVoid:
    def test_unannotated_function_runs(self, engine):
        """无标注函数 = void 缺省：定义 + 调用 + 副作用正常。"""
        out = []
        engine.run_string(
            "func f():\n"
            '    print("hi")\n'
            "f()\n"
            'print("done")\n',
            output_callback=out.append, silent=True)
        assert out and out[0].strip() == "hi" and out[1].strip() == "done"

    def test_unannotated_return_value_discarded(self, engine):
        """void 缺省函数体内 return 值丢弃（与 `-> void` 同语义）。"""
        out = []
        engine.run_string(
            "func g(int x):\n"
            "    return x\n"
            "g(1)\n"
            'print("discarded-ok")\n',
            output_callback=out.append, silent=True)
        assert out and "discarded-ok" in out[0]

    def test_void_value_not_assignable(self, engine):
        """void 缺省函数返回值不可赋给非 void 变量（void 语义正确）。"""
        with pytest.raises(CompilerError) as exc:
            engine.compile_string(
                "func h(int x):\n"
                "    return x\n"
                "int v = h(1)\n",
                silent=True)
        assert any(d.code == "SEM_TYPE_MISMATCH" for d in exc.value.diagnostics)


class TestExplicitAnnotationsUnchanged:
    def test_explicit_void(self, engine):
        out = []
        engine.run_string(
            "func f() -> void:\n"
            '    print("v")\n'
            "f()\n",
            output_callback=out.append, silent=True)
        assert out and out[0].strip() == "v"

    def test_explicit_auto(self, engine):
        out = []
        engine.run_string(
            "func f() -> auto:\n"
            "    return 42\n"
            "int v = f()\n"
            'print("v=" + (str)v)\n',
            output_callback=out.append, silent=True)
        assert out and "v=42" in out[0]

    def test_explicit_type(self, engine):
        out = []
        engine.run_string(
            "func f() -> int:\n"
            "    return 7\n"
            "int v = f()\n"
            'print("v=" + (str)v)\n',
            output_callback=out.append, silent=True)
        assert out and "v=7" in out[0]

    def test_explicit_any(self, engine):
        out = []
        engine.run_string(
            "func f() -> any:\n"
            '    return "any-val"\n'
            "any v = f()\n"
            'print("v=" + (str)v)\n',
            output_callback=out.append, silent=True)
        assert out and "v=any-val" in out[0]


class TestLambdaRequiresExplicit:
    def test_lambda_unannotated_still_errors(self, engine):
        """lambda 保持显式标注要求（值表达式语义——A4 仅声明函数）。"""
        with pytest.raises(CompilerError) as exc:
            engine.compile_string(
                "fn f = lambda(int x): x + 1\n"
                "int v = f(1)\n",
                silent=True)
        assert any(
            d.code == "SEM_MISSING_RETURN_ANNOTATION" for d in exc.value.diagnostics
        )
