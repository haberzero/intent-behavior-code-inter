"""
tests/compiler/semantic/test_diagnostic_locations.py

语义期诊断的 ibci 源位置契约：pass 的 error()/warn() 从 AST 节点提取
解析期附着的 loc（单一权威源），诊断携带真实行/列而非 0:0。
渲染侧（DiagnosticFormatter）消费 line/column 产出源行上下文。
"""

import os

import pytest

from core.engine import IBCIEngine
from core.kernel.issue import CompilerError


@pytest.fixture
def engine():
    return IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)))


def _errors(engine, code):
    with pytest.raises(CompilerError) as exc:
        engine.compile_string(code, silent=True)
    return exc.value.diagnostics


class TestSemanticDiagnosticLocations:
    def test_undefined_symbol_carries_line_and_column(self, engine):
        diags = _errors(engine, "x = 1\ny = undef")
        sem = [d for d in diags if d.code == "SEM_UNDEFINED_SYMBOL"]
        assert sem, "expected SEM_UNDEFINED_SYMBOL diagnostic"
        loc = sem[0].location
        assert loc is not None
        assert loc.line == 2
        assert loc.column == 5  # 'undef' 的列位置（1-based）

    def test_dict_key_type_mismatch_carries_line(self, engine):
        diags = _errors(engine, "dict[str,int] d = {}\nd[42] = 1")
        sem = [d for d in diags if d.code == "SEM_TYPE_MISMATCH"]
        assert sem, "expected SEM_TYPE_MISMATCH diagnostic"
        assert sem[0].location is not None
        assert sem[0].location.line == 2

    def test_assignment_type_mismatch_carries_line(self, engine):
        # int 变量接收 str：赋值点诊断定位到赋值行
        diags = _errors(engine, "int n = 1\nint m = \"nope\"")
        sem = [d for d in diags if d.code == "SEM_TYPE_MISMATCH"]
        assert sem, "expected SEM_TYPE_MISMATCH diagnostic"
        assert sem[0].location is not None
        assert sem[0].location.line == 2

    def test_first_line_error_line_is_one(self, engine):
        diags = _errors(engine, "y = undef")
        sem = [d for d in diags if d.code == "SEM_UNDEFINED_SYMBOL"]
        assert sem[0].location is not None
        assert sem[0].location.line == 1
