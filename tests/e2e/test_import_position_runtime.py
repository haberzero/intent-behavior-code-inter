"""
tests/e2e/test_import_position_runtime.py — 正常顺序 import 的运行时行为。

自原 compiler/test_import_position.py 拆分（mixed-concerns：完整程序运行时
行为归 e2e/，编译期契约归 compiler/test_import_position.py）。
"""

from tests.conftest import run_ibci


class TestImportPositionRuntimeRegression:
    """正常顺序的 import 产生可工作的运行时。"""

    def test_top_imports_program_runs(self):
        code = (
            "import ai\n"
            "import idbg\n"
            'ai.set_mock_mode()\n'
            'str x = "hello"\n'
            "print(x)\n"
            "idbg.show_intents()\n"
        )
        lines = run_ibci(code)
        assert "hello" in lines
