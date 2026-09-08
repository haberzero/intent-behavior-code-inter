"""
tests/runtime/test_environment_type.py

environment 一等环境对象（B3）判别测试：

- frames 栈键值环境：get/set/pop/clear/len/contains/keys；
- 快照语义：fork 深拷贝（快照与原件双向隔离）；
- use 替换语义：fork 拷贝绑定（非引用——原件后续变异不泄漏）；
- 值隔离：容器值深拷贝存储（外部变异不污染环境）；
- 序列化 round-trip（save_state/load_state——frames 键值保真，
  含嵌套容器值）。
"""

import os

import pytest

from core.engine import IBCIEngine


@pytest.fixture
def engine():
    return IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)))


class TestEnvironmentBasics:
    def test_set_get(self, engine):
        out = []
        engine.run_string(
            "environment e = environment()\n"
            'e.set("mode", "draft")\n'
            'str v = (str)e.get("mode")\n'
            'print("v=" + v)\n',
            output_callback=out.append, silent=True)
        assert out and out[0].strip() == "v=draft"

    def test_missing_key_none(self, engine):
        out = []
        engine.run_string(
            "environment e = environment()\n"
            'bool none = e.get("missing") == None\n'
            'print("none=" + (str)none)\n',
            output_callback=out.append, silent=True)
        assert out and "none=True" in out[0]

    def test_len_contains_keys(self, engine):
        out = []
        engine.run_string(
            "environment e = environment()\n"
            'e.set("a", 1)\n'
            'e.set("b", 2)\n'
            'int n = e.len()\n'
            'bool ca = e.contains("a")\n'
            'bool cb = e.contains("zz")\n'
            'list ks = e.keys()\n'
            'print("n=" + (str)n + " ca=" + (str)ca + " cb=" + (str)cb + " ks=" + (str)ks)\n',
            output_callback=out.append, silent=True)
        assert out and "n=2 ca=True cb=False" in out[0] and "a" in out[0] and "b" in out[0]


class TestForkSnapshot:
    def test_fork_isolation(self, engine):
        """fork 深拷贝：快照上 set 不泄漏回原件（双向隔离）。"""
        out = []
        engine.run_string(
            "environment e = environment()\n"
            'e.set("mode", "draft")\n'
            "environment f = e.fork()\n"
            'f.set("mode", "final")\n'
            'str orig = (str)e.get("mode")\n'
            'str forked = (str)f.get("mode")\n'
            'bool iso = (orig == "draft") and (forked == "final")\n'
            'print("iso=" + (str)iso)\n',
            output_callback=out.append, silent=True)
        assert out and "iso=True" in out[0]


class TestUseReplace:
    def test_use_fork_semantics(self, engine):
        """use 以 fork 副本替换当前环境（非引用绑定——原件后续 set 不泄漏）。"""
        out = []
        engine.run_string(
            "environment e = environment()\n"
            'e.set("world", "garden")\n'
            "environment.use(e)\n"
            "environment cur = environment.get_current()\n"
            'str w = (str)cur.get("world")\n'
            'e.set("world", "void")\n'
            "environment cur2 = environment.get_current()\n"
            'str w2 = (str)cur2.get("world")\n'
            'print("w=" + w + " w2=" + w2)\n',
            output_callback=out.append, silent=True)
        # use 后原件变异不泄漏：cur/cur2 均为 garden
        assert out and "w=garden w2=garden" in out[0]

    def test_use_empty_clears(self, engine):
        out = []
        engine.run_string(
            "environment e = environment()\n"
            'e.set("k", 1)\n'
            "environment.use(e)\n"
            "environment empty = environment()\n"
            "environment.use(empty)\n"
            "environment cur = environment.get_current()\n"
            'bool gone = cur.get("k") == None\n'
            'print("gone=" + (str)gone)\n',
            output_callback=out.append, silent=True)
        assert out and "gone=True" in out[0]


class TestValueIsolation:
    def test_container_value_copied_in(self, engine):
        """容器值深拷贝存储：外部 list 变异不污染环境内值。"""
        out = []
        engine.run_string(
            "environment e = environment()\n"
            'list items = ["a"]\n'
            'e.set("items", items)\n'
            'items.append("b")\n'
            'list stored = e.get("items")\n'
            'int n = stored.len()\n'
            'print("n=" + (str)n)\n',
            output_callback=out.append, silent=True)
        # 外部 append 不污染：环境内仍为单元素
        assert out and "n=1" in out[0]


class TestSerializationRoundTrip:
    def test_frames_preserved(self, engine):
        """save_state/load_state：environment 实例 frames 键值保真（含嵌套容器）。"""
        out = []
        engine.run_string(
            "import ihost\n"
            "environment e = environment()\n"
            'e.set("mode", "draft")\n'
            'e.set("count", 7)\n'
            'list items = ["a", "b"]\n'
            'e.set("items", items)\n'
            'ihost.save_state("./logs/env_test_rt.json")\n'
            'ihost.load_state("./logs/env_test_rt.json")\n'
            'str m = (str)e.get("mode")\n'
            'int c = (int)e.get("count")\n'
            'list it = e.get("items")\n'
            'print("m=" + m + " c=" + (str)c + " it=" + (str)it)\n',
            output_callback=out.append, silent=True)
        assert out and "m=draft c=7 it=[a, b]" in out[0]
