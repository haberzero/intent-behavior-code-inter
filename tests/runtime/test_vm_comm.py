"""
tests/runtime/test_vm_comm.py
=============================

PT-MT-3 VM 层并发/通信 e2e 测试。

锁定：
- chan 构造 + send/recv（语言面）
- slot 构造 + set/get（语言面）
- signal 构造
- spawn/join（延迟任务模型：join 触发求值）
- cancel（协作式）
- pubsub 模式 subscribe（经 IbChannel 底层）
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


class TestSignalE2E:
    def test_signal_create(self):
        lines = run_ibci("""
signal s = signal("cancel")
print("ok")
""")
        assert lines == ["ok"]


class TestSpawnJoinE2E:
    def test_spawn_join_function(self):
        lines = run_ibci("""
func compute(str x) -> int:
    return 42
task t = spawn compute("x")
int r = join t
print((str)r)
""")
        assert lines == ["42"]

    def test_spawn_join_lambda(self):
        lines = run_ibci("""
task t = spawn lambda() -> int: 7
int r = join t
print((str)r)
""")
        assert lines == ["7"]

    def test_cancel_task(self):
        lines = run_ibci("""
func compute(str x) -> int:
    return 42
task t = spawn compute("x")
cancel t
print("cancelled")
""")
        assert lines == ["cancelled"]
