import os
from typing import Dict, List, Optional
from typedef.dependency_types import (
    ImportInfo, ModuleInfo, ImportType
)
from utils.diagnostics.issue_tracker import IssueTracker
from typedef.diagnostic_types import Severity, Location
from utils.diagnostics.codes import DEP_INVALID_IMPORT_POSITION
from typedef.lexer_types import TokenType, Token
from utils.parser.base_parser import BaseParser, ParseControlFlowError

class DependencyScanner(BaseParser):
    """
    Stateless scanner that extracts imports from a token stream.
    Inherits from BaseParser to reuse parsing logic.
    Intended to be instantiated per-file.
    """
    
    def __init__(self, tokens: List[Token], issue_tracker: IssueTracker):
        super().__init__(tokens, issue_tracker)
        
    def scan(self, file_path: str = "<unknown>") -> List[ImportInfo]:
        imports = []
        imports_allowed = True
        
        while not self.is_at_end():
            token = self.peek()
            
            # Skip whitespace/structure tokens
            if token.type in (TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT):
                self.advance()
                continue
                
            if token.type == TokenType.EOF:
                break
                
            # Check for Import
            if self.match(TokenType.IMPORT):
                if not imports_allowed:
                    self._report_invalid_pos(file_path, self.previous())
                    self._skip_to_next_statement()
                    continue
                    
                try:
                    node = self.parse_import()
                    
                    for alias in node.names:
                        info = ImportInfo(
                            module_name=alias.name,
                            lineno=node.lineno,
                            import_type=ImportType.IMPORT
                        )
                        imports.append(info)
                except ParseControlFlowError:
                    self._skip_to_next_statement()
                    
            elif self.match(TokenType.FROM):
                if not imports_allowed:
                    self._report_invalid_pos(file_path, self.previous())
                    self._skip_to_next_statement()
                    continue
                    
                try:
                    node = self.parse_from_import()
                    
                    # Reconstruct module name representation
                    mod_name = node.module or ""
                    if node.level > 0:
                        mod_name = "." * node.level + mod_name
                        
                    info = ImportInfo(
                        module_name=mod_name,
                        lineno=node.lineno,
                        import_type=ImportType.FROM_IMPORT
                    )
                    imports.append(info)
                except ParseControlFlowError:
                    self._skip_to_next_statement()
                    
            else:
                # Non-import token found (and not newline/indent)
                # This marks the end of the allowed import section
                imports_allowed = False
                self.advance()
                
        return imports

    def _skip_to_next_statement(self):
        while not self.is_at_end() and self.peek().type != TokenType.NEWLINE:
            self.advance()
        if self.match(TokenType.NEWLINE):
            pass

    def _report_invalid_pos(self, file_path: str, token: Token):
        loc = Location(file_path=file_path, line=token.line, column=token.column)
        self.issue_tracker.report(
            Severity.ERROR, 
            DEP_INVALID_IMPORT_POSITION, 
            "Import statements must be at the top of the file", 
            loc
        )
