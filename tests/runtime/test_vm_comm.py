"""
tests/runtime/test_vm_comm.py
=============================

VM 层并发/通信 e2e 测试。

锁定：
- chan 构造 + send/recv（语言面）
- slot 构造 + set/get（语言面）

线程（spawn/join/cancel）已被 thread 对象模型取代，
其测试见 test_thread_model.py / test_vm_instance.py。
"""
from tests.conftest import run_ibci


class TestChannelE2E:
    def test_chan_send_recv(self):
        lines = run_ibci("""
chan c = chan(str, "stream")
c.send("hello")
str msg = c.recv()
print(msg)
""")
        assert lines == ["hello"]

    def test_chan_multiple_messages(self):
        lines = run_ibci("""
chan c = chan(int, "message")
c.send(1)
c.send(2)
int a = c.recv()
int b = c.recv()
print((str)a)
print((str)b)
""")
        assert lines == ["1", "2"]

    def test_chan_recv_nonblocking_empty(self):
        lines = run_ibci("""
chan c = chan(str, "stream")
any none = c.recv_nonblocking()
print(none)
""")
        # 空缓冲非阻塞返回 None
        assert lines == ["None"]


class TestSlotE2E:
    def test_slot_get_set(self):
        lines = run_ibci("""
slot st = slot("score", 0)
st.set(42)
int v = st.get()
print((str)v)
""")
        assert lines == ["42"]


class TestChannelPubSubE2E:
    """pubsub 语言层（subscribe → subscriber 端点 + send_nowait 语义）。"""

    def test_pubsub_subscribe_recv(self):
        lines = run_ibci("""
chan c = chan(str, "pubsub")
subscriber sub = c.subscribe()
c.send("hello")
str msg = sub.recv()
print(msg)
""")
        assert lines == ["hello"]

    def test_pubsub_fanout(self):
        lines = run_ibci("""
chan c = chan(int, "pubsub")
subscriber a = c.subscribe()
subscriber b = c.subscribe()
c.send(7)
print((str)a.recv())
print((str)b.recv())
""")
        assert lines == ["7", "7"]

    def test_pubsub_send_nowait_no_subscribers_false(self):
        lines = run_ibci("""
chan c = chan(int, "pubsub")
bool r = c.send_nowait(1)
print((str)r)
""")
        assert lines == ["False"]

    def test_pubsub_bounded_subscriber(self):
        lines = run_ibci("""
chan c = chan(int, "pubsub")
subscriber sub = c.subscribe(1)
c.send(1)
bool r = c.send_nowait(2)
print((str)r)
print((str)sub.recv())
""")
        assert lines == ["False", "1"]


def test_comm_objects_use_create_blank_protocol():
    """comm 句柄对象经 _create_blank 统一构造协议创建实例。"""
    from core.runtime.objects.kernel import IbChannel, IbSlot, IbSubscriber
    assert isinstance(IbChannel._create_blank(None), IbChannel)
    assert isinstance(IbSlot._create_blank(None), IbSlot)
    assert isinstance(IbSubscriber._create_blank(None), IbSubscriber)
