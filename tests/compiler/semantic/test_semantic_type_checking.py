"""
tests/compiler/semantic/test_semantic_type_checking.py

编译期运算符类型检查契约（KERNEL_ISSUE-SEM-1 修复面）：

- 排序比较（< <= > >=）逐对静态检查：公理层运算符声明
  （resolve_op → resolve_operation_type_name）= 单一权威源，不可比且双侧
  非动态 → SEM_TYPE_MISMATCH（带 ibci 源行列）；
- 算术二元运算：公理声明失败即 SEM_TYPE_MISMATCH（无兜底推断）；
- 相等/不等（== !=）跨类型放行（运行期返回 False/True，Python 语义）；
- any/auto 动态操作数放行（is_dynamic 惯例——运行期裁决）；
- 防误报：字符串重复（int * str / bool * str / str * int）放行。
"""
import os

import pytest

from core.engine import IBCIEngine
from core.kernel.issue import CompilerError


@pytest.fixture
def engine():
    return IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)))


def _sem_errors(engine, code):
    with pytest.raises(CompilerError) as exc:
        engine.compile_string(code, silent=True)
    return [d for d in exc.value.diagnostics if d.code == "SEM_TYPE_MISMATCH"]


class TestCompileTimeCompareChecking:
    # ── SEM-1 三形态（原运行期 TypeError，现编译期拦截）──

    def test_str_ge_int_bare_form(self, engine):
        diags = _sem_errors(engine, 'str x = "a"\nif x >= 0:\n    print("a")\n')
        assert diags, "str >= int 裸形态应编译期拦截"
        assert diags[0].location is not None
        assert diags[0].location.line == 2

    def test_str_ge_int_cast_form(self, engine):
        diags = _sem_errors(engine, 'str x = (str)42\nif x >= 0:\n    print("b")\n')
        assert diags, "str >= int cast 形态应编译期拦截"
        assert diags[0].location.line == 2

    def test_str_ge_int_find_cast_chain(self, engine):
        diags = _sem_errors(
            engine, 'str s = "abc def"\nif (str)s.find("de") >= 0:\n    print("hit")\n'
        )
        assert diags, "str >= int cast 链形态应编译期拦截"
        assert diags[0].location.line == 2

    def test_int_ge_str(self, engine):
        diags = _sem_errors(engine, 'if 1 >= "a":\n    print("x")\n')
        assert diags, "int >= str 应编译期拦截（对称方向）"

    def test_chained_compare_str_mixed(self, engine):
        # 链式比较逐对检查：str 混入任意一对即拦截
        diags = _sem_errors(engine, 'any c = "a" < 1 < 2\n')
        assert diags, "链式比较 str 混入应编译期拦截"

    def test_list_ordering_compare(self, engine):
        diags = _sem_errors(engine, 'any a = [1] < [2]\n')
        assert diags, "容器排序比较（无 __lt__）应编译期拦截"

    def test_float_lt_str(self, engine):
        diags = _sem_errors(engine, 'any a = 1.5 < "x"\n')
        assert diags


class TestCompileTimeComparePassthrough:
    # ── 合法形态放行（防误报）──

    def test_int_ordering_compare_ok(self, engine):
        assert engine.compile_string("any a = 1 < 2", silent=True) is not None

    def test_str_ordering_compare_ok(self, engine):
        assert engine.compile_string('any a = "a" < "b"', silent=True) is not None

    def test_bool_ordering_compare_ok(self, engine):
        assert engine.compile_string("any a = True < False", silent=True) is not None

    def test_float_int_ordering_compare_ok(self, engine):
        assert engine.compile_string("any a = 1.5 < 2", silent=True) is not None

    def test_chained_int_compare_ok(self, engine):
        assert engine.compile_string("any a = 1 < 2 < 3", silent=True) is not None

    def test_cross_type_equality_ok(self, engine):
        # ==/!= 跨类型合法（运行期 False/True）
        assert engine.compile_string('any a = 5 == "x"', silent=True) is not None
        assert engine.compile_string('any a = "x" != 5', silent=True) is not None

    def test_container_equality_ok(self, engine):
        assert engine.compile_string("any a = [1] == [1]", silent=True) is not None

    def test_dynamic_operand_passthrough(self, engine):
        # any 操作数放行（is_dynamic 惯例——运行期裁决）
        assert engine.compile_string("any x = 1\nany y = 2\nany c = x >= y", silent=True) is not None
        assert engine.compile_string('any s = "a"\nany c = s >= 0', silent=True) is not None


class TestCompileTimeArithmeticChecking:
    def test_int_plus_str_intercepted(self, engine):
        diags = _sem_errors(engine, 'any a = 1 + "x"\n')
        assert diags, "int + str 应编译期拦截（运行期 TypeError 同语义前移）"

    def test_list_plus_int_intercepted(self, engine):
        diags = _sem_errors(engine, "any a = [1] + 1\n")
        assert diags

    def test_string_repetition_int_str_ok(self, engine):
        # 防误报：int * str = 字符串重复（运行期合法）
        assert engine.compile_string('any a = 5 * "x"', silent=True) is not None

    def test_string_repetition_bool_str_ok(self, engine):
        assert engine.compile_string('any a = True * "x"', silent=True) is not None

    def test_string_repetition_str_int_ok(self, engine):
        assert engine.compile_string('any a = "x" * 2', silent=True) is not None

    def test_float_str_mul_intercepted(self, engine):
        # float 无重复语义（运行期 ERR）
        diags = _sem_errors(engine, 'any a = 1.5 * "x"\n')
        assert diags

    def test_arithmetic_ok(self, engine):
        assert engine.compile_string("any a = 1 + 2", silent=True) is not None
        assert engine.compile_string("any a = 1.5 - 1", silent=True) is not None
        assert engine.compile_string("any a = True + True", silent=True) is not None

    def test_arithmetic_error_carries_location(self, engine):
        diags = _sem_errors(engine, "str a = \"x\"\nany b = 1 + a\n")
        assert diags and diags[0].location is not None
        assert diags[0].location.line == 2
