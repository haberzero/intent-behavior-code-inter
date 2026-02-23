from typing import List, Optional
from typedef.lexer_types import TokenType
from typedef import parser_types as ast
from typedef.symbol_types import SymbolType
from typedef.scope_types import ScopeType
from typedef.diagnostic_types import Severity
from utils.parser.core.component import BaseComponent
from utils.parser.scanners.pre_scanner import PreScanner
from utils.parser.components.expression import ExpressionComponent
from utils.parser.components.statement import StatementComponent
from utils.parser.components.type_def import TypeComponent

class DeclarationComponent(BaseComponent):
    def __init__(self, context, expr_component: ExpressionComponent, stmt_component: StatementComponent, type_component: TypeComponent):
        super().__init__(context)
        self.expression = expr_component
        self.statement = stmt_component
        self.type_def = type_component
        
        # Link statement component back to this declaration component
        self.statement.set_decl_parser(self)

    def parse_declaration(self) -> Optional[ast.Stmt]:
        # Handle Intent (@)
        if self.stream.match(TokenType.INTENT):
            if self.context.pending_intent is not None:
                raise self.stream.error(self.stream.previous(), "Multiple intent comments are not allowed for a single statement.")
            
            self.context.pending_intent = self.stream.previous().value
            if self.stream.check(TokenType.NEWLINE):
                self.stream.advance()
            return self.parse_declaration()
        
        stmt = None
        if self.stream.match(TokenType.FUNC):
            stmt = self.function_declaration()
        elif self.stream.match(TokenType.LLM_DEF):
            stmt = self.llm_function_declaration()
        elif self.stream.match(TokenType.VAR):
            # Explicit 'var' declaration
            stmt = self.variable_declaration(explicit_var=True)
        elif self.check_declaration_lookahead():
            # Implicit type declaration: Type name = ...
            stmt = self.variable_declaration(explicit_var=False)
        else:
            stmt = self.statement.parse_statement()
        
        if self.context.pending_intent is not None and stmt is not None:
            # Check if stmt consumed it (Call or BehaviorExpr might have, but if it was a Stmt like Return, it might not)
            # Actually, statements like If/While/For don't usually consume intent in this language spec?
            # Or maybe they do?
            # If stmt is ExprStmt, and Expr consumed it, fine.
            # If stmt is Return, maybe not.
            # Let's warn if still pending.
            # But wait, ExpressionComponent consumes it if it's a Call/Behavior.
            # If it was consumed, pending_intent is None.
            
            # TODO: Add warning logic if needed.
            # For now, we clear it to avoid leaking to next statement.
            self.issue_tracker.report(
                Severity.WARNING, "PAR_WARN", 
                f"Intent comment '{self.context.pending_intent}' was not used by the following statement.", 
                self.stream.peek() # Approximation
            )
            self.context.pending_intent = None
            
        return stmt

    def check_declaration_lookahead(self) -> bool:
        """
        Check if the current tokens form a variable declaration.
        """
        # Case 1: Standard Type Name or Known Type in Symbol Table
        if self.stream.check(TokenType.IDENTIFIER) and self.scope_manager.is_type(self.stream.peek().value):
            next_token = self.stream.peek(1)
            
            if next_token.type == TokenType.IDENTIFIER:
                return True
            
            # Special case: Generic type declaration like list[int] x
            if next_token.type == TokenType.LBRACKET:
                return self._check_generic_lookahead(1)
                
            return False
            
        # Case 2: Identifier starting a declaration
        if self.stream.check(TokenType.IDENTIFIER):
            next_token = self.stream.peek(1)
            
            if next_token.type == TokenType.IDENTIFIER:
                return True
                
            if next_token.type == TokenType.LBRACKET:
                return self._check_generic_lookahead(1)
                
        return False

    def _check_generic_lookahead(self, offset: int) -> bool:
        bracket_depth = 0
        current_offset = offset
        # We need to access tokens directly from stream to scan ahead efficiently
        # But stream only provides peek(offset).
        
        # Limit lookahead to avoid performance issues?
        # Typically declarations aren't huge.
        
        while self.stream.current + current_offset < len(self.stream.tokens):
            t = self.stream.peek(current_offset)
            if t.type == TokenType.LBRACKET:
                bracket_depth += 1
            elif t.type == TokenType.RBRACKET:
                bracket_depth -= 1
                if bracket_depth == 0:
                    after_bracket = self.stream.peek(current_offset + 1)
                    if after_bracket.type == TokenType.IDENTIFIER:
                        return True
                    else:
                        return False
            elif t.type == TokenType.NEWLINE or t.type == TokenType.EOF:
                return False
                
            current_offset += 1
        return False

    def variable_declaration(self, explicit_var: bool = False) -> ast.Assign:
        type_token = None
        type_annotation = None
        
        if explicit_var:
            # 'var' keyword already consumed
            type_token = self.stream.previous()
            type_annotation = self._loc(ast.Name(id='var', ctx='Load'), type_token)
        else:
            # Parse type annotation
            start_token = self.stream.peek()
            type_annotation = self.type_def.parse_type_annotation()
            type_token = start_token

        name_token = self.stream.consume(TokenType.IDENTIFIER, "Expect variable name.")
        target = self._loc(ast.Name(id=name_token.value, ctx='Store'), name_token)
        
        value = None
        if self.stream.match(TokenType.ASSIGN):
            value = self.expression.parse_expression()
        
        self.stream.consume_end_of_statement("Expect newline after variable declaration.")
        
        return self._loc(ast.Assign(targets=[target], value=value, type_annotation=type_annotation), type_token)

    def function_declaration(self) -> ast.FunctionDef:
        start_token = self.stream.previous()
        name = self.stream.consume(TokenType.IDENTIFIER, "Expect function name.").value
        self.stream.consume(TokenType.LPAREN, "Expect '(' after function name.")
        args = self.parameters()
        self.stream.consume(TokenType.RPAREN, "Expect ')' after parameters.")
        
        returns = None
        if self.stream.match(TokenType.ARROW):
            returns = self.type_def.parse_type_annotation()
            
        self.stream.consume(TokenType.COLON, "Expect ':' before function body.")
        
        func_node = self._loc(ast.FunctionDef(name=name, args=args, body=[], returns=returns), start_token)
        
        # Enter Function Scope
        self.scope_manager.enter_scope(ScopeType.FUNCTION)
        func_node.scope = self.scope_manager.current_scope
        
        # Register parameters
        for arg in args:
            self.scope_manager.define(arg.arg, SymbolType.VARIABLE)
            
        # Pre-scan local variables/functions
        self._run_pre_scanner()
        
        body = self.statement.block()
        
        # Exit Function Scope
        self.scope_manager.exit_scope()
        
        func_node.body = body
        return func_node

    def llm_function_declaration(self) -> ast.LLMFunctionDef:
        start_token = self.stream.previous()
        name = self.stream.consume(TokenType.IDENTIFIER, "Expect LLM function name.").value
        self.stream.consume(TokenType.LPAREN, "Expect '(' after function name.")
        args = self.parameters()
        self.stream.consume(TokenType.RPAREN, "Expect ')' after parameters.")
        
        returns = None
        if self.stream.match(TokenType.ARROW):
            returns = self.type_def.parse_type_annotation()
            
        self.stream.consume(TokenType.COLON, "Expect ':' before function body.")
        
        llm_node = self._loc(ast.LLMFunctionDef(name=name, args=args, sys_prompt=None, user_prompt=None, returns=returns), start_token)
        
        # LLM functions also have a scope
        self.scope_manager.enter_scope(ScopeType.FUNCTION)
        llm_node.scope = self.scope_manager.current_scope
        
        # Register parameters
        for arg in args:
            self.scope_manager.define(arg.arg, SymbolType.VARIABLE)
            
        self._run_pre_scanner()
        
        sys_prompt, user_prompt = self.llm_body()
        llm_node.sys_prompt = sys_prompt
        llm_node.user_prompt = user_prompt
        
        self.scope_manager.exit_scope()
        
        return llm_node

    def parameters(self) -> List[ast.arg]:
        params = []
        if not self.stream.check(TokenType.RPAREN):
            while True:
                annotation = self.type_def.parse_type_annotation()
                name_token = self.stream.consume(TokenType.IDENTIFIER, "Expect parameter name.")
                
                params.append(self._loc(ast.arg(arg=name_token.value, annotation=annotation), name_token))
                if not self.stream.match(TokenType.COMMA):
                    break
        return params

    def llm_body(self) -> tuple[Optional[ast.Constant], Optional[ast.Constant]]:
        self.stream.consume(TokenType.NEWLINE, "Expect newline before LLM block.")
        
        sys_prompt = None
        user_prompt = None
        
        while not self.stream.check(TokenType.LLM_END) and not self.stream.is_at_end():
            if self.stream.match(TokenType.LLM_SYS):
                sys_prompt = self.parse_llm_section_content()
            elif self.stream.match(TokenType.LLM_USER):
                user_prompt = self.parse_llm_section_content()
            elif self.stream.match(TokenType.NEWLINE):
                continue
            else:
                raise self.stream.error(self.stream.peek(), "Unexpected token in LLM block. Expect '__sys__', '__user__', or 'llmend'.")

        self.stream.consume(TokenType.LLM_END, "Expect 'llmend' to close LLM block.")
        return sys_prompt, user_prompt

    def parse_llm_section_content(self) -> ast.Constant:
        start_token = self.stream.previous()
        content_parts = []
        while not self.stream.is_at_end():
            if self.stream.check(TokenType.LLM_SYS) or self.stream.check(TokenType.LLM_USER) or self.stream.check(TokenType.LLM_END):
                break
            
            if self.stream.match(TokenType.RAW_TEXT):
                content_parts.append(self.stream.previous().value)
            elif self.stream.match(TokenType.NEWLINE):
                content_parts.append("\n")
            elif self.stream.match(TokenType.PARAM_PLACEHOLDER):
                content_parts.append(self.stream.previous().value)
            else:
                raise self.stream.error(self.stream.peek(), "Unexpected token in LLM section content.")
        
        return self._loc(ast.Constant(value="".join(content_parts)), start_token)

    def _run_pre_scanner(self):
        """Run the PreScanner on the current scope."""
        scanner = PreScanner(self.stream.tokens, self.stream.current, self.scope_manager)
        scanner.scan()
