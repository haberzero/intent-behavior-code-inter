"""
tests/runtime/test_vm_comm.py
=============================

PT-MT-3 VM 层并发/通信 e2e 测试。

锁定：
- chan 构造 + send/recv（语言面）
- slot 构造 + set/get（语言面）

线程（spawn/join/cancel）已被 thread 对象模型取代（任务 C/F），
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
