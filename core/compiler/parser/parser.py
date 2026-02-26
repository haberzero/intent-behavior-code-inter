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

from core.support.host_interface import HostInterface

if TYPE_CHECKING:
    from core.compiler.parser.resolver.resolver import ModuleResolver

class Parser:
    """
    IBC-Inter Parser.
    Uses Component-based architecture.
    """
    def __init__(self, tokens: List[Token], issue_tracker: Optional[IssueTracker] = None, module_cache: Optional[Dict[str, Any]] = None, package_name: str = "", module_resolver: Optional['ModuleResolver'] = None, host_interface: Optional[HostInterface] = None):
        
        # 1. Initialize Context
        self.stream = TokenStream(tokens, issue_tracker)
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
        self.expr_component = ExpressionComponent(self.context)
        self.stmt_component = StatementComponent(self.context, self.expr_component)
        self.type_component = TypeComponent(self.context)
        self.decl_component = DeclarationComponent(
            self.context, 
            self.expr_component, 
            self.stmt_component, 
            self.type_component
        )
        self.import_component = ImportComponent(self.context)
        
        # 3. Initial Global Scan
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
        statements = []
        while not self.stream.is_at_end():
            try:
                if self.stream.match(TokenType.NEWLINE):
                    continue
                
                # Top level declarations or statements
                stmt = self.declaration()
                if stmt:
                    statements.append(stmt)
            except ParseControlFlowError:
                self.synchronize()
        
        # Check for errors at the end
        self.context.issue_tracker.check_errors()
        
        module_node = ast.Module(body=statements)
        module_node.scope = self.context.scope_manager.global_scope
        return module_node

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
