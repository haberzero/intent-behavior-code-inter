"""
tests/compiler/test_parse_error_attribution.py

解析错误位置归位契约（P2 修复面）：

- 跨行续行态（括号构造未闭合、NEWLINE 被词法器吞掉）下，错误卡住点落在
  续行行会误导用户——错误位置归位到**构造起点**（最内层未闭合开括号
  位置，词法器 paren_stack 单一权威源）；
- 同行错误维持卡住点（列号精确，不劣化）；
- 废弃 cast（(Type) @~...~）位置 = cast 起点（`(`），非 speculate 消费
  后的 peek；
- Token.continuation_start 标记仅对跨行 token 附着（同行不标记）。
"""
import os

import pytest

from core.compiler.lexer.lexer import Lexer
from core.engine import IBCIEngine
from core.kernel.issue import CompilerError
from core.compiler.diagnostics.formatter import DiagnosticFormatter


@pytest.fixture
def engine():
    return IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)))


def _first_error(engine, code):
    with pytest.raises(CompilerError) as exc:
        engine.compile_string(code, silent=True)
    diags = exc.value.diagnostics
    assert diags, "expected a compile error"
    return diags[0]


class TestCrossLineAttribution:
    def test_missing_closing_paren_attributed_to_construct_start(self, engine):
        # 行 1 print( 未闭合（缺 )）→ 解析卡住点在行 2 → 归位到行 1 的 (
        diag = _first_error(
            engine, 'print("a=" + (str)1\nprint("DONE")\n'
        )
        assert diag.location is not None
        assert diag.location.line == 1
        assert diag.location.column == 6  # print 的 ( 位置

    def test_missing_paren_innermost_open_paren(self, engine):
        # 最内层未闭合构造位置（嵌套括号：内层已闭合、外层未闭合）
        diag = _first_error(
            engine, 'int n = 1\nprint("a=" + (str)x\nprint("DONE")\n'
        )
        assert diag.location is not None
        assert diag.location.line == 2
        assert diag.location.column == 6

    def test_same_line_error_keeps_stuck_point(self, engine):
        # 同行错误（无续行吞行）：卡住点维持（列号精确，不归位）
        diag = _first_error(engine, "print(1 +\n")
        assert diag.location is not None
        assert diag.location.line == 1
        # 卡住点 = 行末 NEWLINE 之前（同行，列号指向出错处附近）
        assert diag.location.column >= 1

    def test_deprecated_cast_position_is_cast_start(self, engine):
        # 废弃 cast：位置 = cast 起点 (（第 1 行第 5 列 x = ( ），
        # 非 speculate 消费 @~...~ 块后的 peek
        diag = _first_error(engine, "x = (int) @~ do it ~\nprint(x)\n")
        assert diag.location is not None
        assert diag.location.line == 1
        assert diag.location.column == 5


class TestContinuationMark:
    def test_cross_line_tokens_carry_continuation_start(self):
        from core.compiler.diagnostics.issue_tracker import IssueTracker
        src = 'print("a=" + (str)1\nprint("DONE")\n'
        lexer = Lexer(src, IssueTracker("debug"))
        tokens = lexer.tokenize()
        # 续行行的首个代码 token 带 continuation_start（= 行 1 的未闭合 (
        # 位置）；行内新开的括号（其自身成为新构造起点）不标记——同行
        # 错误卡住点列号精确，标记仅服务于跨行归位。
        line2_tokens = [t for t in tokens if t.line == 2]
        assert line2_tokens, "expected line 2 tokens"
        first = line2_tokens[0]
        assert first.continuation_start is not None
        assert first.continuation_start[0] == 1
        assert first.continuation_start[1] == 6  # 行 1 print 的 ( 列

    def test_same_line_tokens_not_marked(self):
        from core.compiler.diagnostics.issue_tracker import IssueTracker
        src = 'int n = (1 + 2)\n'
        lexer = Lexer(src, IssueTracker("debug"))
        tokens = lexer.tokenize()
        # 行内括号（同行闭合）：token 不附标记（同行错误卡住点列号精确）
        paren_tokens = [t for t in tokens if t.value in ("(", ")") and t.line == 1]
        assert all(t.continuation_start is None for t in paren_tokens)

    def test_rendered_context_line_is_construct_line(self, engine):
        # 渲染侧：归位后的源行上下文 = 构造所在行（非续行行）
        src = 'print("a=" + (str)1\nprint("DONE")\n'
        diag = _first_error(engine, src)
        rendered = DiagnosticFormatter.format(
            diag, use_color=False, source_manager=engine.scheduler.source_manager
        )
        assert 'print("a=" + (str)1' in rendered  # 源行 = 行 1（构造行）
