"""
tests/runtime/test_observability.py
===================================

内省层测试：runtime.snapshot() + runtime.subscribe()。

锁定：
- iruntime 模块注册为 kernel-native，可 import
- snapshot() 返回结构化 dict（slots/vms/llm 等字段）
- subscribe() 返回 stream Channel，事件流送达（chan_created/slot_updated）
- 关键字作成员名（iruntime.snapshot 中 snapshot 是保留字）可被点访问
"""
from tests.conftest import run_ibci


class TestSnapshotE2E:
    def test_snapshot_returns_dict_with_slots(self):
        lines = run_ibci("""
import iruntime
slot st = slot("score", 42)
dict snap = iruntime.snapshot()
print(snap)
""")
        assert len(lines) == 1
        # snapshot dict 应含 slots（IBCI dict 打印格式）
        assert "slots" in lines[0]
        assert "score" in lines[0]

    def test_snapshot_has_llm_section(self):
        lines = run_ibci("""
import iruntime
dict snap = iruntime.snapshot()
print(snap)
""")
        assert "llm" in lines[0]
        assert "tasks" in lines[0]
        assert "channels" in lines[0]

    def test_snapshot_collects_module_variables(self):
        """snapshot()[\"vars\"] 收集用户变量（统一变量视图；回归：消费端曾按原始值误读富 dict 而恒空）。"""
        lines = run_ibci("""
import iruntime
int x = 42
str s = "hi"
list[int] l = [1, 2]
dict snap = iruntime.snapshot()
print(snap["vars"])
""")
        assert len(lines) == 1
        assert "x" in lines[0] and "42" in lines[0]
        assert "s" in lines[0] and "hi" in lines[0]
        assert "l" in lines[0] and "[1, 2]" in lines[0]

    def test_snapshot_tracks_named_channel(self):
        lines = run_ibci("""
import iruntime
chan c = chan(str, "stream", name="my_ch")
dict snap = iruntime.snapshot()
print(snap)
""")
        assert "my_ch" in lines[0]


class TestSubscribeE2E:
    def test_subscribe_receives_chan_created(self):
        lines = run_ibci("""
import iruntime
chan ev = iruntime.subscribe()
chan c = chan(str, "stream")
dict e = ev.recv()
print(e)
""")
        assert len(lines) == 1
        assert "chan_created" in lines[0]

    def test_subscribe_receives_slot_updated(self):
        lines = run_ibci("""
import iruntime
chan ev = iruntime.subscribe()
slot st = slot("score", 1)
dict e = ev.recv()
print(e)
""")
        assert "slot_updated" in lines[0]
        assert "score" in lines[0]


class TestKeywordMemberAccess:
    def test_keyword_as_member_name(self):
        """``snapshot`` 是保留关键字，但可作为模块成员名（iruntime.snapshot）。"""
        lines = run_ibci("""
import iruntime
dict snap = iruntime.snapshot()
print(snap)
""")
        assert len(lines) == 1
        assert "llm" in lines[0]
