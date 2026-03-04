from typing import List, Optional, Dict, Any, TYPE_CHECKING
from core.types.lexer_types import Token, TokenType
from core.types import parser_types as ast
from core.compiler.parser.core.token_stream import TokenStream, ParseControlFlowError
from core.compiler.parser.core.context import ParserContext
from core.compiler.parser.symbol_table import ScopeManager
from core.compiler.parser.scanners.pre_scanner import PreScanner
from core.support.diagnostics.issue_tracker import IssueTracker
from core.compiler.parser.components.expression import ExpressionComponent
from core.compiler.parser.components.statement import StatementComponent
from core.compiler.parser.components.declaration import DeclarationComponent
from core.compiler.parser.components.type_def import TypeComponent
from core.compiler.parser.components.import_def import ImportComponent
from core.types.dependency_types import ImportInfo, ImportType
from core.support.diagnostics.codes import DEP_INVALID_IMPORT_POSITION
from core.types.diagnostic_types import Severity, Location

from core.support.host_interface import HostInterface
from core.support.diagnostics.core_debugger import CoreModule, DebugLevel, core_debugger

if TYPE_CHECKING:
    from core.compiler.parser.resolver.resolver import ModuleResolver

class Parser:
    """
    IBC-Inter Parser.
    Uses Component-based architecture.
    """
    def __init__(self, tokens: List[Token], issue_tracker: Optional[IssueTracker] = None, module_cache: Optional[Dict[str, Any]] = None, package_name: str = "", module_resolver: Optional['ModuleResolver'] = None, host_interface: Optional[HostInterface] = None, debugger: Optional[Any] = None):
        
        # 1. Initialize Context
        self.stream = TokenStream(tokens, issue_tracker)
        self.debugger = debugger or core_debugger
        self.context = ParserContext(
            stream=self.stream,
            issue_tracker=self.stream.issue_tracker,
            scope_manager=ScopeManager(),
            module_resolver=module_resolver,
            module_cache=module_cache,
            host_interface=host_interface,
            package_name=package_name
        )
        
        # 2. Initialize Components
        # We pass context to each component. Components can access other components via context.
        self.expr_component = ExpressionComponent(self.context)
        self.stmt_component = StatementComponent(self.context)
        self.type_component = TypeComponent(self.context)
        self.decl_component = DeclarationComponent(self.context)
        self.import_component = ImportComponent(self.context)
        
        # 3. Register components to Context (Mediator Pattern)
        self.context.expression_parser = self.expr_component
        self.context.statement_parser = self.stmt_component
        self.context.type_parser = self.type_component
        self.context.declaration_parser = self.decl_component
        self.context.import_parser = self.import_component
        
        # 4. Initial Global Scan
        self._run_pre_scanner()

    @property
    def issue_tracker(self):
        return self.context.issue_tracker

    @property
    def scope_manager(self):
        return self.context.scope_manager

    def _run_pre_scanner(self):
        """Run the PreScanner on the current scope."""
        # Create a lookahead stream to avoid moving the main parser stream
        lookahead_stream = TokenStream(self.stream.tokens, self.context.issue_tracker)
        lookahead_stream.current = self.stream.current
        
        scanner = PreScanner(lookahead_stream, self.context.scope_manager)
        scanner.scan()

    def parse(self) -> ast.Module:
        self.debugger.trace(CoreModule.PARSER, DebugLevel.BASIC, "Starting parsing...")
        statements = []
        while not self.stream.is_at_end():
            try:
                if self.stream.match(TokenType.NEWLINE):
                    continue
                
                # Top level declarations or statements
                stmt = self.declaration()
                if stmt:
                    self.debugger.trace(CoreModule.PARSER, DebugLevel.DETAIL, f"Parsed top-level statement: {stmt.__class__.__name__}")
                    statements.append(stmt)
            except ParseControlFlowError:
                self.synchronize()
        
        # Check for errors at the end
        self.context.issue_tracker.check_errors()
        
        module_node = ast.Module(body=statements)
        module_node.scope = self.context.scope_manager.global_scope
        
        self.debugger.trace(CoreModule.PARSER, DebugLevel.BASIC, f"Parsing complete. Total statements: {len(statements)}")
        self.debugger.trace(CoreModule.PARSER, DebugLevel.DATA, "AST Module body:", data=statements)
        
        return module_node
        
    def parse_imports_only(self) -> List[ImportInfo]:
        """
        Only parse import statements at the beginning of the file.
        Stops when non-import/non-whitespace tokens are encountered.
        Used by Scheduler for dependency scanning.
        """
        imports = []
        imports_allowed = True
        
        # Temporarily enable skip_registration on ImportComponent
        old_skip = self.import_component.skip_registration
        self.import_component.skip_registration = True
        
        try:
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
                        # REPORT ERROR for misplaced import
                        self._report_invalid_import_pos(self.stream.previous())
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
                        # REPORT ERROR for misplaced import
                        self._report_invalid_import_pos(self.stream.previous())
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
                    
                    # Instead of breaking, we continue to scan but mark as not allowed
                    # We just skip the token/statement
                    self._skip_to_next_statement()
                    # But wait, _skip_to_next_statement only skips until newline.
                    # We need to make sure we advance at least once if we didn't match import
                    if not self.stream.is_at_end():
                        # If we are here, we peeked a token that is not IMPORT/FROM/WHITESPACE
                        # And we called _skip_to_next_statement which skips until NEWLINE.
                        # If the current token is not NEWLINE, it will be skipped.
                        pass
        finally:
             # Restore state
             self.import_component.skip_registration = old_skip
             
        return imports

    def _report_invalid_import_pos(self, token: Token):
        # file_path might be unknown if not set in tracker, but we try our best
        loc = Location(file_path="<unknown>", line=token.line, column=token.column)
        self.context.issue_tracker.report(
            Severity.ERROR, 
            DEP_INVALID_IMPORT_POSITION, 
            "Import statements must be at the top of the file", 
            loc
        )

    def _skip_to_next_statement(self):
        # Advance at least once to avoid infinite loop if we are stuck
        if not self.stream.is_at_end():
             self.stream.advance()
             
        while not self.stream.is_at_end() and self.stream.peek().type != TokenType.NEWLINE:
            self.stream.advance()
        if self.stream.match(TokenType.NEWLINE):
            pass

    def declaration(self) -> Optional[ast.Stmt]:
        # Delegate to DeclarationComponent or ImportComponent
        
        if self.stream.check(TokenType.IMPORT) or self.stream.check(TokenType.FROM):
            if self.stream.match(TokenType.IMPORT):
                return self.import_component.parse_import()
            elif self.stream.match(TokenType.FROM):
                return self.import_component.parse_from_import()
        
        # DeclarationComponent handles func, var, llm, and falls back to statement
        return self.decl_component.parse_declaration()

    def synchronize(self):
        """
        Discard tokens until we find a statement boundary to recover from error.
        """
        self.stream.advance()
        while not self.stream.is_at_end():
            if self.stream.previous().type == TokenType.NEWLINE:
                return
            
            if self.stream.peek().type in (TokenType.FUNC, TokenType.VAR, TokenType.FOR,
                                    TokenType.IF, TokenType.WHILE, TokenType.RETURN,
                                    TokenType.LLM_DEF, TokenType.IMPORT, TokenType.FROM,
                                    TokenType.BREAK, TokenType.CONTINUE):
                return
                
            if self.stream.peek().type == TokenType.DEDENT:
                return

            self.stream.advance()
