"""
tests/runtime/test_concurrent_dispatch_integrity.py
====================================================

PT-SYNC-1 并发正确性验证：executor 并行 dispatch（`dispatch_eager`/`resolve`）
在真实并发下的完整性。

与 MOCK（同步路径、忽略 SLEEP）不同，本文件经 ``mock_server`` 真实 HTTP +
真实 OpenAI 客户端 + 真实线程池驱动并行 dispatch，确保后台 worker 真正并行
执行，从而验证：

  ① 真正并发重叠（服务端观测到 max_concurrent ≥ 2，总时显著小于串行）
  ② 无串扰（每条独立 dispatch 的 prompt→值映射唯一、正确，不互相污染）
  ③ 乱序完成下输出仍按程序序（确定性）
  ④ 批次间无状态泄漏（多次并发批互不污染）

价值场景：Stage 1 去共享化的根因（worker 线程不写主线程单写槽）的正确性
不被回归——若后台 worker 污染共享状态，①-④ 之一会失败。
"""
from tests.conftest import run_ibci


def _code(server, n, sleep_ms, value_prefix):
    """构建 N 条独立 behavior 赋值 + 顺序打印的脚本（强制并发重叠）。"""
    body = []
    for i in range(n):
        body.append(f"str k{i} = @~ MOCK:STR:{value_prefix}{i} MOCK:SLEEP:{sleep_ms} ~")
    for i in range(n):
        body.append(f"print(k{i})")
    return 'import ai\nai.set_config("{}", "sk-test", "mock")\n'.format(server.url + "/v1") + "\n".join(body)


class TestConcurrentDispatchOverlap:
    """① 真正并发重叠：非串行执行。"""

    def test_independent_dispatch_overlaps(self, mock_server):
        run_ibci(_code(mock_server, n=4, sleep_ms=350, value_prefix="ov"))
        # 服务端观测到并发请求（max_concurrent >= 2）
        assert mock_server.stats.max_concurrent >= 2, (
            f"expected concurrency, got max_concurrent={mock_server.stats.max_concurrent}"
        )

    def test_total_time_below_serial(self, mock_server):
        import time

        sleep_ms = 300
        n = 4
        t0 = time.monotonic()
        run_ibci(_code(mock_server, n=n, sleep_ms=sleep_ms, value_prefix="fast"))
        elapsed_ms = (time.monotonic() - t0) * 1000
        # 串行需 ~4*300=1200ms + 开销；并发应显著小于。
        assert elapsed_ms < n * sleep_ms  # 严格小于串行总和即证并发


class TestConcurrentDispatchNoCrossTalk:
    """② 无串扰：每条独立 dispatch 的 prompt→值映射唯一且正确。"""

    def test_all_values_correct_and_unique(self, mock_server):
        n = 6
        out = run_ibci(_code(mock_server, n=n, sleep_ms=200, value_prefix="vt"))
        # 输出恰好为每个唯一值一次（无污染 / 无丢失）
        assert out == [f"vt{i}" for i in range(n)]

    def test_each_request_has_unique_directive(self, mock_server):
        run_ibci(_code(mock_server, n=5, sleep_ms=150, value_prefix="uq"))
        reqs = [r["user_prompt"] for r in mock_server.stats.requests]
        seen = set()
        for p in reqs:
            for i in range(5):
                marker = f"uq{i}"
                if marker in p:
                    assert marker not in seen, f"directive {marker} dispatched twice (cross-talk)"
                    seen.add(marker)
        assert seen == {f"uq{i}" for i in range(5)}


class TestConcurrentDispatchDeterminism:
    """③ 乱序完成下输出仍按程序序。"""

    def test_output_order_is_program_order_under_concurrency(self, mock_server):
        n = 6
        out = run_ibci(_code(mock_server, n=n, sleep_ms=180, value_prefix="ord"))
        assert out == [f"ord{i}" for i in range(n)]


class TestConcurrentBatchIsolation:
    """④ 批次间无状态泄漏。"""

    def test_two_sequential_batches_do_not_cross_contaminate(self, mock_server):
        first = run_ibci(_code(mock_server, n=3, sleep_ms=120, value_prefix="b1"))
        second = run_ibci(_code(mock_server, n=3, sleep_ms=120, value_prefix="b2"))
        assert first == ["b10", "b11", "b12"]
        assert second == ["b20", "b21", "b22"]


class TestConcurrentStability:
    """⑤ 稳定性：重复并发执行跨轮次必须确定性一致（防间歇性 race）。

    race 类缺陷是间歇性的——单轮通过不代表无并发竞争。重复多轮完全一致
    是对 Stage 1 去共享化（worker 不写共享状态）的强证据。
    """

    def test_repeated_runs_are_deterministic(self, mock_server):
        ref = None
        for _ in range(5):
            out = run_ibci(_code(mock_server, n=5, sleep_ms=120, value_prefix="det"))
            if ref is None:
                ref = out
            assert out == ref, f"并发执行跨轮次不确定 (race): {out}"

    def test_eight_task_batch_at_worker_limit(self, mock_server):
        """8 路并发在 max_workers=8 满员下仍正确且重叠（池边界）。"""
        n = 8
        out = run_ibci(_code(mock_server, n=n, sleep_ms=150, value_prefix="mx"))
        assert out == [f"mx{i}" for i in range(n)]
        assert mock_server.stats.max_concurrent >= 2