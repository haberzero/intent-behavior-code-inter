"""tests_v2/contracts/test_smoke.py — 契约层种子（证明黑盒 infra 可用；移植中替换）。"""

from tests_v2.conftest import expect_compile_error, run_ibci


class TestContractsSmoke:
    def test_print_basic(self):
        assert run_ibci('print("hi")\n') == ["hi"]

    def test_optional_rejects_none(self):
        expect_compile_error("int x = None\n", "SEM_TYPE_MISMATCH")
