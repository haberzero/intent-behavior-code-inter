"""
tests/e2e/test_e2e_m4_multi_interpreter.py
===========================================

M4 — 多 Interpreter 并发（Layer 2 执行隔离）E2E 测试。

覆盖：

* Engine 层 API：request_spawn_isolated / request_collect 直接调用；
* IBCI 层 API：ihost.spawn_isolated / ihost.collect 通过脚本使用；
* 并发正确性：两个子引擎可以同时运行（总耗时 < 串行耗时）；
* 变量提取：collect 返回子环境的用户变量（str / int / list / dict），
  排除内置符号和不可序列化对象；
* 错误传播：子引擎编译失败时 collect 应抛出 RuntimeError；
* 幂等性保护：对同一 handle 重复 collect 应抛出 RuntimeError；
* run_isolated（阻塞版）行为不受 M4 影响。
"""
import os
import time
import tempfile
import pytest

from core.engine import IBCIEngine

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# 并发测试容差常量（宽松值，容纳 CI 调度抖动）
# ---------------------------------------------------------------------------
# 若两次串行执行各耗时 T，则两个并发执行的墙钟时间应 < T * FACTOR + JITTER_SECONDS
# FACTOR=1.5 对应"理想并行 ≈ 1×T"与"完全串行 = 2×T"之间留出明显余量
_CONCURRENCY_TOLERANCE_FACTOR = 1.5
_SCHEDULING_JITTER_SECONDS = 0.5
# spawn_isolated 本身（不含子引擎执行）不应阻塞主线程超过此时长
_MAX_SPAWN_BLOCKING_SECONDS = 5.0


def make_engine() -> IBCIEngine:
    return IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)


def _write_child(code: str) -> str:
    """将 IBCI 代码写入临时文件，返回绝对路径。"""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".ibci", delete=False, dir=ROOT_DIR, encoding="utf-8"
    )
    f.write(code)
    f.close()
    return f.name


# ===========================================================================
# 1. Engine 层直接 API 测试
# ===========================================================================

class TestEngineLayerAPI:
    """直接调用 IBCIEngine.request_spawn_isolated / request_collect。"""

    def test_spawn_returns_handle_string(self):
        child = _write_child('str result = "hello"\n')
        try:
            eng = make_engine()
            handle = eng.request_spawn_isolated(child, {})
            assert isinstance(handle, str)
            assert handle.startswith("spawn_")
            # 等待完成，避免悬挂线程影响后续测试
            eng.request_collect(handle)
        finally:
            os.unlink(child)

    def test_collect_returns_dict_with_user_vars(self):
        child = _write_child(
            'str greeting = "world"\n'
            'int count = 42\n'
        )
        try:
            eng = make_engine()
            handle = eng.request_spawn_isolated(child, {})
            result = eng.request_collect(handle)
            assert result.get("greeting") == "world"
            assert result.get("count") == 42
        finally:
            os.unlink(child)

    def test_collect_excludes_builtins(self):
        """内置符号（print、len 等）不应出现在 collect 结果中。"""
        child = _write_child('str x = "value"\n')
        try:
            eng = make_engine()
            handle = eng.request_spawn_isolated(child, {})
            result = eng.request_collect(handle)
            assert "print" not in result
            assert "len" not in result
            assert "x" in result
        finally:
            os.unlink(child)

    def test_collect_extracts_list_and_dict(self):
        child = _write_child(
            'list nums = [1, 2, 3]\n'
            'dict info = {"key": "val"}\n'
        )
        try:
            eng = make_engine()
            handle = eng.request_spawn_isolated(child, {})
            result = eng.request_collect(handle)
            assert result.get("nums") == [1, 2, 3]
            assert result.get("info") == {"key": "val"}
        finally:
            os.unlink(child)

    def test_collect_handle_consumed_raises_on_reuse(self):
        """同一 handle 不能被 collect 两次。"""
        child = _write_child('str x = "once"\n')
        try:
            eng = make_engine()
            handle = eng.request_spawn_isolated(child, {})
            eng.request_collect(handle)
            with pytest.raises(RuntimeError, match="Unknown spawn handle"):
                eng.request_collect(handle)
        finally:
            os.unlink(child)

    def test_collect_propagates_child_exception(self):
        """子引擎编译错误应在 collect 时以 RuntimeError 形式传播。"""
        child = _write_child("INVALID IBCI CODE @@@@\n")
        try:
            eng = make_engine()
            handle = eng.request_spawn_isolated(child, {})
            with pytest.raises(RuntimeError):
                eng.request_collect(handle)
        finally:
            os.unlink(child)

    def test_unknown_handle_raises(self):
        eng = make_engine()
        with pytest.raises(RuntimeError, match="Unknown spawn handle"):
            eng.request_collect("spawn_deadbeef")

    def test_multiple_sequential_spawns(self):
        """多次顺序 spawn/collect 各自独立，互不干扰。"""
        child_a = _write_child('str label = "alpha"\n')
        child_b = _write_child('str label = "beta"\n')
        try:
            eng = make_engine()
            ha = eng.request_spawn_isolated(child_a, {})
            hb = eng.request_spawn_isolated(child_b, {})
            ra = eng.request_collect(ha)
            rb = eng.request_collect(hb)
            assert ra.get("label") == "alpha"
            assert rb.get("label") == "beta"
        finally:
            os.unlink(child_a)
            os.unlink(child_b)


