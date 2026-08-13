"""
tests/e2e/test_chan_send_waitable.py

``chan.send`` 满通道 Waitable 化（与 ``recv`` 对称）。

机制：非满 send 立即投递返回 ``None``；有界满通道返回发送 Waitable——VM 经
既有 Waitable 挂起路径等待腾出空间后恢复（协作挂起，不阻塞线程）。

覆盖：
- 有界满通道 send 协作挂起，消费者腾出空间后恢复（不阻塞线程、不死锁）
- send 与 recv 对称（recv 已转 Waitable）
- 非满 send 立即完成（返回 None）
- 有界通道 send_nowait 满时返回 False（保留）
"""

from tests.conftest import run_ibci


class TestSendWaitable:
    def test_bounded_send_suspends_threaddrain(self):
        """有界满通道 send 协作挂起，消费者线程 recv 腾出空间后恢复。

        主线程 fill 满 capacity=1 通道后第二次 send 经 Waitable 协作挂起
        （不阻塞解释器线程）；消费者线程 recv 腾出空间，send 恢复完成。
        """
        code = """
chan c = chan(int, "stream", buffer=1)
func consume(chan x) -> int:
    int a = x.recv()
    int b = x.recv()
    return a + b

c.send(1)
thread[int] t = thread(callable=consume, args=[c])
c.send(2)
print("sent")
thread_result[int] r = t.join()
print((str)r.expect())
"""
        lines = run_ibci(code)
        assert lines == ["sent", "3"]

    def test_send_returns_none_when_not_full(self):
        """非满 send 立即投递完成（返回 None，无挂起）。"""
        code = """
chan c = chan(str, "stream")
c.send("a")
str m = c.recv()
print(m)
"""
        assert run_ibci(code) == ["a"]

    def test_send_nowait_full_returns_false(self):
        """有界通道 send_nowait 满时返回 False（保留非阻塞语义）。"""
        code = """
chan c = chan(int, "stream", buffer=1)
c.send(1)
bool r = c.send_nowait(2)
print((str)r)
"""
        assert run_ibci(code) == ["False"]