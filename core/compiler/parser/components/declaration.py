from typing import List, Optional
from core.types.lexer_types import TokenType
from core.types import parser_types as ast
from core.types.symbol_types import SymbolType
from core.types.scope_types import ScopeType
from core.types.diagnostic_types import Severity
from core.compiler.parser.core.component import BaseComponent
from core.compiler.parser.core.recognizer import SyntaxRecognizer, SyntaxRole
from core.compiler.parser.core.token_stream import TokenStream, ParseControlFlowError
from core.compiler.parser.components.expression import ExpressionComponent
from core.compiler.parser.components.statement import StatementComponent
from core.compiler.parser.components.type_def import TypeComponent

class DeclarationComponent(BaseComponent):
    def __init__(self, context, expr_component: ExpressionComponent, stmt_component: StatementComponent, type_component: TypeComponent):
        super().__init__(context)
        self.expression = expr_component
        self.statement = stmt_component
        self.type_def = type_component
        
        # Link statement component back to this declaration component
        self.statement.set_decl_parser(self)

    def parse_declaration(self) -> Optional[ast.Stmt]:
        role = SyntaxRecognizer.get_role(self.stream, self.scope_manager)
        
        if role == SyntaxRole.INTENT_MARKER:
            self.stream.advance()
            if self.context.pending_intent is not None:
                raise self.stream.error(self.stream.previous(), "Multiple intent comments are not allowed for a single statement.")
            
            self.context.pending_intent = self.stream.previous().value
            if self.stream.check(TokenType.NEWLINE):
                self.stream.advance()
            return self.parse_declaration()
        
        stmt = None
        if role == SyntaxRole.FUNCTION_DEFINITION:
            self.stream.advance() # func
            stmt = self.function_declaration()
        elif role == SyntaxRole.LLM_DEFINITION:
            self.stream.advance() # llm
            stmt = self.llm_function_declaration()
        elif role == SyntaxRole.VARIABLE_DECLARATION:
            explicit_var = self.stream.match(TokenType.VAR)
            stmt = self.variable_declaration(explicit_var=explicit_var)
        else:
            stmt = self.statement.parse_statement()
        
        if self.context.pending_intent is not None and stmt is not None:
            # If the statement is not one that naturally consumes an intent (like Call or BehaviorExpr),
            # we report a warning to the user.
            self.issue_tracker.report(
                Severity.WARNING, "PAR_WARN", 
                f"Intent comment '{self.context.pending_intent}' was not used by the following statement.", 
                self.stream.peek()
            )
            self.context.pending_intent = None
            
        return stmt

    def _run_pre_scanner(self):
        """Run the PreScanner on the current scope."""
        from core.compiler.parser.scanners.pre_scanner import PreScanner
        
        # Create a lookahead stream to avoid moving the main parser stream
        lookahead_stream = TokenStream(self.stream.tokens, self.context.issue_tracker)
        lookahead_stream.current = self.stream.current
        
        scanner = PreScanner(lookahead_stream, self.scope_manager)
        scanner.scan()

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
        
        # Link type annotation node to symbol for SemanticAnalyzer
        sym = self.scope_manager.resolve(name_token.value)
        if sym:
            sym.declared_type_node = type_annotation
        
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
        
        # Link function symbol
        func_sym = self.scope_manager.resolve(name)
        if func_sym:
            func_sym.declared_type_node = returns
        
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
        
        # Link function symbol
        func_sym = self.scope_manager.resolve(name)
        if func_sym:
            func_sym.declared_type_node = returns
            
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
                
                param_node = self._loc(ast.arg(arg=name_token.value, annotation=annotation), name_token)
                params.append(param_node)
                
                # Link type annotation to parameter symbol
                sym = self.scope_manager.resolve(name_token.value)
                if sym:
                    sym.declared_type_node = annotation
                    
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
