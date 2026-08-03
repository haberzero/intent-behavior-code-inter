"""
tests/runtime/test_streaming.py
===============================

PT-MT-6 流式 + 并行测试。

锁定：
- MOCK:STREAM 指令解析（mock_scenario 分块）
- MockServer SSE 流式端点（真实 OpenAI 客户端流式收到分块）
- stream_call（Waitable）经 await / 赋值自动等待返回完整文本
- stream_channel 增量渲染（阻塞 recv 逐块消费）
- IbStreamHandle 单元（后台线程 → Channel → 完整文本）
"""
import time

import pytest

from tests.conftest import run_ibci
from ibci_modules.ibci_ai.mock_scenario import MockScenarioEngine
from ibci_modules.ibci_ai.mock_service import MockServer
from openai import OpenAI

from core.runtime.objects.stream import IbStreamHandle


# ------------------------------------------------------------------ #
# 单元：IbStreamHandle                                               #
# ------------------------------------------------------------------ #

class TestIbStreamHandle:
    def test_producer_to_full_text(self):
        h = IbStreamHandle(producer=lambda: iter(["a", "b", "c"]))
        assert h.result() == "abc"

    def test_channel_receives_chunks(self):
        h = IbStreamHandle(producer=lambda: iter(["x", "y"]))
        ok1, c1 = h.recv_nowait()
        ok2, c2 = h.recv_nowait()
        assert (ok1 and c1 == "x") and (ok2 and c2 == "y")

    def test_is_done_after_consumption(self):
        h = IbStreamHandle(producer=lambda: iter(["z"]))
        h.result()
        assert h.is_done


# ------------------------------------------------------------------ #
# MOCK 指令：STREAM 分块                                            #
# ------------------------------------------------------------------ #

class TestMockStreamDirective:
    def test_stream_directive_chunks(self):
        eng = MockScenarioEngine()
        r = eng.handle("MOCK:STREAM:Hello| World|!")
        assert r.chunks == ["Hello", " World", "!"]
        assert r.content == "Hello World!"


# ------------------------------------------------------------------ #
# MockServer SSE 端点（真实 OpenAI 客户端流式）                      #
# ------------------------------------------------------------------ #

class TestMockServerStreaming:
    def test_streaming_via_openai_client(self, mock_server):
        base = mock_server.url.rstrip("/") + "/v1"
        client = OpenAI(api_key="sk-test", base_url=base)
        resp = client.chat.completions.create(
            model="mock",
            messages=[{"role": "user", "content": "MOCK:STREAM:Hello| World|!"}],
            stream=True,
        )
        pieces = []
        for chunk in resp:
            if chunk.choices and chunk.choices[0].delta.content:
                pieces.append(chunk.choices[0].delta.content)
        assert pieces == ["Hello", " World", "!"]
        assert "".join(pieces) == "Hello World!"


# ------------------------------------------------------------------ #
# 语言面：stream_call（await / 自动等待完整文本）                    #
# ------------------------------------------------------------------ #

class TestStreamCallLanguage:
    def test_stream_call_awaits_full_text(self, mock_server):
        code = (
            f'import ai\nai.set_config("{mock_server.url}", "sk-test", "mock")\n'
            'str full = await ai.stream_call("sys", "MOCK:STREAM:Hello| World|!")\n'
            "print(full)\n"
        )
        lines = run_ibci(code)
        assert lines == ["Hello World!"]

    def test_stream_call_auto_wait_on_assign(self, mock_server):
        code = (
            f'import ai\nai.set_config("{mock_server.url}", "sk-test", "mock")\n'
            'any h = ai.stream_call("sys", "MOCK:STREAM:Hi| there")\n'
            "str s = (str)h\n"
            "print(s)\n"
        )
        lines = run_ibci(code)
        assert lines == ["Hi there"]


# ------------------------------------------------------------------ #
# 语言面：stream_channel（增量渲染）                                 #
# ------------------------------------------------------------------ #

class TestStreamChannelLanguage:
    def test_stream_channel_incremental_recv(self, mock_server):
        code = (
            f'import ai\nai.set_config("{mock_server.url}", "sk-test", "mock")\n'
            'chan chunks = ai.stream_channel("sys", "MOCK:STREAM:Hello| World|!")\n'
            "str c1 = chunks.recv()\n"
            "str c2 = chunks.recv()\n"
            "str c3 = chunks.recv()\n"
            "print(c1)\n"
            "print(c2)\n"
            "print(c3)\n"
        )
        lines = run_ibci(code)
        assert lines == ["Hello", " World", "!"]
