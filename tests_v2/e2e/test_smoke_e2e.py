"""tests_v2/e2e/test_smoke.py — e2e 层种子（完整程序黑盒；移植中替换）。"""

from tests_v2.conftest import run_ibci


class TestE2eSmoke:
    def test_hello_world(self):
        assert run_ibci('print("hello")\n') == ["hello"]

    def test_vars_and_types(self):
        assert run_ibci('int x = 42\nprint(x)\n') == ["42"]
