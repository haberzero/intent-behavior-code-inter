"""
tests/runtime/test_comm_kernel.py
=================================

PT-MT-3 统一通信内核单元测试：CommBuffer / ChannelCore / SignalCore /
SlotCore / CommRegistry 的线程安全与语义。

锁定：
- CommBuffer：有界 send/recv、非阻塞、close 语义、qsize、多线程并发
- ChannelCore：stream/message/pubsub 三模式、subscribe 扇出、close
- SignalCore：kind 校验、定向/广播字段、不可变
- SlotCore：get/set/update 原子读改写、并发 update 一致性
- CommRegistry：register/lookup/all/snapshot 线程安全
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from core.runtime.shared.comm.buffer import CommBuffer, CommClosedError
from core.runtime.shared.comm.channel import ChannelCore
from core.runtime.shared.comm.signal import SignalCore
from core.runtime.shared.comm.slot import SlotCore
from core.runtime.shared.comm.registry import CommRegistry


# ------------------------------------------------------------------ #
# CommBuffer                                                          #
# ------------------------------------------------------------------ #

class TestCommBuffer:
    def test_send_recv_fifo(self):
        b = CommBuffer(0)
        b.send(1)
        b.send(2)
        assert b.recv() == 1
        assert b.recv() == 2

    def test_send_nowait_when_full(self):
        b = CommBuffer(1)
        assert b.send_nowait(1) is True
        assert b.send_nowait(2) is False  # 满

    def test_recv_nowait_when_empty(self):
        b = CommBuffer(0)
        ok, item = b.recv_nowait()
        assert ok is False
        assert item is None

    def test_close_then_send_raises(self):
        b = CommBuffer(0)
        b.close()
        with pytest.raises(CommClosedError):
            b.send(1)

    def test_close_then_recv_drains_then_raises(self):
        b = CommBuffer(0)
        b.send(1)
        b.close()
        assert b.recv() == 1  # 排空剩余
        with pytest.raises(CommClosedError):
            b.recv()

    def test_qsize(self):
        b = CommBuffer(0)
        b.send(1)
        b.send(2)
        assert b.qsize == 2

    def test_close_idempotent(self):
        b = CommBuffer(0)
        b.close()
        b.close()  # 幂等

    def test_send_recv_concurrent(self):
        """多生产者/多消费者并发：总吞吐一致、无丢失。"""
        b = CommBuffer(0)
        n = 500
        sent = []

        def producer(start):
            for i in range(start, start + n):
                b.send(i)

        def consumer():
            got = []
            while len(got) < 2 * n:
                try:
                    got.append(b.recv())
                except CommClosedError:
                    break
            return got

        with ThreadPoolExecutor(max_workers=3) as pool:
            f1 = pool.submit(producer, 0)
            f2 = pool.submit(producer, n)
            f3 = pool.submit(consumer)
            f1.result()
            f2.result()
            got = f3.result()
        assert sorted(got) == list(range(2 * n))


# ------------------------------------------------------------------ #
# ChannelCore                                                         #
# ------------------------------------------------------------------ #

class TestChannelStream:
    def test_stream_fifo(self):
        c = ChannelCore(mode="stream")
        c.send("a")
        c.send("b")
        assert c.recv() == "a"
        assert c.recv() == "b"

    def test_stream_close(self):
        c = ChannelCore(mode="stream")
        c.send("x")
        c.close()
        assert c.closed
        assert c.recv() == "x"
        with pytest.raises(CommClosedError):
            c.recv()


class TestChannelMessage:
    def test_message_queue(self):
        c = ChannelCore(mode="message")
        for i in range(10):
            c.send(i)
        assert [c.recv() for _ in range(10)] == list(range(10))


class TestChannelPubSub:
    def test_pubsub_fanout(self):
        c = ChannelCore(mode="pubsub")
        s1 = c.subscribe()
        s2 = c.subscribe()
        c.send("m1")
        c.send("m2")
        assert s1.recv() == "m1"
        assert s2.recv() == "m1"
        assert s1.recv() == "m2"
        assert s2.recv() == "m2"

    def test_pubsub_subscriber_drain(self):
        """订阅者关闭后不再收到后续消息。"""
        c = ChannelCore(mode="pubsub")
        s1 = c.subscribe()
        s2 = c.subscribe()
        s1.close()
        c.send("m")
        ok, _ = s1.recv_nowait()
        assert ok is False  # s1 已关闭
        assert s2.recv() == "m"

    def test_subscribe_rejected_non_pubsub(self):
        c = ChannelCore(mode="message")
        with pytest.raises(ValueError):
            c.subscribe()

    def test_pubsub_close_closes_subscribers(self):
        c = ChannelCore(mode="pubsub")
        s = c.subscribe()
        c.close()
        assert s.closed

    def test_invalid_mode(self):
        with pytest.raises(ValueError):
            ChannelCore(mode="bogus")


class TestChannelSnapshot:
    def test_snapshot_fields(self):
        c = ChannelCore(mode="message", buffer=3, name="ch")
        snap = c.snapshot()
        assert snap["mode"] == "message"
        assert snap["name"] == "ch"
        assert snap["closed"] is False


# ------------------------------------------------------------------ #
# SignalCore                                                          #
# ------------------------------------------------------------------ #

class TestSignal:
    def test_kind_validated(self):
        with pytest.raises(ValueError):
            SignalCore(kind="bogus")

    def test_kinds(self):
        for k in ("cancel", "pause", "resume", "config_change"):
            s = SignalCore(kind=k)
            assert s.kind == k

    def test_target_default_none(self):
        s = SignalCore(kind="cancel")
        assert s.target is None  # 广播

    def test_target_directed(self):
        s = SignalCore(kind="cancel", target="handle_123")
        assert s.target == "handle_123"

    def test_frozen(self):
        s = SignalCore(kind="cancel")
        with pytest.raises(Exception):
            s.kind = "pause"  # frozen dataclass 不可变

    def test_to_dict(self):
        s = SignalCore(kind="config_change", payload={"parallel": False})
        d = s.to_dict()
        assert d["kind"] == "config_change"
        assert d["payload"] == {"parallel": False}


# ------------------------------------------------------------------ #
# SlotCore                                                           #
# ------------------------------------------------------------------ #

class TestSlot:
    def test_get_set(self):
        s = SlotCore("score", 0)
        assert s.get() == 0
        s.set(42)
        assert s.get() == 42

    def test_update_atomic(self):
        s = SlotCore("count", 0)
        s.update(lambda v: v + 1)
        assert s.get() == 1

    def test_concurrent_update(self):
        """100 线程各 +1：最终值 = 100（原子读改写无丢失）。"""
        s = SlotCore("count", 0)
        n = 100

        def inc():
            s.update(lambda v: v + 1)

        threads = [threading.Thread(target=inc) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert s.get() == n

    def test_update_exception_no_write(self):
        s = SlotCore("x", 1)
        with pytest.raises(ValueError):
            s.update(lambda v: (_ for _ in ()).throw(ValueError("boom")))
        assert s.get() == 1

    def test_snapshot(self):
        s = SlotCore("name", "v")
        assert s.snapshot() == {"name": "name", "value": "v"}


# ------------------------------------------------------------------ #
# CommRegistry                                                       #
# ------------------------------------------------------------------ #

class TestCommRegistry:
    def test_register_lookup(self):
        r = CommRegistry()
        c = ChannelCore(mode="message")
        r.register("my_chan", c, "chan")
        assert r.lookup("my_chan") is c
        assert r.kind_of("my_chan") == "chan"

    def test_all_by_kind(self):
        r = CommRegistry()
        r.register("c1", ChannelCore(), "chan")
        r.register("s1", SlotCore("s"), "slot")
        assert len(r.all("chan")) == 1
        assert len(r.all("slot")) == 1
        assert len(r.all()) == 2

    def test_unregister(self):
        r = CommRegistry()
        r.register("x", ChannelCore(), "chan")
        r.unregister("x")
        assert r.lookup("x") is None

    def test_snapshot(self):
        r = CommRegistry()
        c = ChannelCore(mode="message", name="named")
        r.register("ch", c, "chan")
        snap = r.snapshot()
        assert "ch" in snap
        assert snap["ch"]["mode"] == "message"

    def test_auto_name_when_empty(self):
        r = CommRegistry()
        r.register("", ChannelCore(), "chan")
        assert len(r.names()) == 1