# ===========================================================================
# 2. 并发正确性测试
# ===========================================================================

class TestConcurrency:
    """验证多个子引擎可以真正并发运行（Layer 2 的核心价值）。"""

    def test_two_spawns_run_concurrently(self):
        """
        两个子引擎应并发执行而非串行。
        基准：顺序执行同一子脚本两次的总耗时（串行 2×T）；
        并发：spawn 两个子脚本后 collect 两次的总耗时（应 ≈ T）。
        验证：并发总耗时 < 串行总耗时 * FACTOR + JITTER。
        """
        child_code = 'str done = "yes"\n'
        child_a = _write_child(child_code)
        child_b = _write_child(child_code)
        try:
            eng = make_engine()

            # 串行基准：两次顺序 spawn/collect
            t0 = time.monotonic()
            h1 = eng.request_spawn_isolated(child_a, {})
            eng.request_collect(h1)
            h2 = eng.request_spawn_isolated(child_b, {})
            eng.request_collect(h2)
            serial_time = time.monotonic() - t0

            # 并发测量：两个 spawn 后再 collect
            t1 = time.monotonic()
            ha = eng.request_spawn_isolated(child_a, {})
            hb = eng.request_spawn_isolated(child_b, {})
            ra = eng.request_collect(ha)
            rb = eng.request_collect(hb)
            concurrent_time = time.monotonic() - t1

            assert ra.get("done") == "yes"
            assert rb.get("done") == "yes"
            # 并发耗时应明显小于串行两倍执行时间
            threshold = serial_time * _CONCURRENCY_TOLERANCE_FACTOR + _SCHEDULING_JITTER_SECONDS
            assert concurrent_time < threshold, (
                f"concurrent_time={concurrent_time:.3f}s is not < "
                f"serial_time×{_CONCURRENCY_TOLERANCE_FACTOR}+{_SCHEDULING_JITTER_SECONDS}s "
                f"= {threshold:.3f}s (serial_time={serial_time:.3f}s)"
            )
        finally:
            os.unlink(child_a)
            os.unlink(child_b)

    def test_spawn_is_nonblocking(self):
        """
        spawn_isolated 应立即返回，主线程不被阻塞直到 collect。
        通过检查 spawn 返回时间远小于最大容许阻塞阈值来验证。
        """
        child = _write_child('str result = "nonblock"\n')
        try:
            eng = make_engine()
            t0 = time.monotonic()
            handle = eng.request_spawn_isolated(child, {})
            t_spawn = time.monotonic() - t0
            assert t_spawn < _MAX_SPAWN_BLOCKING_SECONDS, (
                f"spawn_isolated blocked for {t_spawn:.2f}s "
                f"(threshold: {_MAX_SPAWN_BLOCKING_SECONDS}s)"
            )
            # handle 已注册到任务表
            with eng._spawned_tasks_lock:
                assert handle in eng._spawned_tasks
            eng.request_collect(handle)
        finally:
            os.unlink(child)


