import unittest
from typing import List
from typedef.dependency_types import ImportInfo, ImportType
from typedef.lexer_types import Token, TokenType
from utils.dependency.dependency_scanner import DependencyScanner
from utils.diagnostics.issue_tracker import IssueTracker

class TestDependencyScanner(unittest.TestCase):

    def setUp(self):
        self.issue_tracker = IssueTracker()
        # DependencyScanner is now instantiated per tokens
        pass

    def _create_token(self, type: TokenType, value: str = "") -> Token:
        return Token(type, value, 1, 1)

    def _scan(self, tokens: List[Token]) -> List[ImportInfo]:
        scanner = DependencyScanner(tokens, self.issue_tracker)
        return scanner.scan()

    def test_simple_import(self):
        # import math
        tokens = [
            self._create_token(TokenType.IMPORT, "import"),
            self._create_token(TokenType.IDENTIFIER, "math"),
            self._create_token(TokenType.NEWLINE, "\n"),
            self._create_token(TokenType.EOF)
        ]
        
        imports = self._scan(tokens)
        
        self.assertEqual(len(imports), 1)
        self.assertEqual(imports[0].module_name, "math")
        self.assertEqual(imports[0].import_type, ImportType.IMPORT)

    def test_multiple_imports(self):
        # import os, sys
        tokens = [
            self._create_token(TokenType.IMPORT, "import"),
            self._create_token(TokenType.IDENTIFIER, "os"),
            self._create_token(TokenType.COMMA, ","),
            self._create_token(TokenType.IDENTIFIER, "sys"),
            self._create_token(TokenType.NEWLINE, "\n"),
            self._create_token(TokenType.EOF)
        ]
        
        imports = self._scan(tokens)
        
        self.assertEqual(len(imports), 2)
        self.assertEqual(imports[0].module_name, "os")
        self.assertEqual(imports[1].module_name, "sys")

    def test_from_import(self):
        # from utils import math
        tokens = [
            self._create_token(TokenType.FROM, "from"),
            self._create_token(TokenType.IDENTIFIER, "utils"),
            self._create_token(TokenType.IMPORT, "import"),
            self._create_token(TokenType.IDENTIFIER, "math"),
            self._create_token(TokenType.NEWLINE, "\n"),
            self._create_token(TokenType.EOF)
        ]
        
        imports = self._scan(tokens)
        
        self.assertEqual(len(imports), 1)
        self.assertEqual(imports[0].module_name, "utils")
        self.assertEqual(imports[0].import_type, ImportType.FROM_IMPORT)

    def test_relative_import(self):
        # from .utils import math
        tokens = [
            self._create_token(TokenType.FROM, "from"),
            self._create_token(TokenType.DOT, "."),
            self._create_token(TokenType.IDENTIFIER, "utils"),
            self._create_token(TokenType.IMPORT, "import"),
            self._create_token(TokenType.IDENTIFIER, "math"),
            self._create_token(TokenType.NEWLINE, "\n"),
            self._create_token(TokenType.EOF)
        ]
        
        imports = self._scan(tokens)
        
        self.assertEqual(len(imports), 1)
        self.assertEqual(imports[0].module_name, ".utils")
        self.assertEqual(imports[0].import_type, ImportType.FROM_IMPORT)

    def test_ignore_non_imports(self):
        # x = 1
        # import math
        
        tokens = [
            self._create_token(TokenType.IDENTIFIER, "x"),
            self._create_token(TokenType.ASSIGN, "="),
            self._create_token(TokenType.NUMBER, "1"),
            self._create_token(TokenType.NEWLINE, "\n"),
            self._create_token(TokenType.IMPORT, "import"), # Should be skipped/flagged as error
            self._create_token(TokenType.IDENTIFIER, "math"),
            self._create_token(TokenType.NEWLINE, "\n"),
            self._create_token(TokenType.EOF)
        ]
        
        imports = self._scan(tokens)
        
        self.assertEqual(len(imports), 0)
        self.assertTrue(self.issue_tracker.has_errors()) # DEP_INVALID_IMPORT_POSITION

if __name__ == '__main__':
    unittest.main()
