"""
tests/runtime/test_runtime_configure.py
=======================================

控制层测试：runtime.configure(...) 统一启停。

锁定：
- 默认值（parallel/stream/observability 开，debug 关）
- configure(parallel=False, debug=True) 生效并返回 effective config
- observability 关闭后事件流抑制（chan_created 不再送达）
- get_config 读取生效配置
"""
from tests.conftest import run_ibci


class TestDefaults:
    def test_get_config_defaults(self):
        lines = run_ibci("""
import iruntime
dict cfg = iruntime.get_config()
print(cfg)
""")
        assert len(lines) == 1
        assert "parallel" in lines[0]
        assert "debug" in lines[0]

    def test_configure_returns_effective(self):
        lines = run_ibci("""
import iruntime
dict eff = iruntime.configure(parallel=False, debug=True)
print(eff)
""")
        assert len(lines) == 1
        assert "False" in lines[0]  # parallel 已关
        assert "True" in lines[0]   # debug 已开


class TestObservabilityGate:
    def test_observability_off_suppresses_events(self):
        """observability 关闭后 chan 创建不再产生事件（recv_nowait 返回 None）。"""
        lines = run_ibci("""
import iruntime
iruntime.configure(observability=False)
subscriber ev = iruntime.subscribe()
chan c = chan(str, "stream")
any e = ev.recv_nowait()
print(e)
""")
        assert lines == ["None"]

    def test_observability_on_emits_events(self):
        """observability 默认开启时 chan 创建产生事件。"""
        lines = run_ibci("""
import iruntime
subscriber ev = iruntime.subscribe()
chan c = chan(str, "stream")
dict e = ev.recv()
print(e)
""")
        assert "chan_created" in lines[0]


class TestConfigPersistence:
    def test_config_survives_subsequent_queries(self):
        """configure 后的配置在后续 get_config 中持久生效。"""
        lines = run_ibci("""
import iruntime
iruntime.configure(debug=True)
dict cfg = iruntime.get_config()
print(cfg)
""")
        assert "True" in lines[0]
