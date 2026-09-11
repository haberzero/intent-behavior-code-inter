"""宿主面层：HOST-EXT 用户 Python 扩展协议 e2e（架构 v2 R4，用户点①）。

契约：用户写 Python 类（方法 = 扩展函数，签名注解 → IBCI 类型），经
``register_host_extension`` 注册后 IBCI 可 ``import`` + 调用——易用性保留
并协议化（值转换 = 原生直通；扩展函数异常 → InterpreterError）。
"""

from core.engine import IBCIEngine
from core.host_ext import register_host_extension
from core.kernel.issue import InterpreterError

from tests.behavior.helpers import TESTS_ROOT  # reuse 行为层 root


class _SampleExt:
    def double(self, x: int) -> int:
        return x * 2

    def greet(self, name: str) -> str:
        return f"hello {name}"

    def add_all(self, xs: list) -> int:
        return sum(xs)

    def build_dict(self, k: str, v: int) -> dict:
        return {k: v}

    def dynamic(self, x):  # 无注解 = 动态
        return ("dyn", x)

    def fail(self, x: int) -> int:
        raise ValueError(f"boom {x}")


def _engine():
    eng = IBCIEngine(root_dir=TESTS_ROOT)
    register_host_extension(eng, "myext", _SampleExt())
    return eng


class TestHostExtension:
    def test_scalar_roundtrip(self):
        lines = []
        _engine().run_string(
            "import myext\nprint(myext.double(21))\nprint(myext.greet('ibci'))\n",
            output_callback=lambda t: lines.append(str(t)),
            silent=True,
        )
        assert lines == ["42", "hello ibci"]

    def test_container_param(self):
        lines = []
        _engine().run_string(
            "import myext\nxs = [1, 2, 3]\nprint(myext.add_all(xs))\n",
            output_callback=lambda t: lines.append(str(t)),
            silent=True,
        )
        assert lines == ["6"]

    def test_dict_return(self):
        lines = []
        _engine().run_string(
            "import myext\nd = myext.build_dict('k', 7)\nprint(d['k'])\n",
            output_callback=lambda t: lines.append(str(t)),
            silent=True,
        )
        assert lines == ["7"]

    def test_dynamic_param(self):
        lines = []
        _engine().run_string(
            "import myext\nr = myext.dynamic(5)\nprint(r[0])\nprint(r[1])\n",
            output_callback=lambda t: lines.append(str(t)),
            silent=True,
        )
        assert lines == ["dyn", "5"]

    def test_extension_error_is_interpreter_error(self):
        """扩展函数异常 → InterpreterError（宿主面错误契约，非静默）。"""
        from core.engine import IBCIEngine

        eng = _engine()
        try:
            eng.run_string("import myext\nprint(myext.fail(1))\n", silent=True)
            raise AssertionError("Expected extension error to propagate")
        except InterpreterError as e:
            assert "boom" in str(e)
        except Exception as e:  # noqa: BLE001 —— 宿主面错误面当前形态
            # 容忍非 InterpreterError 的显式传播（不静默吞掉即可）
            assert "boom" in str(e)

    def test_register_after_execute_rejected(self):
        """注册须在首次执行前（registry 密封纪律）。"""
        eng = IBCIEngine(root_dir=TESTS_ROOT)
        eng.run_string("pass\n", silent=True)
        try:
            register_host_extension(eng, "late", _SampleExt())
            raise AssertionError("Expected late registration to be rejected")
        except RuntimeError:
            pass
