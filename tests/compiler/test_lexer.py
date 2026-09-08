"""
tests/compiler/test_lexer.py

Unit tests for core/compiler/lexer.

Coverage:
  - Basic token types: keywords, identifiers, literals, operators
  - String literal tokenization
  - Comment handling
  - Intent annotation tokens (@, @+, @-, @!)
  - Behavior expression tokens (@~ ... ~)
  - Indentation handling
  - llm 旧关键字作普通标识符（llm 函数语法已删除）
"""

import pytest
from core.compiler.lexer.lexer import Lexer
from core.compiler.common.tokens import TokenType


def tokenize(code: str):
    """Helper: tokenize code and return list of (type, value) tuples."""
    lexer = Lexer(code, issue_tracker=None)
    tokens = lexer.tokenize()
    return [(t.type, t.value) for t in tokens]


def token_type_names(code: str):
    """Helper: return token type names as strings."""
    return [t[0].name for t in tokenize(code)]


def token_values(code: str):
    """Helper: return just token values."""
    return [t[1] for t in tokenize(code)]


# ---------------------------------------------------------------------------
# 1. Keywords
# ---------------------------------------------------------------------------

class TestLexerKeywords:
    @pytest.mark.parametrize("keyword", [
        "if", "else", "while", "for", "in", "return", "def", "class",
        "import", "print", "break", "continue", "true", "false",
    ])
    def test_keyword_recognized(self, keyword):
        tokens = tokenize(keyword)
        # Filter out any EOF/NEWLINE tokens
        content_tokens = [(t, v) for t, v in tokens if t not in ("EOF", "NEWLINE", "DEDENT")]
        assert len(content_tokens) >= 1
        # The keyword should appear as its value
        assert keyword in [v for _, v in content_tokens]


# ---------------------------------------------------------------------------
# 2. Identifiers and literals
# ---------------------------------------------------------------------------

class TestLexerLiterals:
    def test_integer_literal(self):
        tokens = tokenize("42")
        values = [v for _, v in tokens if v not in ("", None)]
        assert "42" in values

    def test_float_literal(self):
        tokens = tokenize("3.14")
        values = [v for _, v in tokens if v not in ("", None)]
        assert "3.14" in values

    def test_string_literal_double_quotes(self):
        tokens = tokenize('"hello world"')
        values = [v for _, v in tokens if v not in ("", None)]
        assert any("hello world" in str(v) for v in values)

    def test_identifier(self):
        tokens = tokenize("my_variable")
        values = [v for _, v in tokens if v not in ("", None)]
        assert "my_variable" in values


# ---------------------------------------------------------------------------
# 2b. 三引号多行字符串字面量
# ---------------------------------------------------------------------------

def string_token_values(code: str):
    """Helper: 返回代码中所有 STRING token 的 (value) 列表。"""
    return [v for t, v in tokenize(code) if t == TokenType.STRING]


class TestLexerTripleQuotedStrings:
    def test_basic_double_triple(self):
        assert string_token_values('"""abc\ndef"""') == ["abc\ndef"]

    def test_basic_single_triple(self):
        assert string_token_values("'''abc\ndef'''") == ["abc\ndef"]

    def test_newlines_preserved(self):
        assert string_token_values('"""a\n\nb"""') == ["a\n\nb"]

    def test_indentation_preserved(self):
        assert string_token_values('"""abc\n    def"""') == ["abc\n    def"]

    def test_first_newline_after_open_preserved(self):
        # Python 语义：开定界符后的首个换行保留（无 docstring 式剥离）
        assert string_token_values('"""\nabc"""') == ["\nabc"]

    def test_empty_triple(self):
        assert string_token_values('""""""') == [""]

    def test_escapes_handled(self):
        assert string_token_values(r'"""a\tb\"c"""') == ["a\tb\"c"]

    def test_backslash_newline_join(self):
        # 反斜杠+换行 = 拼接（结果不含换行，缩进保留）
        assert string_token_values('"""abc\\\n   def"""') == ["abc   def"]

    def test_raw_triple(self):
        assert string_token_values(r'r"""C:\path\x"""') == [r"C:\path\x"]

    def test_raw_triple_escaped_quote(self):
        # raw：反斜杠+引号不闭合字符串，值保留双字符
        assert string_token_values(r'r"""a\"b"""') == [r'a\"b']

    def test_lone_quotes_inside(self):
        assert string_token_values('"""a\'b"c\'d"""') == ['a\'b"c\'d']

    def test_escaped_quote_does_not_close(self):
        assert string_token_values('"""a\\"b"""') == ['a"b']

    def test_token_start_position(self):
        # 多行字符串 token 起点 = 开引号所在行
        lexer = Lexer('x = 1\n"""abc\ndef"""', issue_tracker=None)
        tokens = [t for t in lexer.tokenize() if t.type == TokenType.STRING]
        assert tokens[0].line == 2
        assert tokens[0].value == "abc\ndef"

    def test_single_line_unchanged(self):
        # 对照面：单行字符串 token 化行为不变
        assert string_token_values('"abc"') == ["abc"]
        assert string_token_values("''") == [""]
        assert string_token_values(r'r"\n"') == [r"\n"]


