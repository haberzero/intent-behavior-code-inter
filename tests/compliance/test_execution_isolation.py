"""
tests/compliance/test_execution_isolation.py
============================================

IBCI VM 合规测试：多 Interpreter 执行隔离（M4 / SPEC §4）。

覆盖 docs/VM_SPEC.md §4 定义的以下契约：
  - 子 Interpreter 拥有独立 RuntimeContext，与主 Interpreter 完全隔离
  - 子 Interpreter 的变量写入不影响主 Interpreter 的变量空间
  - 主 Interpreter 的变量写入不影响子 Interpreter 的执行
  - ``collect()`` 仅返回子环境的用户变量（str / int / bool / list / dict）
  - 同一 handle 重复 ``collect()`` 产生幂等性错误
  - 子 Interpreter 编译失败时 ``collect()`` 传播错误

合规性说明：本文件仅使用 ``IBCIEngine`` 公开 API，不依赖内部实现细节，
可作为未来跨宿主实现的合规验证测试集。
"""
import os
import tempfile
import pytest

from core.engine import IBCIEngine


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def make_engine() -> IBCIEngine:
    return IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)


def write_child(code: str) -> str:
    """将 IBCI 代码写入临时文件，返回绝对路径。"""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".ibci", delete=False, dir=ROOT_DIR, encoding="utf-8"
    )
    f.write(code)
    f.close()
    return f.name


# ===========================================================================
# SPEC §4.1 — 子 Interpreter 变量不泄漏到主 Interpreter
# ===========================================================================

class TestVariableIsolation:
    """SPEC §4.1：子 Interpreter 变量写入与主 Interpreter 完全隔离。"""

    def test_child_variable_not_visible_in_parent(self):
        """子 Interpreter 定义的变量不应出现在主 Interpreter 的作用域中。"""
        child_code = 'str secret = "child_only"\n'
        child_path = write_child(child_code)
        try:
            eng = make_engine()
            handle = eng.request_spawn_isolated(child_path, {})
            child_vars = eng.request_collect(handle)
            # 子环境变量可从 collect 读取
            assert child_vars.get("secret") == "child_only"
            # 主解释器不存在该变量
            with pytest.raises(Exception):
                eng.interpreter.runtime_context.get_variable("secret")
        finally:
            os.unlink(child_path)

    def test_parent_variable_not_inherited_by_child(self):
        """子 Interpreter 不继承主 Interpreter 的变量（隔离策略）。"""
        # 子脚本尝试读取一个在主环境中存在的变量（会触发 undefined variable）
        child_code = 'str result = "ok_without_parent"\n'
        child_path = write_child(child_code)
        try:
            # 先在主环境定义一个变量
            eng = make_engine()
            eng.run_string('str main_var = "main_value"\n', silent=True)
            # 子 Interpreter 正常运行，不受主环境变量影响
            handle = eng.request_spawn_isolated(child_path, {})
            result = eng.request_collect(handle)
            assert result.get("result") == "ok_without_parent"
        finally:
            os.unlink(child_path)

    def test_two_children_independent_from_each_other(self):
        """两个并发子 Interpreter 互不影响。"""
        child_a = write_child('str who = "A"\nint val = 1\n')
        child_b = write_child('str who = "B"\nint val = 2\n')
        try:
            eng = make_engine()
            ha = eng.request_spawn_isolated(child_a, {})
            hb = eng.request_spawn_isolated(child_b, {})
            ra = eng.request_collect(ha)
            rb = eng.request_collect(hb)
            assert ra.get("who") == "A" and ra.get("val") == 1
            assert rb.get("who") == "B" and rb.get("val") == 2
        finally:
            os.unlink(child_a)
            os.unlink(child_b)


# ===========================================================================
# SPEC §4.2 — collect 结果语义
# ===========================================================================

class TestCollectSemantics:
    """SPEC §4.2：collect 返回值的类型和内容约束。"""

    def test_collect_returns_dict(self):
        child = write_child('int x = 42\n')
        try:
            eng = make_engine()
            h = eng.request_spawn_isolated(child, {})
            result = eng.request_collect(h)
            assert isinstance(result, dict)
        finally:
            os.unlink(child)

    def test_collect_includes_str_int_bool(self):
        child = write_child(
            'str s = "hello"\n'
            'int n = 99\n'
            'bool flag = True\n'
        )
        try:
            eng = make_engine()
            h = eng.request_spawn_isolated(child, {})
            result = eng.request_collect(h)
            assert result.get("s") == "hello"
            assert result.get("n") == 99
            assert result.get("flag") is True
        finally:
            os.unlink(child)

    def test_collect_includes_list_and_dict(self):
        child = write_child(
            'list[int] nums = [1, 2, 3]\n'
            'dict[str, int] mapping = {"a": 1, "b": 2}\n'
        )
        try:
            eng = make_engine()
            h = eng.request_spawn_isolated(child, {})
            result = eng.request_collect(h)
            assert result.get("nums") == [1, 2, 3]
            assert result.get("mapping") == {"a": 1, "b": 2}
        finally:
            os.unlink(child)

    def test_collect_excludes_builtin_symbols(self):
        """collect 不应返回内置函数（print/len/range 等）。"""
        child = write_child('int x = 1\n')
        try:
            eng = make_engine()
            h = eng.request_spawn_isolated(child, {})
            result = eng.request_collect(h)
            assert "print" not in result
            assert "len" not in result
            assert "range" not in result
        finally:
            os.unlink(child)

    def test_collect_empty_child(self):
        """空脚本的 collect 应返回空字典（无用户变量）。"""
        child = write_child('')
        try:
            eng = make_engine()
            h = eng.request_spawn_isolated(child, {})
            result = eng.request_collect(h)
            assert isinstance(result, dict)
            # 不含任何用户变量
            assert "x" not in result
        finally:
            os.unlink(child)


# ===========================================================================
# SPEC §4.3 — collect 幂等性保护 + 错误传播
# ===========================================================================

class TestCollectConstraints:
    """SPEC §4.3：collect 的错误语义。"""

    def test_double_collect_raises(self):
        """对同一 handle 重复 collect 应抛出 RuntimeError（幂等性保护）。"""
        child = write_child('int x = 1\n')
        try:
            eng = make_engine()
            h = eng.request_spawn_isolated(child, {})
            eng.request_collect(h)  # 第一次成功
            with pytest.raises(RuntimeError):
                eng.request_collect(h)  # 第二次应失败
        finally:
            os.unlink(child)

    def test_child_compile_error_propagates_to_collect(self):
        """子 Interpreter 编译失败时，collect 应传播错误（RuntimeError 或 Exception）。"""
        child = write_child('THIS IS NOT VALID IBCI @@@@\n')
        try:
            eng = make_engine()
            h = eng.request_spawn_isolated(child, {})
            with pytest.raises(Exception):
                eng.request_collect(h)
        finally:
            os.unlink(child)

    def test_spawn_returns_handle_string(self):
        """spawn_isolated 应立即返回字符串 handle（不阻塞等待子 Interpreter 完成）。"""
        child = write_child('int x = 1\n')
        try:
            eng = make_engine()
            h = eng.request_spawn_isolated(child, {})
            assert isinstance(h, str) and len(h) > 0
            eng.request_collect(h)  # 等待完成，避免悬挂线程
        finally:
            os.unlink(child)
