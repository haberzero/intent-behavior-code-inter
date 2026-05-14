"""
tests/compiler/test_import_position.py
=======================================

H2 回归：``import`` 必须位于文件顶部。如果在其它语句之后出现，
编译器应明确报 ``DEP_003 DEP_INVALID_IMPORT_POSITION``，而不是
误导性的 ``SEM_001 Module 'X' not found``。

详见 docs/COMPLETED.md 2026-05-14 锚点。
"""

from tests.conftest import compile_or_errors, expect_compile_error, run_ibci


class TestImportPositionEnforcement:
    """``import`` 与 ``from ... import ...`` 必须位于所有可执行语句之前。"""

    def test_import_at_top_compiles_successfully(self):
        """正常顺序：imports 全部在顶部 → 无错误。"""
        code = (
            "import ai\n"
            "import idbg\n"
            'ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'
            'str x = "hello"\n'
            "print(x)\n"
        )
        artifact, errors = compile_or_errors(code)
        assert artifact is not None, f"Expected success, got errors: {errors}"
        assert "DEP_003" not in errors

    def test_import_after_statement_reports_dep_003(self):
        """import 出现在普通语句之后 → DEP_003，而非 SEM_001。"""
        code = (
            "import ai\n"
            'ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'
            'str x = "hello"\n'
            "print(x)\n"
            "import idbg\n"
        )
        expect_compile_error(code, "DEP_003")

    def test_from_import_after_statement_reports_dep_003(self):
        """from-import 同样受位置约束。"""
        code = (
            "import ai\n"
            'ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'
            'str x = "hello"\n'
            "print(x)\n"
            "from idbg import show_intents\n"
        )
        expect_compile_error(code, "DEP_003")

    def test_misplaced_import_not_reported_as_sem_001(self):
        """关键断言：misplaced import 必须报 DEP_003，不能仅报 SEM_001
        模块未找到——否则用户会以为是插件路径出问题。"""
        code = (
            "import ai\n"
            'ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'
            'str x = "hello"\n'
            "import idbg\n"
        )
        artifact, errors = compile_or_errors(code)
        assert artifact is None
        assert "DEP_003" in errors

    def test_comments_and_blank_lines_before_imports_ok(self):
        """import 之前允许出现注释、空行。"""
        code = (
            "# header comment\n"
            "\n"
            "# more comments\n"
            "import ai\n"
            'ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'
            'print("ok")\n'
        )
        artifact, errors = compile_or_errors(code)
        assert artifact is not None, f"Expected success, got: {errors}"

    def test_misplaced_import_zero_top_imports_still_reports(self):
        """文件中**只有一个 misplaced import**（没有顶部 import）也要报错。"""
        code = (
            'str x = "hello"\n'
            "print(x)\n"
            "import ai\n"
        )
        artifact, errors = compile_or_errors(code)
        assert artifact is None
        assert "DEP_003" in errors

    def test_correct_imports_followed_by_other_imports_after_code_reports_only_misplaced(self):
        """混合：顶部正常 + 中间错位 + 后面又错位 — 只有错位的报 DEP_003。"""
        code = (
            "import ai\n"
            'ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'
            'print("a")\n'
            "import idbg\n"
            'print("b")\n'
            "import file\n"
        )
        artifact, errors = compile_or_errors(code)
        assert artifact is None
        assert "DEP_003" in errors


class TestImportPositionRuntimeRegression:
    """正常顺序的 import 仍然产生可工作的运行时（避免回归）。"""

    def test_top_imports_program_runs(self):
        code = (
            "import ai\n"
            "import idbg\n"
            'ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'
            'str x = "hello"\n'
            "print(x)\n"
            "idbg.show_intents()\n"
        )
        lines = run_ibci(code)
        assert "hello" in lines
