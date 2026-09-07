"""
tests/runtime/test_streaming.py
===============================

流式 + 并行测试。

锁定：
- MOCK:STREAM 指令解析（mock_scenario 分块）
- MockServer SSE 流式端点（真实 OpenAI 客户端流式收到分块）
- stream_call（Waitable）经 await / 赋值自动等待返回完整文本
- stream_channel 增量渲染（阻塞 recv 逐块消费）
- IbStreamHandle 单元（后台线程 → Channel → 完整文本）
"""
import time
import threading

import pytest

from tests.conftest import run_ibci
from ibci_modules.ibci_ai.mock_scenario import MockScenarioEngine
from ibci_modules.ibci_ai.mock_service import MockServer
from openai import OpenAI

from core.runtime.objects.stream import IbStreamHandle
from core.runtime.objects import stream as stream_mod


# ------------------------------------------------------------------ #
# 单元：IbStreamHandle                                               #
# ------------------------------------------------------------------ #

class TestIbStreamHandle:
    def test_producer_to_full_text(self):
        h = IbStreamHandle(producer=lambda: (x for x in ["a", "b", "c"]))
        assert h.result() == "abc"

    def test_channel_receives_chunks(self):
        h = IbStreamHandle(producer=lambda: (x for x in ["x", "y"]))
        ok1, c1 = h.recv_nowait()
        ok2, c2 = h.recv_nowait()
        assert (ok1 and c1 == "x") and (ok2 and c2 == "y")

    def test_is_done_after_consumption(self):
        h = IbStreamHandle(producer=lambda: (x for x in ["z"]))
        h.result()
        assert h.is_done


# ------------------------------------------------------------------ #
# IbStreamHandle.cancel（协作式截断）+ 退出兜底                       #
# ------------------------------------------------------------------ #

class TestIbStreamHandleCancel:
    """cancel 协作式截断与进程退出 drain（流句柄放弃 → 消费线程干净退出）。"""

    def _slow_producer(self, finally_ran, first_chunk_delay=0.2, hang_after_first=2.0):
        def producer():
            time.sleep(first_chunk_delay)  # 首块前延迟：cancel 时生成器在运行而非挂起
            try:
                yield "a"
                time.sleep(hang_after_first)  # 挂起点：cancel 的 gen.close() 在此投 GeneratorExit
                yield "b"
            finally:
                finally_ran.append(1)
        return producer

    def test_cancel_after_first_chunk_truncates(self):
        finally_ran = []
        h = IbStreamHandle(producer=self._slow_producer(finally_ran))
        # 等到首块到达（消费线程已越过 producer() 进入迭代）
        ok, chunk = (False, None)
        for _ in range(100):
            ok, chunk = h.recv_nowait()
            if ok:
                break
            time.sleep(0.01)
        assert ok and chunk == "a"
        h.cancel()
        h._thread.join(timeout=5)
        assert not h._thread.is_alive()
        assert h.is_done
        # 截断语义：无 error，result 为截断前缀（"a"），不含挂起后的 "b"
        assert h.result() == "a"
        # 生成器 finally 必须执行（资源闭环经 gen.close() 触发）
        assert finally_ran == [1]
        # live 注册表已移除
        assert h not in stream_mod._LIVE_HANDLES

    def test_cancel_before_first_chunk(self):
        finally_ran = []
        h = IbStreamHandle(producer=self._slow_producer(finally_ran, first_chunk_delay=0.2))
        time.sleep(0.05)  # 消费线程已进入 producer()（生成器运行中、未挂起）
        h.cancel()
        h._thread.join(timeout=5)
        assert not h._thread.is_alive()
        assert h.is_done
        assert h.result() == ""  # 零块产出 → 空前缀
        assert finally_ran == [1]

    def test_cancel_idempotent(self):
        finally_ran = []
        h = IbStreamHandle(producer=self._slow_producer(finally_ran))
        time.sleep(0.05)
        h.cancel()
        h.cancel()  # 幂等：二次调用无副作用
        h._thread.join(timeout=5)
        assert not h._thread.is_alive()
        assert h.is_done
        assert h.result() == ""

    def test_cancel_after_natural_completion_is_noop(self):
        h = IbStreamHandle(producer=lambda: (x for x in ["x", "y"]))
        assert h.result() == "xy"
        h.cancel()  # 已终结：无副作用
        assert h.is_done
        assert h.result() == "xy"

    def test_atexit_drain_abandoned_stream(self):
        """放弃的流（不 recv 不 cancel）经 atexit 路径被 drain：线程干净退出。"""
        finally_ran = []
        h = IbStreamHandle(producer=self._slow_producer(finally_ran, first_chunk_delay=0.05))
        time.sleep(0.05)  # 消费线程启动
        assert h in stream_mod._LIVE_HANDLES
        stream_mod._drain_live_streams()  # 直接执行 atexit 钩子路径
        h._thread.join(timeout=5)
        assert not h._thread.is_alive()
        assert h.is_done
        assert finally_ran == [1]
        assert h not in stream_mod._LIVE_HANDLES

    def test_producer_contract_non_generator_fail_fast(self):
        """producer 契约：返回非生成器 → 生产异常路径 fail-fast（result 重抛 TypeError）。"""
        h = IbStreamHandle(producer=lambda: iter(["a"]))
        with pytest.raises(TypeError):
            h.result()

    def test_live_registry_no_residue_after_fast_streams(self):
        """快速流（即时生成器）完全消费后 live 注册表零残留（登记先于线程启动）。"""
        baseline = len(stream_mod._LIVE_HANDLES)
        for _ in range(5):
            h = IbStreamHandle(producer=lambda: (x for x in ["a", "b"]))
            h.result()
        assert len(stream_mod._LIVE_HANDLES) == baseline


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
#
# stream_call / stream_channel 统一消费 LLMCallable 实例（行为值或用户
# llm 可调用类）——经统一装配入口（帧内 CPS）装配请求后流式执行；字符串形态
# （sys_prompt, user_prompt）已随旧机制删除（真删除，无双通道）。

