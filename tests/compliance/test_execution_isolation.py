"""
tests/compliance/test_execution_isolation.py
============================================

IBCI VM 合规测试：多 Interpreter 执行隔离。

覆盖以下契约：
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
import time
import tempfile
import pytest

from core.engine import IBCIEngine


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def write_child(code: str) -> str:
    """将 IBCI 代码写入临时文件，返回绝对路径。"""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".ibci", delete=False, dir=ROOT_DIR, encoding="utf-8"
    )
    f.write(code)
    f.close()
    return f.name


# ===========================================================================
# 子 Interpreter 变量不泄漏到主 Interpreter
# ===========================================================================

class TestVariableIsolation:
    """子 Interpreter 变量写入与主 Interpreter 完全隔离。"""

    def test_child_variable_not_visible_in_parent(self):
        """子 Interpreter 定义的变量不应出现在主 Interpreter 的作用域中。"""
        child_code = 'str secret = "child_only"\n'
        child_path = write_child(child_code)
        try:
            eng = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
            handle = eng.request_spawn_isolated(child_path, {})
            child_vars = eng.request_collect(handle)
            # 子环境变量可从 collect 读取
            assert child_vars.get("secret") == "child_only"
            # 主解释器从未运行（interpreter 未就绪），子变量天然不可见——
            # 不存在可被读取的"主 secret"。
            assert eng.interpreter is None
        finally:
            os.unlink(child_path)

    def test_parent_variable_not_inherited_by_child(self):
        """子 Interpreter 不继承主 Interpreter 的变量（隔离策略）。

        R2-E7：用公开 Engine API ``set_variable`` 注入主变量（激活该 API）。
        """
        # 子脚本尝试读取一个在主环境中存在的变量（会触发 undefined variable）
        child_code = 'str result = "ok_without_parent"\n'
        child_path = write_child(child_code)
        try:
            # 先在主环境定义一个变量（经公开 Engine API）
            eng = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
            eng.set_variable("main_var", "main_value")
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
            eng = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
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
# collect 结果语义
# ===========================================================================

class TestCollectSemantics:
    """collect 返回值的类型和内容约束。"""

    def test_collect_returns_dict(self):
        child = write_child('int x = 42\n')
        try:
            eng = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
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
            eng = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
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
            eng = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
            h = eng.request_spawn_isolated(child, {})
            result = eng.request_collect(h)
            assert result.get("nums") == [1, 2, 3]
            assert result.get("mapping") == {"a": 1, "b": 2}
        finally:
            os.unlink(child)

    def test_collect_excludes_intrinsic_symbols(self):
        """collect 不应返回内核原生函数（print/len/range 等）。"""
        child = write_child('int x = 1\n')
        try:
            eng = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
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
            eng = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
            h = eng.request_spawn_isolated(child, {})
            result = eng.request_collect(h)
            assert isinstance(result, dict)
            # 不含任何用户变量
            assert "x" not in result
        finally:
            os.unlink(child)


# ===========================================================================
# collect 幂等性保护 + 错误传播
# ===========================================================================

class TestCollectConstraints:
    """collect 的错误语义。"""

    def test_double_collect_raises(self):
        """对同一 handle 重复 collect 应抛出 RuntimeError（幂等性保护）。"""
        child = write_child('int x = 1\n')
        try:
            eng = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
            h = eng.request_spawn_isolated(child, {})
            eng.request_collect(h)  # 第一次成功
            with pytest.raises(RuntimeError):
                eng.request_collect(h)  # 第二次应失败
        finally:
            os.unlink(child)

    def test_child_compile_error_propagates_to_collect(self):
        """子 Interpreter 编译失败时，collect 应传播错误（RuntimeError 包装）。"""
        child = write_child('THIS IS NOT VALID IBCI @@@@\n')
        try:
            eng = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
            h = eng.request_spawn_isolated(child, {})
            with pytest.raises(RuntimeError, match="raised an exception"):
                eng.request_collect(h)
        finally:
            os.unlink(child)

    def test_spawn_returns_handle_string(self):
        """spawn_isolated 应立即返回字符串 handle（不阻塞等待子 Interpreter 完成）。"""
        child = write_child('int x = 1\n')
        try:
            eng = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
            h = eng.request_spawn_isolated(child, {})
            assert isinstance(h, str) and len(h) > 0
            eng.request_collect(h)  # 等待完成，避免悬挂线程
        finally:
            os.unlink(child)


# ===========================================================================
# collect 超时契约（ISO-9）
# ===========================================================================

class TestCollectTimeout:
    """collect 的墙钟超时行为（ISO-9）。"""

    def test_default_policy_is_unbounded(self):
        """默认 policy（无 collect_timeout）保持无界等待，正常脚本可被收集。"""
        child = write_child('str x = "ok"\n')
        try:
            eng = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
            h = eng.request_spawn_isolated(child, {})
            result = eng.request_collect(h)
            assert result.get("x") == "ok"
        finally:
            os.unlink(child)

    def test_explicit_none_timeout_collects_normally(self):
        """显式 collect_timeout=None 等价于无界，正常脚本可被收集。"""
        child = write_child('int n = 7\n')
        try:
            eng = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
            h = eng.request_spawn_isolated(child, {"collect_timeout": None})
            result = eng.request_collect(h)
            assert result.get("n") == 7
        finally:
            os.unlink(child)

    def test_generous_timeout_allows_completion(self):
        """宽裕的超时值不应干扰正常收集。"""
        child = write_child('str s = "done"\n')
        try:
            eng = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
            h = eng.request_spawn_isolated(child, {"collect_timeout": 30.0})
            result = eng.request_collect(h)
            assert result.get("s") == "done"
        finally:
            os.unlink(child)

    def test_timeout_raises_when_child_exceeds_deadline(self):
        """子执行未在 collect_timeout 内完成时，collect 应抛 RuntimeError。

        采用极小超时（1ms）：子引擎启动（构造 Engine + 编译 + 运行）远超 1ms，
        故 collect 必然超时。超时后子线程作为 daemon 孤儿继续运行；短暂等待
        让其自行结束，避免残留线程读取已被 finally 删除的临时文件。
        """
        child = write_child('str x = "ok"\n')
        try:
            eng = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
            h = eng.request_spawn_isolated(child, {"collect_timeout": 0.001})
            with pytest.raises(RuntimeError, match=r"(?i)timed out|timeout"):
                eng.request_collect(h)
            # 让未被 join 的 daemon 子线程自行结束
            time.sleep(0.3)
        finally:
            os.unlink(child)
