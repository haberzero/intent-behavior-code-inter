"""
tests_v2/e2e/test_kernel_native.py
====================================

端到端回归：ai/ihost/idbg/isys 提升为 kernel-native 后，
既有 IBCI 层 API 行为保持不变。
"""
from core.engine import IBCIEngine
from tests_v2.conftest import AI_MOCK_PREFIX, run_ibci


class TestAINative:
    """ai 模块 kernel-native 后 MOCK 调用链仍工作。"""

    def test_ai_mock_complete(self):
        code = (
            AI_MOCK_PREFIX
            + "str answer = @~What is 2+2? Please answer with only the number.~\n"
            + "print(answer)\n"
        )
        out = run_ibci(code)
        # MOCK 模式下会返回非空字符串
        assert any(line.strip() for line in out)


class TestIHostNative:
    """ihost 模块 kernel-native 后隔离执行仍工作。"""

    def test_ihost_run_isolated_still_works(self, tmp_path, monkeypatch, capsys):
        parent_dir = tmp_path / "isohome"
        parent_dir.mkdir()
        (parent_dir / "child.ibci").write_text(
            AI_MOCK_PREFIX
            + 'print("child_ran")\n',
            encoding="utf-8",
        )
        parent_path = parent_dir / "parent.ibci"
        parent_path.write_text(
            "import ihost\n"
            'dict policy = {"isolated": True, "registry_isolation": True, "inherit_variables": False}\n'
            'dict res = ihost.run_isolated("child.ibci", policy)\n'
            'print("parent_done")\n',
            encoding="utf-8",
        )

        other_dir = tmp_path / "elsewhere"
        other_dir.mkdir()
        monkeypatch.chdir(other_dir)

        parent_out = []
        eng = IBCIEngine(root_dir=str(parent_dir), auto_sniff=False)
        eng.run(str(parent_path), output_callback=lambda s: parent_out.append(str(s)), silent=True)
        captured = capsys.readouterr()
        assert "child_ran" in captured.out
        assert "parent_done" in parent_out


class TestIdbgAndIsysNative:
    """idbg / isys 模块 kernel-native 后仍可 import 调用。"""

    def test_idbg_vars_available(self):
        code = (
            "import idbg\n"
            "int x = 42\n"
            "dict d = idbg.vars()\n"
            "print((str)d.get(\"x\"))\n"
        )
        out = run_ibci(code)
        assert any("42" in line for line in out)

    def test_isys_entry_dir_available(self):
        code = (
            "import isys\n"
            "str d = isys.entry_dir()\n"
            "print(d)\n"
        )
        out = run_ibci(code)
        # run_string 入口目录 = project_root，至少应返回非空字符串
        assert any(line.strip() for line in out)
