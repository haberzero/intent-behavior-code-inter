from typing import List, Optional
from core.domain.tokens import TokenType
from core.domain import ast as ast
from core.compiler.parser.core.component import BaseComponent

class ImportComponent(BaseComponent):
    """
    Component for parsing import statements.
    Produces AST nodes for further semantic analysis.
    """

    def __init__(self, context):
        super().__init__(context)

    def parse_import(self) -> ast.IbImport:
        """Parses 'import a.b, c as d'."""
        start_token = self.stream.previous() 
        
        names = self.parse_aliases()
        self.stream.consume_end_of_statement("Expect newline after import.")
        
        return self._loc(ast.IbImport(names=names), start_token)

    def parse_from_import(self) -> ast.IbImportFrom:
        """Parses 'from .a import b'."""
        start_token = self.stream.previous() # 'from' already consumed
        
        # Handle relative imports: from . import x, from ..foo import x
        level = 0
        while self.stream.match(TokenType.DOT):
            level += 1
            
        module_name = None
        if self.stream.check(TokenType.IDENTIFIER):
            module_name = self.parse_dotted_name()
            
        self.stream.consume(TokenType.IMPORT, "Expect 'import'.")
        names = self.parse_aliases()
        
        self.stream.consume_end_of_statement("Expect newline after import.")
        return self._loc(ast.IbImportFrom(module=module_name, names=names, level=level), start_token)

    def parse_aliases(self) -> List[ast.IbAlias]:
        aliases = []
        while True:
            start = self.stream.peek()
            
            # Handle '*' for from ... import *
            if self.stream.match(TokenType.STAR):
                aliases.append(self._loc(ast.IbAlias(name="*", asname=None), start))
            else:
                name = self.parse_dotted_name()
                asname = None
                if self.stream.match(TokenType.AS):
                    asname = self.stream.consume(TokenType.IDENTIFIER, "Expect alias name after 'as'.").value
                
                aliases.append(self._loc(ast.IbAlias(name=name, asname=asname), start))
            
            if not self.stream.match(TokenType.COMMA):
                break
        return aliases

    def parse_dotted_name(self) -> str:
        parts = [self.stream.consume(TokenType.IDENTIFIER, "Expect identifier in dotted name.").value]
        while self.stream.match(TokenType.DOT):
            parts.append(self.stream.consume(TokenType.IDENTIFIER, "Expect identifier after '.'.").value)
        return ".".join(parts)
