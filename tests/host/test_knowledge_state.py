"""宿主面层：knowledge 状态保存/恢复（ihost.save_state/load_state）——R3-C5
迁移（原 test_knowledge_type.py 的 TestSaveLoadFidelity 两个测试，ihost =
宿主模块 → 源路由 Python → 宿主面层归类）。"""

from core.kernel.issue import InterpreterError

from tests.behavior.helpers import TESTS_ROOT

from core.engine import IBCIEngine


def _engine():
    return IBCIEngine(root_dir=TESTS_ROOT)


class TestSaveLoadFidelity:
    def test_state_roundtrip_same_file(self, tmp_path):
        state_path = str(tmp_path / "know_state.json")
        captured = []
        _engine().run_string(
            "import ihost\n"
            "func c(any x) -> bool:\n"
            "    return x.len() > 0\n"
            "knowledge kb = knowledge()\n"
            f'kb.store("k1", "value-one", c)\n'
            f'kb.amend("k1", "value-one-amended", "reason: amend before save")\n'
            f'ihost.save_state("{state_path}")\n'
            'kb.store("k2", "value-two", c)\n'
            f'ihost.load_state("{state_path}")\n'
            "int n = kb.len()\n"
            'str v1 = (str)kb.get("k1")\n'
            'list h = kb.history("k1")\n'
            'print("n=" + (str)n)\n'
            'print("v1=" + v1)\n'
            'print("events=" + (str)len(h))\n',
            output_callback=captured.append,
            silent=True,
        )
        out = "\n".join(captured)
        assert "n=1" in out, f"load 后回退快照（save 后变更丢弃）: {out}"
        assert "v1=value-one-amended" in out, f"值保真: {out}"
        assert "events=2" in out, f"审计事件流保真（store + amend）: {out}"

    def test_amend_after_restore_fail_fast(self, tmp_path):
        # 水化后谓词引用丢失 → amend 拒绝（已知边界：需重新 store）
        state_path = str(tmp_path / "know_state2.json")
        try:
            _engine().run_string(
                "import ihost\n"
                "func c(any x) -> bool:\n"
                "    return x.len() > 0\n"
                "knowledge kb = knowledge()\n"
                f'kb.store("k", "v1", c)\n'
                f'ihost.save_state("{state_path}")\n'
                f'ihost.load_state("{state_path}")\n'
                'kb.amend("k", "v2", "reason")\n',
                silent=True,
            )
            raise AssertionError("Expected KNW_CHECK_REJECTED after restore")
        except InterpreterError as e:
            assert e.error_code == "KNW_CHECK_REJECTED"