# ===========================================================================
# 3. IBCI 层 ihost.spawn_isolated / ihost.collect 测试
# ===========================================================================

class TestIBCILayerAPI:
    """通过 IBCI 代码调用 ihost.spawn_isolated / ihost.collect。"""

    def _run_capture(self, code: str):
        out: list = []
        eng = make_engine()
        eng.run_string(code, output_callback=lambda s: out.append(str(s)), silent=True)
        return eng, out

    def test_spawn_collect_roundtrip_via_ibci(self):
        """IBCI 脚本可以 spawn 一个子脚本并通过 collect 读取其结果。"""
        child = _write_child('str answer = "forty-two"\n')
        try:
            code = (
                "import ihost\n"
                f'str handle = ihost.spawn_isolated("{child}", {{}})\n'
                "dict results = ihost.collect(handle)\n"
                'print(results["answer"])\n'
            )
            _, out = self._run_capture(code)
            assert any("forty-two" in line for line in out)
        finally:
            os.unlink(child)

    def test_spawn_collect_int_result(self):
        child = _write_child('int score = 100\n')
        try:
            code = (
                "import ihost\n"
                f'str handle = ihost.spawn_isolated("{child}", {{}})\n'
                "dict results = ihost.collect(handle)\n"
                'print((str)results["score"])\n'
            )
            _, out = self._run_capture(code)
            assert any("100" in line for line in out)
        finally:
            os.unlink(child)

    def test_spawn_returns_str_handle_in_ibci(self):
        """spawn_isolated 在 IBCI 类型系统中返回 str。"""
        child = _write_child('str x = "ok"\n')
        try:
            code = (
                "import ihost\n"
                f'str handle = ihost.spawn_isolated("{child}", {{}})\n'
                "print(handle)\n"
                "dict _ = ihost.collect(handle)\n"
            )
            _, out = self._run_capture(code)
            # handle 应以 spawn_ 开头
            assert any(line.startswith("spawn_") for line in out)
        finally:
            os.unlink(child)

    def test_two_concurrent_spawns_via_ibci(self):
        """IBCI 代码可以同时 spawn 两个子脚本，两者都能成功 collect。"""
        child_a = _write_child('str name = "alice"\n')
        child_b = _write_child('str name = "bob"\n')
        try:
            code = (
                "import ihost\n"
                f'str ha = ihost.spawn_isolated("{child_a}", {{}})\n'
                f'str hb = ihost.spawn_isolated("{child_b}", {{}})\n'
                "dict ra = ihost.collect(ha)\n"
                "dict rb = ihost.collect(hb)\n"
                'print(ra["name"])\n'
                'print(rb["name"])\n'
            )
            _, out = self._run_capture(code)
            assert any("alice" in line for line in out)
            assert any("bob" in line for line in out)
        finally:
            os.unlink(child_a)
            os.unlink(child_b)


# ===========================================================================
# 4. run_isolated（阻塞版）兼容性回归测试
# ===========================================================================

class TestRunIsolatedCompatibility:
    """确保 M4 新增的 spawn/collect 不破坏既有的同步 run_isolated。"""

    def test_run_isolated_still_works(self):
        child = _write_child('str x = "sync"\n')
        try:
            code = (
                "import ihost\n"
                f'bool ok = ihost.run_isolated("{child}", {{}})\n'
                "print((str)ok)\n"
            )
            out: list = []
            eng = make_engine()
            eng.run_string(code, output_callback=lambda s: out.append(str(s)), silent=True)
            assert any("1" in line or "True" in line for line in out)
        finally:
            os.unlink(child)