class TestStreamCallLanguage:
    def test_stream_call_awaits_full_text(self, mock_server):
        code = (
            f'import ai\nai.set_config("{mock_server.url}/v1", "sk-test", "mock")\n'
            "class Steamer:\n"
            "    func __llm_call__(self) -> dict:\n"
            "        return {\"user_prompt\": \"MOCK:STREAM:Hello| World|!\"}\n"
            "Steamer s = Steamer()\n"
            "str full = await ai.stream_call(s)\n"
            "print(full)\n"
        )
        lines = run_ibci(code)
        assert lines == ["Hello World!"]

    def test_stream_call_auto_wait_on_assign(self, mock_server):
        code = (
            f'import ai\nai.set_config("{mock_server.url}/v1", "sk-test", "mock")\n'
            "class Steamer:\n"
            "    func __llm_call__(self) -> dict:\n"
            "        return {\"user_prompt\": \"MOCK:STREAM:Hi| there\"}\n"
            "Steamer s = Steamer()\n"
            "any h = ai.stream_call(s)\n"
            "str txt = (str)h\n"
            "print(txt)\n"
        )
        lines = run_ibci(code)
        assert lines == ["Hi there"]

    def test_stream_call_behavior_value(self, mock_server):
        """行为值经统一流式装配（语义槽路径）——装配的 user_prompt 交给 provider 流式执行。"""
        code = (
            f'import ai\nai.set_config("{mock_server.url}/v1", "sk-test", "mock")\n'
            "fn b = lambda(any x) -> str: @~ MOCK:STREAM:Hi| there ~\n"
            "str full = await ai.stream_call(b)\n"
            "print(full)\n"
        )
        lines = run_ibci(code)
        assert lines == ["Hi there"]


# ------------------------------------------------------------------ #
# 语言面：stream_channel（增量渲染）                                 #
# ------------------------------------------------------------------ #

class TestStreamChannelLanguage:
    def test_stream_channel_incremental_recv(self, mock_server):
        code = (
            f'import ai\nai.set_config("{mock_server.url}/v1", "sk-test", "mock")\n'
            "class Steamer:\n"
            "    func __llm_call__(self) -> dict:\n"
            "        return {\"user_prompt\": \"MOCK:STREAM:Hello| World|!\"}\n"
            "Steamer s = Steamer()\n"
            "chan chunks = ai.stream_channel(s)\n"
            "str c1 = chunks.recv()\n"
            "str c2 = chunks.recv()\n"
            "str c3 = chunks.recv()\n"
            "print(c1)\n"
            "print(c2)\n"
            "print(c3)\n"
        )
        lines = run_ibci(code)
        assert lines == ["Hello", " World", "!"]

    def test_stream_channel_incremental_recv_inprocess_mock(self):
        """进程内 mock（ai.set_mock_mode）路径：provider.stream 的 test_mode 分支
        尊重 MOCK:STREAM 分块，stream_channel 逐块 recv 与 HTTP mock 路径一致。"""
        code = (
            "import ai\n"
            "ai.set_mock_mode()\n"
            "class Steamer:\n"
            "    func __llm_call__(self) -> dict:\n"
            "        return {\"user_prompt\": \"MOCK:STREAM:Hello| World|!\"}\n"
            "Steamer s = Steamer()\n"
            "chan chunks = ai.stream_channel(s)\n"
            "str c1 = chunks.recv()\n"
            "str c2 = chunks.recv()\n"
            "str c3 = chunks.recv()\n"
            "print(c1)\n"
            "print(c2)\n"
            "print(c3)\n"
        )
        lines = run_ibci(code)
        assert lines == ["Hello", " World", "!"]
