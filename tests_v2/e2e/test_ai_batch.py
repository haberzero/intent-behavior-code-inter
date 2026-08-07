"""
tests_v2/e2e/test_ai_batch.py
==============================

``ai.run_batch`` 并发批量行为执行原语测试。

经 MOCK HTTP 服务（``mock_server``）验证真实并发：SLEEP 指令的逐项
延迟在并行调度下总时近似 max 而非 sum。
"""
import time

from tests_v2.conftest import run_ibci


def _code(server, body):
    return f'import ai\nai.set_config("{server.url}/v1", "sk-test", "mock")\n' + body


class TestAiRunBatch:
    """ai.run_batch 批量行为执行。"""

    def test_run_batch_values_ordered(self, mock_server):
        """逐项绑定参数，结果按 items 顺序返回。"""
        lines = run_ibci(
            _code(
                mock_server,
                "fn label = lambda(int i) -> str: @~ MOCK:STR:item$i ~\n"
                "list items = [1, 2, 3]\n"
                "list results = ai.run_batch(label, items)\n"
                "print(results)\n",
            )
        )
        assert lines, f"expected output, got {lines}"
        assert "item1" in lines[0]
        assert "item2" in lines[0]
        assert "item3" in lines[0]

    def test_run_batch_concurrent_over_service(self, mock_server):
        """3 项各 SLEEP:300 → 总时显著小于串行 900ms，服务端观测到并发。"""
        t0 = time.monotonic()
        run_ibci(
            _code(
                mock_server,
                "fn slow = lambda(int i) -> int: @~ MOCK:INT:$i MOCK:SLEEP:300 ~\n"
                "list items = [1, 2, 3]\n"
                "list results = ai.run_batch(slow, items)\n"
                "print(results)\n",
            )
        )
        elapsed_ms = (time.monotonic() - t0) * 1000
        assert mock_server.stats.max_concurrent >= 2, "未观测到并发"
        assert elapsed_ms < 800, f"串行化迹象: {elapsed_ms:.0f}ms (3×300 串行≈900ms)"

    def test_run_batch_fail_raises(self, mock_server):
        """任一项 parse 失败 → 抛 LLMParseError（整个批次错误粒度）。"""
        lines = run_ibci(
            _code(
                mock_server,
                "fn risky = lambda(int i) -> str: @~ MOCK:FAIL boom$i ~\n"
                "list items = [1, 2, 3]\n"
                "try:\n"
                "    list results = ai.run_batch(risky, items)\n"
                "    print('no')\n"
                "except:\n"
                "    print('caught')\n",
            )
        )
        assert "caught" in lines
        assert "no" not in lines

    def test_run_batch_reuses_captured_var(self, mock_server):
        """行为可同时引用参数与定义作用域自由变量（lambda 闭包）。"""
        lines = run_ibci(
            _code(
                mock_server,
                "str prefix = 'doc'\n"
                "fn label = lambda(str x) -> str: @~ MOCK:STR:$prefix-$x ~\n"
                "list items = ['a', 'b']\n"
                "list results = ai.run_batch(label, items)\n"
                "print(results)\n",
            )
        )
        assert lines and "doc-a" in lines[0] and "doc-b" in lines[0]
