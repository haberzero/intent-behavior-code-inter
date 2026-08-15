"""
tests/e2e/test_protocol_syntax_runtime.py — protocol declaration runtime no-op.
"""

from tests.conftest import run_ibci


class TestProtocolDeclarationRuntime:
    def test_protocol_declaration_runs_as_noop(self):
        code = """
protocol Greeter:
    func greet(self) -> str:
        pass

print("ok")
"""
        assert run_ibci(code) == ["ok"]

    def test_protocol_with_multiple_methods_runs(self):
        code = """
protocol Serializable:
    func to_dict(self) -> dict:
        pass
    func from_dict(self, dict raw) -> any:
        pass

print("ok")
"""
        assert run_ibci(code) == ["ok"]
