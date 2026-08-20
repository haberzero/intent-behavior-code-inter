"""
tests/e2e/test_ai_batch.py
==============================

``ai.run_batch`` 并发批量行为执行原语测试。

经 MOCK HTTP 服务（``mock_server``）验证真实并发：SLEEP 指令的逐项
延迟在并行调度下总时近似 max 而非 sum。

``run_batch`` 返回 ``CPSDrivable`` Waitable（不同步阻塞主线程），
与 ``stream_call`` 范式一致。
"""
import time

from tests.conftest import run_ibci


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


    def test_run_batch_rejects_invalid_target(self, mock_server):
        """统一装配入口 fail-fast：非 behavior / 非 llm 可调用类值 → TypeError。"""
        lines = run_ibci(
            _code(
                mock_server,
                "int x = 123\n"
                "try:\n"
                "    list results = ai.run_batch(x, [1])\n"
                "    print('no')\n"
                "except:\n"
                "    print('caught')\n",
            )
        )
        assert "caught" in lines
        assert "no" not in lines


class TestRunBatchWaitableContract:
    """run_batch 返回 CPSDrivable Waitable，不同步阻塞主线程。"""

    def test_executor_run_batch_returns_waitable(self, engine):
        """executor.run_batch 返回懒 Waitable+CPSDrivable（非普通 List）。

        懒构造即返回、不预求值、不阻塞；由 VM ``cps_drive`` 帧内驱动 +
        调度器非阻塞等待（与 stream_call 返回 Waitable 范式一致）。
        """
        from core.runtime.shared.waitable import Waitable, CPSDrivable
        from tests.conftest import AI_MOCK_PREFIX

        engine.run_string(
            AI_MOCK_PREFIX
            + "fn label = lambda(int i) -> str: @~ MOCK:STR:item$i ~\n",
            silent=True,
        )
        ec = engine.interpreter.execution_context
        executor = engine.interpreter.service_context.llm_executor
        behavior = ec.runtime_context.get_variable("label")
        items = [ec.registry.box(i) for i in (1, 2, 3)]
        t0 = time.monotonic()
        result = executor.run_batch(behavior, items, ec)
        elapsed = time.monotonic() - t0
        # 懒构造应即时返回（不预求值、不阻塞），即使 LLM 慢
        assert elapsed < 0.2, f"run_batch 构造不应阻塞: {elapsed:.3f}s"
        assert isinstance(result, Waitable), "run_batch 应返回 Waitable"
        assert isinstance(result, CPSDrivable), "run_batch 应支持 cps_drive"

    def test_run_batch_with_concurrent_thread(self, mock_server):
        """run_batch 与并发 spawn 线程共存：无死锁，各自结果正确。"""
        lines = run_ibci(
            _code(
                mock_server,
                "func worker(int n) -> int:\n"
                "    int s = 0\n"
                "    int i = 0\n"
                "    while i < n:\n"
                "        s = s + 1\n"
                "        i = i + 1\n"
                "    return s\n"
                "thread[int] t = thread(callable=worker, args=[5])\n"
                "fn label = lambda(int i) -> str: @~ MOCK:STR:item$i ~\n"
                "list results = ai.run_batch(label, [1, 2, 3])\n"
                "thread_result[int] r = t.join()\n"
                "print((str)r.expect())\n"
                "print(results)\n",
            )
        )
        assert lines and "5" in lines[0]
        assert lines[1] and "item1" in lines[1] and "item2" in lines[1] and "item3" in lines[1]


class TestRunBatchObservability:
    """run_batch 批路径的 LLM 调用可观测性。

    run_batch 批内 LLM 调用记录主线程单写槽，`get_current_call_info()` 立即可见，
    与单调用路径（inline/dispatch）的契约一致。
    """

    def test_run_batch_records_call_info(self):
        out = run_ibci(
            'fn label = lambda(int i) -> str: @~ MOCK:STR:item$i ~\n'
            'list results = ai.run_batch(label, [1, 2, 3])\n'
            'dict info = ai.get_current_call_info()\n'
            'print("user_prompt" in info)\n'
            'print(len(info["user_prompt"]) > 0)\n',
            ai=True,
        )
        assert out == ["True", "True"]

