import unittest
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from typedef.diagnostic_types import Severity, CompilerError
from utils.diagnostics.codes import *

class TestParserErrors(unittest.TestCase):
    """
    Error handling and resilience tests for Parser (Using Diagnostic System).
    Covers:
    1. Syntax Errors (Malformed imports, Missing newlines)
    2. Deep Recursion Resilience
    3. Unexpected EOF
    4. Warnings (Unused intent comments)
    """

    def parse(self, code):
        """Helper to parse code into a module."""
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        try:
            mod = parser.parse()
        except CompilerError:
            # Expected in error tests.
            # We return None for module, but the manager is available for inspection.
            mod = None
        return mod, parser.issue_tracker

    def test_deep_recursion(self):
        """Test parser resilience against deep recursion."""
        depth = 200
        # Nested parens
        source = "(" * depth + "1" + ")" * depth
        try:
            self.parse(source)
        except RecursionError:
            # Expected behavior for recursive descent parser
            pass

        # Nested types
        source = "List[" * depth + "int" + "]" * depth + " x = []"
        try:
            mod, manager = self.parse(source)
            # This specific deep nesting might be parsed as syntactically incorrect 
            # but we just want to ensure it doesn't crash unexpectedly if not RecursionError.
        except RecursionError:
            pass

    def test_unexpected_eof(self):
        """Test EOF handling in various contexts."""
        # EOF in func
        mod, manager = self.parse("func my_func(")
        self.assertTrue(manager.has_errors())
        diags = manager.diagnostics
        # Expect PAR_EXPECTED_TOKEN
        self.assertTrue(any(d.code == PAR_EXPECTED_TOKEN for d in diags))
        self.assertTrue(any("Expect type name" in d.message or "Expect parameter name" in d.message for d in diags))

    def test_malformed_import(self):
        """Test malformed import."""
        mod, manager = self.parse("import")
        self.assertTrue(manager.has_errors())
        diags = manager.diagnostics
        self.assertTrue(any(d.code == PAR_EXPECTED_TOKEN for d in diags))

    def test_behavior_errors(self):
        """Test errors related to behavior syntax (Lexer errors caught during parse)."""
        # Invalid continuation (e.g. extra tokens on line)
        # Lexer now tokenizes successfully, so Parser should catch the extra tokens.
        # We use '123' after behavior because 'and' is a valid operator that would extend the expression.
        mod, manager = self.parse("x = ~~ behavior ~~ 123")
        self.assertTrue(manager.has_errors())
        diags = manager.diagnostics
        # Should be "Expect newline"
        self.assertTrue(any("Expect newline" in d.message for d in diags))

    def test_intent_comment_warning(self):
        """Test warning when intent comment is unused."""
        code = """
@ unused intent
x = 1
"""
        mod, manager = self.parse(code)
        
        diags = manager.diagnostics
        warnings = [d for d in diags if d.severity == Severity.WARNING]
        
        self.assertTrue(len(warnings) > 0)
        self.assertTrue(any(d.code == "PAR_WARN" and "Intent comment" in d.message for d in warnings))

    def test_missing_newline_before_block(self):
        """Test missing newline before block (e.g. for 10: pass on one line)."""
        # Note: In IBC, blocks must start on new line with indentation.
        code = "for 10: pass"
        mod, manager = self.parse(code)
        self.assertTrue(manager.has_errors())
        diags = manager.diagnostics
        #  Parser synchronization might produce different errors, but should complain about block
        # Actually "Expect newline before block" or "Expect indent"
        self.assertTrue(any("Expect newline" in d.message or "Expect indent" in d.message for d in diags))

    def test_consecutive_intent_errors(self):
        """Test consecutive intent comments error."""
        code = """
@ intent 1
@ intent 2
x = 1
"""
        mod, manager = self.parse(code)
        self.assertTrue(manager.has_errors())
        diags = manager.diagnostics
        self.assertTrue(any("Multiple intent comments" in d.message for d in diags))

if __name__ == '__main__':
    unittest.main()
