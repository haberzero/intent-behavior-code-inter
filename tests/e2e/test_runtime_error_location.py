"""
tests/e2e/test_runtime_error_location.py

运行期错误的 ibci 源位置契约：VM CPS 首次捕获点（内层帧 = 出错现场）
经 node_to_loc 侧表把位置附着到异常对象（单一权威源补位），诊断码
由 throw 点携带（值层/幽灵码）。

动态值（any）经编译期检查放行（is_dynamic 惯例），其类型不匹配在运行期
裁决——本文件用 any 形态锁定"运行期错误 + 位置 + 码"语义（编译期静态
检查的边界 = 动态值放行，见 test_semantic_type_checking.py）。
"""
import os

import pytest

from core.engine import IBCIEngine
from core.kernel.issue import InterpreterError


@pytest.fixture
def engine():
    return IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)))


class TestRuntimeErrorLocation:
    def test_dynamic_compare_type_mismatch_carries_source_line_column(self, engine):
        # 行 2 的 `s >= 0`：s 静态为 any（编译期放行），运行期 str 比较类型
        # 不匹配 → 现场 = 比较表达式位置
        with pytest.raises(InterpreterError) as exc:
            engine.run_string('any s = "a"\nany c = s >= 0\n')
        loc = exc.value.location
        assert loc is not None, "运行期错误应携带 ibci 源位置（翻译点补位）"
        assert loc.line == 2
        assert loc.column == 9  # 's' 起始列（第 2 行 any c = s >= 0 的比较起点）

    def test_dynamic_compare_type_mismatch_code_not_generic(self, engine):
        with pytest.raises(InterpreterError) as exc:
            engine.run_string('any s = "x"\nany c = s >= 1\n')
        assert exc.value.error_code == "RUN_TYPE_MISMATCH"

    def test_str_mul_type_mismatch_code(self, engine):
        # any 放行 → 运行期 str * str 重复类型错误
        with pytest.raises(InterpreterError) as exc:
            engine.run_string('any x = "x"\nany a = x * x\n')
        assert exc.value.error_code == "RUN_TYPE_MISMATCH"

    def test_native_function_type_error_code(self, engine):
        # any 放行 → 运行期 native 函数路径（int.__lt__ 跨型）：
        # 幽灵码表 TypeError → RUN_TYPE_MISMATCH
        with pytest.raises(InterpreterError) as exc:
            engine.run_string('any x = 5\nany a = x < "str"\n')
        assert exc.value.error_code == "RUN_TYPE_MISMATCH"

    def test_location_points_to_innermost_frame(self, engine):
        # 错误发生在第 4 行语句：现场 = 该行（any 接收绕过编译期检查，
        # 运行期 int + str 失败）
        src = (
            "str a = \"one\"\n"
            "str b = \"two\"\n"
            "str c = \"three\"\n"
            "any x = 1\n"
            "any m = x + \"x\"\n"
        )
        with pytest.raises(InterpreterError) as exc:
            engine.run_string(src)
        loc = exc.value.location
        assert loc is not None
        assert loc.line == 5

    def test_function_body_error_not_at_def_line(self, engine):
        # 错误发生在函数体第 2 行：现场 = 函数体语句位置（非函数定义行 1）
        src = (
            "func f() -> any:\n"
            "    any x = 1\n"
            '    return x + "x"\n'
            "any n = f()\n"
            "print(\"done\")\n"
        )
        with pytest.raises(InterpreterError) as exc:
            engine.run_string(src)
        loc = exc.value.location
        assert loc is not None
        assert loc.line == 3

    def test_location_carries_module_file_path(self, engine):
        # file_path = 模块源文件真实路径（node_to_loc 侧表绑定 file_path，
        # 非模块名标识）——CLI 源行渲染的数据前提
        with pytest.raises(InterpreterError) as exc:
            engine.run_string('any s = "x"\nany c = s >= 1\n')
        loc = exc.value.location
        assert loc is not None
        assert loc.file_path
        # run_string 载体为 tempfile 路径——断言其为真实文件路径形态（.ibci 扩展名）
        assert loc.file_path.endswith(".ibci")
