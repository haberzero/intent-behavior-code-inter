"""
tests/runtime/test_comm_kernel.py
=================================

统一通信内核单元测试：CommBuffer / ChannelCore / SlotCore /
CommRegistry 的线程安全与语义。

锁定：
- CommBuffer：有界 send/recv、非阻塞、close 语义、qsize、多线程并发
- ChannelCore：stream/message/pubsub 三模式、subscribe 扇出、close
- SlotCore：get/set/update 原子读改写、并发 update 一致性
- CommRegistry：register/lookup/all/snapshot 线程安全
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from core.runtime.shared.comm.buffer import CommBuffer, CommClosedError
from core.runtime.shared.comm.channel import ChannelCore
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
        # 状态断言：双 close 后 send/recv 仍抛 CommClosedError（未因重复 close 复活）
        with pytest.raises(CommClosedError):
            b.send(1)
        with pytest.raises(CommClosedError):
            b.recv()

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

    def test_pubsub_send_nowait_no_subscribers_returns_false(self):
        """无订阅者时消息未投递给任何人 → send_nowait 返回 False（非丢弃报成功）。"""
        c = ChannelCore(mode="pubsub")
        assert c.send_nowait("m") is False

    def test_pubsub_bounded_subscriber(self):
        """subscribe(size) 可配置订阅者队列容量（size=0 无界，>0 有界）。"""
        c = ChannelCore(mode="pubsub")
        s = c.subscribe(size=1)
        c.send("a")
        assert c.send_nowait("b") is False  # 订阅者队列满，未投递
        assert s.recv() == "a"
        assert c.send_nowait("b") is True   # 消费后可再投递
        assert s.recv() == "b"

    def test_pubsub_recv_raises_clear_error(self):
        """pubsub 通道是广播器，直接 recv 明确报错（而非误导性 CommClosedError）。"""
        c = ChannelCore(mode="pubsub")
        with pytest.raises(ValueError):
            c.recv()
        with pytest.raises(ValueError):
            c.recv_nowait()

    def test_close_clears_subscribers(self):
        """close() 清空订阅者注册表，subscriber_count 如实归零。

        close() 关闭订阅者 buffer 并将订阅者移出 _subscribers；通道关闭后
        snapshot()["subscriber_count"] 应为 0，不残留已关订阅者。
        """
        c = ChannelCore(mode="pubsub")
        s1 = c.subscribe()
        s2 = c.subscribe()
        assert c.snapshot()["subscriber_count"] == 2
        c.close()
        snap = c.snapshot()
        assert snap["closed"] is True
        assert snap["subscriber_count"] == 0

    def test_send_skips_concurrently_closed_subscriber(self):
        """send fan-out 跳过已关闭订阅者，异常不泄漏给生产者。

        通道整体未关闭，但某订阅者并发 close：send 应跳过已关订阅者，
        不抛 CommClosedError，仍将消息投递给存活订阅者。
        """
        c = ChannelCore(mode="pubsub")
        alive = c.subscribe()
        closing = c.subscribe()
        closing.close()  # buffer 已关（模拟快照后并发 close 的已关状态）
        c.send("hello")
        assert alive.recv() == "hello"

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

    def test_cas_success(self):
        """单次 CAS：当前值匹配时写回成功。"""
        s = SlotCore("x", 10)
        assert s.cas(10, 11) is True
        assert s.get() == 11

    def test_cas_conflict_returns_false(self):
        """单次 CAS：当前值被并发修改时不写回，返回 False。"""
        s = SlotCore("x", 10)
        assert s.cas(99, 11) is False  # expected 不匹配，不写回
        assert s.get() == 10

    def test_cas_retry_loop(self):
        """CAS 冲突后基于最新值重试（与 _SlotUpdateWaitable 同构的循环）。"""
        s = SlotCore("score", 0)
        expected = s.get()
        while not s.cas(expected, expected + 1):
            expected = s.get()
        assert s.get() == 1

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


# ------------------------------------------------------------------ #
# ChannelRecvWaitable（统一执行地基：通信接收的 Waitable 投影）         #
# ------------------------------------------------------------------ #

class TestChannelRecvWaitable:
    """ChannelRecvWaitable：try_result 非阻塞取 / result 阻塞取 / 终态关闭。"""

    def test_try_result_not_ready_then_ready(self):
        c = ChannelCore(mode="message")
        w = c.recv_waitable()
        assert w.is_done is False
        assert w.try_result() == (False, None)
        c.send("a")
        assert w.is_done is True
        assert w.try_result() == (True, "a")

    def test_result_blocks_until_data(self):
        c = ChannelCore(mode="message")
        w = c.recv_waitable()

        def _send():
            time.sleep(0.05)
            c.send(7)

        threading.Thread(target=_send, daemon=True).start()
        assert w.result() == 7

    def test_closed_empty_try_result_raises(self):
        c = ChannelCore(mode="message")
        w = c.recv_waitable()
        c.close()
        with pytest.raises(CommClosedError):
            w.try_result()

    def test_closed_drains_remaining_before_raise(self):
        c = ChannelCore(mode="message")
        c.send(1)
        w = c.recv_waitable()
        assert w.try_result() == (True, 1)
        c.close()
        with pytest.raises(CommClosedError):
            w.try_result()

    def test_pubsub_recv_waitable_rejected(self):
        c = ChannelCore(mode="pubsub")
        with pytest.raises(ValueError):
            c.recv_waitable()

    def test_subscriber_view_recv_waitable(self):
        c = ChannelCore(mode="pubsub")
        sub = c.subscribe()
        w = sub.recv_waitable()
        c.send("m")
        assert w.try_result() == (True, "m")


# ------------------------------------------------------------------ #
# ChannelSendWaitable（B1：通信发送的 Waitable 投影，与 recv 对称）     #
# ------------------------------------------------------------------ #

class TestChannelSendWaitable:
    """ChannelSendWaitable：满时挂起、非满立即投递、终态关闭。"""

    def test_not_full_sends_immediately(self):
        c = ChannelCore(mode="message")
        w = c.send_waitable("a")
        assert w.is_done is True
        assert w.try_result() == (True, None)
        assert c.recv() == "a"

    def test_full_then_space_becomes_ready(self):
        c = ChannelCore(mode="message", buffer=1)
        c.send(1)
        w = c.send_waitable(2)
        assert w.is_done is False
        assert w.try_result() == (False, None)
        assert c.recv() == 1  # 腾出空间
        assert w.is_done is True
        assert w.try_result() == (True, None)
        assert c.recv() == 2

    def test_closed_raises(self):
        c = ChannelCore(mode="message")
        c.close()
        with pytest.raises(CommClosedError):
            c.send_waitable("a")

    def test_result_blocks_until_space(self):
        c = ChannelCore(mode="message", buffer=1)
        c.send(1)
        w = c.send_waitable(2)

        def _recv():
            time.sleep(0.05)
            return c.recv()

        t = threading.Thread(target=_recv, daemon=True)
        t.start()
        assert w.result() is None  # 阻塞投递，等待空间
        t.join()
        assert c.recv() == 2

    def test_pubsub_fanout_send_waitable(self):
        c = ChannelCore(mode="pubsub")
        s1 = c.subscribe()
        s2 = c.subscribe()
        w = c.send_waitable("m")
        assert w.try_result() == (True, None)
        assert s1.recv() == "m"
        assert s2.recv() == "m"

    def test_pubsub_no_subscribers_immediate(self):
        c = ChannelCore(mode="pubsub")
        w = c.send_waitable("m")
        assert w.is_done is True
        assert w.try_result() == (True, None)

    def test_pubsub_bounded_subscriber_full_pends(self):
        c = ChannelCore(mode="pubsub")
        s = c.subscribe(size=1)
        c.send("a")
        w = c.send_waitable("b")
        assert w.is_done is False
        assert w.try_result() == (False, None)
        assert s.recv() == "a"  # 腾出空间
        assert w.try_result() == (True, None)
        assert s.recv() == "b"
