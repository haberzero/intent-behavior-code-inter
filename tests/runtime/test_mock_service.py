"""
tests/runtime/test_mock_service.py
===================================

MOCK HTTP 服务（``MockServer``）测试：OpenAI 兼容协议、SSE 流式、
延迟/失败注入、并发鲁棒性与 IBCI 端到端集成。

服务是 LLM 并行化（dispatch）机制验证的传输层彩排——测试经真实
``OpenAI`` 客户端驱动服务，覆盖 ``AIPlugin._init_client`` +
``chat.completions.create`` 的完整路径。
"""
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from openai import OpenAI


def _client(server):
    return OpenAI(api_key="sk-test", base_url=server.url + "/v1")


def _complete(client, content, *, stream=False, model="mock"):
    return client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        stream=stream,
    )


def _code(server, body):
    return f'import ai\nai.set_config("{server.url}/v1", "sk-test", "mock")\n' + body


class TestMockServiceHTTP:
    """非流式端点的值指令与哨兵往返。"""

    def test_str_directive_over_http(self, mock_server):
        client = _client(mock_server)
        resp = _complete(client, "MOCK:STR:hello")
        assert resp.choices[0].message.content == "hello"
        assert resp.object == "chat.completion"

    def test_int_directive_over_http(self, mock_server):
        client = _client(mock_server)
        resp = _complete(client, "MOCK:INT:42")
        assert resp.choices[0].message.content == "42"

    def test_fail_sentinel_round_trip(self, mock_server):
        client = _client(mock_server)
        resp = _complete(client, "MOCK:FAIL x")
        assert "MAYBE" in resp.choices[0].message.content

    def test_repair_sequence_over_http(self, mock_server):
        client = _client(mock_server)
        first = _complete(client, "MOCK:REPAIR:STR:fixed")
        second = _complete(client, "MOCK:REPAIR:STR:fixed")
        assert "__MOCK_REPAIR__" in first.choices[0].message.content
        assert second.choices[0].message.content == "fixed"

    def test_stats_recorded(self, mock_server):
        client = _client(mock_server)
        _complete(client, "MOCK:STR:a")
        _complete(client, "MOCK:STR:b")
        assert mock_server.stats.total_requests == 2
        assert mock_server.stats.completed_requests == 2

    def test_unknown_route_404(self, mock_server):
        import urllib.request

        with pytest.raises(Exception):
            urllib.request.urlopen(mock_server.url + "/nope")


class TestMockServiceStream:
    """SSE 流式端点。"""

    def test_stream_content(self, mock_server):
        client = _client(mock_server)
        stream = _complete(client, "MOCK:STR:streamed", stream=True)
        parts = [
            chunk.choices[0].delta.content
            for chunk in stream
            if chunk.choices and chunk.choices[0].delta.content
        ]
        assert "".join(parts) == "streamed"

    def test_stream_finish_reason(self, mock_server):
        client = _client(mock_server)
        stream = _complete(client, "MOCK:STR:x", stream=True)
        finish = [chunk.choices[0].finish_reason for chunk in stream]
        assert "stop" in finish


class TestMockServiceControls:
    """延迟与失败注入。"""

    def test_sleep_delay_honored(self, mock_server):
        client = _client(mock_server)
        t0 = time.monotonic()
        resp = _complete(client, "MOCK:STR:a MOCK:SLEEP:300")
        elapsed_ms = (time.monotonic() - t0) * 1000
        assert resp.choices[0].message.content == "a"
        assert elapsed_ms >= 280

    def test_error_injection_raises(self, mock_server):
        client = _client(mock_server)
        with pytest.raises(Exception) as excinfo:
            _complete(client, "MOCK:ERROR:500")
        assert getattr(excinfo.value, "status_code", None) == 500


class TestMockServiceConcurrency:
    """服务端并发鲁棒性：线程池处理 + 请求级隔离。"""

    def test_parallel_requests_overlap(self, mock_server):
        client = _client(mock_server)

        def call(i):
            return _complete(client, f"MOCK:STR:v{i} MOCK:SLEEP:300").choices[0].message.content

        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=3) as ex:
            results = list(ex.map(call, [1, 2, 3]))
        elapsed_ms = (time.monotonic() - t0) * 1000
        assert sorted(results) == ["v1", "v2", "v3"]
        # 并发重叠证据：总时显著小于串行 900ms，且服务端观测到并发
        assert elapsed_ms < 800
        assert mock_server.stats.max_concurrent >= 2

    def test_seq_state_isolation_between_servers(self):
        """不同服务实例的 SEQ 计数互不影响。"""
        from ibci_modules.ibci_ai.mock_service import MockServer

        with MockServer() as s1, MockServer() as s2:
            c1, c2 = _client(s1), _client(s2)
            r1 = _complete(c1, "MOCK:SEQ:[first,second] k").choices[0].message.content
            r2 = _complete(c2, "MOCK:SEQ:[first,second] k").choices[0].message.content
            assert r1 == "first"
            assert r2 == "first"


class TestMockServiceE2E:
    """经 IBCI 引擎 + 真实 OpenAI 客户端路径的端到端。"""

    def test_behavior_expression_over_service(self, mock_server):
        from tests.conftest import run_ibci

        lines = run_ibci(_code(mock_server, "str x = @~ MOCK:STR:hello ~\nprint(x)\n"))
        assert "hello" in lines

    def test_llmexcept_repair_over_service(self, mock_server):
        from tests.conftest import run_ibci

        lines = run_ibci(
            _code(
                mock_server,
                "int result = @~ MOCK:REPAIR:INT:42 ~\n"
                "llmexcept:\n"
                '    retry "be precise"\n'
                "print((str)result)\n",
            )
        )
        assert "42" in lines

    def test_fail_outside_llmexcept_raises(self, mock_server):
        from tests.conftest import run_ibci

        lines = run_ibci(
            _code(
                mock_server,
                "try:\n"
                "    str x = @~ MOCK:FAIL boom ~\n"
                "    print(x)\n"  # 读取触发 resolve → 抛 LLMParseError
                "    print('no')\n"
                "except:\n"
                "    print('caught')\n",
            )
        )
        assert "caught" in lines
        assert "no" not in lines

    def test_prompt_reaches_executor_call_info(self, mock_server):
        from tests.conftest import run_ibci

        run_ibci(_code(mock_server, "str x = @~ MOCK:STR:seen ~\nprint(x)\n"))
        reqs = [r["user_prompt"] for r in mock_server.stats.requests]
        assert any("MOCK:STR:seen" in p for p in reqs)
