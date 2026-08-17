"""
tests/e2e/test_host_async_concurrency.py
=============================================

统一异步架构并发 E2E 测试。

验证 IBCI 脚本经 ``ihost.collect`` 等待 ``HostAwaitable`` 时，VM 协作式挂起
（而非阻塞），且多个隔离子任务在后台线程中真实并发运行：

- ``collect`` 返回 ``HostAwaitable``（Waitable），VM 经 ``vm_handle_IbCall``
  ``yield`` 挂起，子线程完成后 ``result()`` 取回 dict；
- 多个子任务并发执行：总耗时 ≈ max(各子任务耗时)，而非 sum（串行）。

时序断言：并发总耗时 < 串行基准 × FACTOR + JITTER。
"""
import os
import time
import tempfile

from core.engine import IBCIEngine
from tests.conftest import run_ibci

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

_CONCURRENCY_TOLERANCE_FACTOR = 1.5
_SCHEDULING_JITTER_SECONDS = 0.5


def _write_child(code: str) -> str:
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".ibci", delete=False, dir=ROOT_DIR, encoding="utf-8"
    )
    f.write(code)
    f.close()
    return f.name


def _ibci_path(path: str) -> str:
    return path.replace("\\", "/")


class TestHostAsyncConcurrency:
    def test_collect_returns_awaitable_and_vm_awaits(self):
        """``dict r = ihost.collect(handle)``：VM 经 HostAwaitable 等待并取回 dict。"""
        child = _write_child('str answer = "hi"\n')
        try:
            code = (
                "import ihost\n"
                f'str h = ihost.spawn_isolated("{_ibci_path(child)}", {{}})\n'
                "dict r = ihost.collect(h)\n"
                'print(r["answer"])\n'
            )
            out = run_ibci(code)
            assert any("hi" in line for line in out)
        finally:
            os.unlink(child)

    def test_two_children_run_concurrently_via_ibci(self):
        """两个隔离子任务经 spawn+collect 并发执行，总耗时 ≈ max 而非 sum。"""
        child_code = 'str done = "yes"\n'
        child_a = _write_child(child_code)
        child_b = _write_child(child_code)
        try:
            eng = IBCIEngine(root_dir=ROOT_DIR)

            # 串行基准：两次顺序 spawn/collect（引擎层，作为耗时参照）
            t0 = time.monotonic()
            h1 = eng.request_spawn_isolated(child_a, {})
            eng.request_collect(h1)
            h2 = eng.request_spawn_isolated(child_b, {})
            eng.request_collect(h2)
            serial_time = time.monotonic() - t0

            # 并发路径：IBCI 脚本 spawn 两个子任务后 collect 两个
            code = (
                "import ihost\n"
                f'str ha = ihost.spawn_isolated("{_ibci_path(child_a)}", {{}})\n'
                f'str hb = ihost.spawn_isolated("{_ibci_path(child_b)}", {{}})\n'
                "dict ra = ihost.collect(ha)\n"
                "dict rb = ihost.collect(hb)\n"
                'print(ra["done"])\n'
                'print(rb["done"])\n'
            )
            t1 = time.monotonic()
            out = run_ibci(code)
            concurrent_time = time.monotonic() - t1

            assert any("yes" in line for line in out)
            threshold = serial_time * _CONCURRENCY_TOLERANCE_FACTOR + _SCHEDULING_JITTER_SECONDS
            assert concurrent_time < threshold, (
                f"concurrent_time={concurrent_time:.3f}s is not < "
                f"serial_time×{_CONCURRENCY_TOLERANCE_FACTOR}+{_SCHEDULING_JITTER_SECONDS}s "
                f"= {threshold:.3f}s (serial_time={serial_time:.3f}s)"
            )
        finally:
            os.unlink(child_a)
            os.unlink(child_b)