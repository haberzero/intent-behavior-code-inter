"""
tests/compiler/test_import_position.py — import 位置契约（compile-only）。

``import`` 必须位于文件顶部；错位报 ``DEP_INVALID_IMPORT_POSITION``，
而非误导性的 ``SEM_UNDEFINED_SYMBOL``。运行时回归见 e2e/test_import_position_runtime.py
（mixed-concerns 拆分）。
"""

from tests.conftest import compile_or_errors, expect_compile_error


class TestImportPositionEnforcement:
    """``import`` 与 ``from ... import ...`` 必须位于所有可执行语句之前。"""

    def test_import_at_top_compiles_successfully(self):
        code = (
            "import ai\n"
            "import idbg\n"
            'ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'
            'str x = "hello"\n'
            "print(x)\n"
        )
        artifact, errors = compile_or_errors(code)
        assert artifact is not None, f"Expected success, got errors: {errors}"
        assert "DEP_INVALID_IMPORT_POSITION" not in errors

    def test_import_after_statement_reports_dep_003(self):
        code = (
            "import ai\n"
            'ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'
            'str x = "hello"\n'
            "print(x)\n"
            "import idbg\n"
        )
        expect_compile_error(code, "DEP_INVALID_IMPORT_POSITION")

    def test_from_import_after_statement_reports_dep_003(self):
        code = (
            "import ai\n"
            'ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'
            'str x = "hello"\n'
            "print(x)\n"
            "from idbg import show_intents\n"
        )
        expect_compile_error(code, "DEP_INVALID_IMPORT_POSITION")

    def test_misplaced_import_not_reported_as_sem_001(self):
        code = (
            "import ai\n"
            'ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'
            'str x = "hello"\n'
            "import idbg\n"
        )
        artifact, errors = compile_or_errors(code)
        assert artifact is None
        assert "DEP_INVALID_IMPORT_POSITION" in errors

    def test_comments_and_blank_lines_before_imports_ok(self):
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
        code = (
            'str x = "hello"\n'
            "print(x)\n"
            "import ai\n"
        )
        artifact, errors = compile_or_errors(code)
        assert artifact is None
        assert "DEP_INVALID_IMPORT_POSITION" in errors

    def test_correct_imports_followed_by_other_imports_after_code_reports_only_misplaced(self):
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
        assert "DEP_INVALID_IMPORT_POSITION" in errors
