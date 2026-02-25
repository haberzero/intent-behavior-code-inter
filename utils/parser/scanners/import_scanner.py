from typing import List
from typedef.dependency_types import ImportInfo, ImportType
from typedef.lexer_types import TokenType, Token
from typedef.diagnostic_types import Severity, Location
from utils.diagnostics.issue_tracker import IssueTracker
from utils.diagnostics.codes import DEP_INVALID_IMPORT_POSITION
from utils.parser.core.token_stream import TokenStream, ParseControlFlowError
from utils.parser.core.context import ParserContext
from utils.parser.components.import_def import ImportComponent

class ImportScanner:
    """
    Stateless scanner that extracts imports from a token stream.
    Uses ImportComponent to parse import statements.
    """
    
    def __init__(self, tokens: List[Token], issue_tracker: IssueTracker):
        self.stream = TokenStream(tokens, issue_tracker)
        self.context = ParserContext(self.stream, issue_tracker)
        self.import_component = ImportComponent(self.context, skip_registration=True)
        
    def scan(self, file_path: str = "<unknown>") -> List[ImportInfo]:
        imports = []
        imports_allowed = True
        
        while not self.stream.is_at_end():
            token = self.stream.peek()
            
            # Skip whitespace/structure tokens
            if token.type in (TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT):
                self.stream.advance()
                continue
                
            if token.type == TokenType.EOF:
                break
                
            # Check for Import
            if self.stream.match(TokenType.IMPORT):
                if not imports_allowed:
                    self._report_invalid_pos(file_path, self.stream.previous())
                    self._skip_to_next_statement()
                    continue
                    
                try:
                    node = self.import_component.parse_import()
                    
                    for alias in node.names:
                        info = ImportInfo(
                            module_name=alias.name,
                            lineno=node.lineno,
                            import_type=ImportType.IMPORT
                        )
                        imports.append(info)
                except ParseControlFlowError:
                    self._skip_to_next_statement()
                    
            elif self.stream.match(TokenType.FROM):
                if not imports_allowed:
                    self._report_invalid_pos(file_path, self.stream.previous())
                    self._skip_to_next_statement()
                    continue
                    
                try:
                    node = self.import_component.parse_from_import()
                    
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
                self.stream.advance()
                
        return imports

    def _skip_to_next_statement(self):
        while not self.stream.is_at_end() and self.stream.peek().type != TokenType.NEWLINE:
            self.stream.advance()
        if self.stream.match(TokenType.NEWLINE):
            pass

    def _report_invalid_pos(self, file_path: str, token: Token):
        loc = Location(file_path=file_path, line=token.line, column=token.column)
        self.context.issue_tracker.report(
            Severity.ERROR, 
            DEP_INVALID_IMPORT_POSITION, 
            "Import statements must be at the top of the file", 
            loc
        )
