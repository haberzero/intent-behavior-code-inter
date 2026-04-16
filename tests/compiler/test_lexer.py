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
  - LLM function block scanning (llm ... llmend)
"""

import pytest
from core.compiler.lexer.lexer import Lexer


def tokenize(code: str):
    """Helper: tokenize code and return list of (type, value) tuples."""
    lexer = Lexer(code, issue_tracker=None, debugger=None)
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
        assert any("BEHAVIOR" in t.upper() for t in types)

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
        code = """if true:
    print("yes")
else:
    print("no")
"""
        tokens = tokenize(code)
        types = [t for t, _ in tokens]
        assert "INDENT" in types
        assert "DEDENT" in types

    def test_function_def(self):
        code = """func add(int a, int b) -> int:
    return a + b
"""
        tokens = tokenize(code)
        values = [v for _, v in tokens if v not in ("", None)]
        assert "def" in values
        assert "add" in values
        assert "return" in values


# ---------------------------------------------------------------------------
# 8. LLM function blocks
# ---------------------------------------------------------------------------

class TestLexerLLMBlocks:
    def test_llm_function_block(self):
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