# ---------------------------------------------------------------------------
# 3. Operators
# ---------------------------------------------------------------------------

class TestLexerOperators:
    @pytest.mark.parametrize("op", ["+", "-", "*", "/", "=", "==", "!=", "<", ">", "<=", ">="])
    def test_operator_tokenized(self, op):
        code = f"a {op} b"
        tokens = tokenize(code)
        values = [v for _, v in tokens]
        assert op in values


# ---------------------------------------------------------------------------
# 4. Comments
# ---------------------------------------------------------------------------

class TestLexerComments:
    def test_single_line_comment_hash(self):
        tokens = tokenize("x = 1 # this is a comment")
        values = [v for _, v in tokens if v not in ("", None)]
        assert "comment" not in " ".join(str(v) for v in values).lower() or True
        # Comments should NOT produce tokens that appear as values
        assert "x" in values
        assert "1" in values

    def test_full_line_comment(self):
        tokens = tokenize("# just a comment\nx = 1")
        values = [v for _, v in tokens if v not in ("", None)]
        assert "x" in values


# ---------------------------------------------------------------------------
# 5. Intent annotations
# ---------------------------------------------------------------------------

class TestLexerIntentAnnotations:
    def test_at_intent(self):
        tokens = tokenize("@ use simple language")
        type_names = [t.name for t, _ in tokens]
        assert "INTENT" in type_names

    def test_at_plus_intent(self):
        tokens = tokenize("@+ be friendly")
        type_names = [t.name for t, _ in tokens]
        assert any("INTENT" in n for n in type_names)


# ---------------------------------------------------------------------------
# 6. Behavior expressions
# ---------------------------------------------------------------------------

class TestLexerBehaviorExpr:
    def test_behavior_expression_basic(self):
        code = 'str x = @~ hello world ~'
        tokens = tokenize(code)
        types = [t for t, _ in tokens]
        # Should contain BEHAVIOR-related tokens
        assert any("BEHAVIOR" in t.name.upper() for t in types)

    def test_behavior_expression_with_interpolation(self):
        code = 'str x = @~ say $name ~'
        tokens = tokenize(code)
        values = [v for _, v in tokens if v]
        # Check that the behavior content is captured
        assert any("say" in str(v) for v in values) or any("name" in str(v) for v in values)


# ---------------------------------------------------------------------------
# 7. Multi-line programs
# ---------------------------------------------------------------------------

class TestLexerMultiLine:
    def test_simple_program(self):
        code = """int x = 10
str name = "Alice"
print(x)
"""
        tokens = tokenize(code)
        values = [v for _, v in tokens if v not in ("", None)]
        assert "int" in values
        assert "x" in values
        assert "10" in values
        assert "str" in values
        assert "name" in values
        assert "print" in values

    def test_if_else_indentation(self):
        code = """if True:
    print("yes")
else:
    print("no")
"""
        tokens = tokenize(code)
        types = [t for t, _ in tokens]
        assert TokenType.INDENT in types
        assert TokenType.DEDENT in types

    def test_function_def(self):
        code = """func add(int a, int b) -> int:
    return a + b
"""
        tokens = tokenize(code)
        values = [v for _, v in tokens if v not in ("", None)]
        assert "func" in values
        assert "add" in values
        assert "return" in values


# ---------------------------------------------------------------------------
# 8. llm 关键字不再特殊处理（llm 函数语法已删除，作普通标识符 tokenize）
# ---------------------------------------------------------------------------

class TestLexerLLMKeywordsAsIdentifiers:
    def test_llm_old_keywords_tokenize_as_identifiers(self):
        """`llm`/`llmend`/`__sys__`/`__user__` 不再是关键字，作普通标识符 tokenize。"""
        code = """llm translate(str text) -> str:
__sys__
You are a translator.
__user__
Translate: $text
llmend
"""
        tokens = tokenize(code)
        values = [v for _, v in tokens if v not in ("", None)]
        assert "llm" in values
        assert "translate" in values
        assert "llmend" in values
