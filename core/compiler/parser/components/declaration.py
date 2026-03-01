from typing import List, Optional, Union
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
        elif role == SyntaxRole.CLASS_DEFINITION:
            self.stream.advance() # class
            stmt = self.class_declaration()
        elif role == SyntaxRole.VARIABLE_DECLARATION:
            explicit_var = self.stream.match(TokenType.VAR)
            stmt = self.variable_declaration(explicit_var=explicit_var)
        else:
            stmt = self.statement.parse_statement()
        
        if self.context.pending_intent is not None and stmt is not None:
            # 尝试将待处理意图注释注入到后续语句中
            intent_consumed = False
            
            # 1. 直接赋值给行为描述行 (BehaviorExpr)
            if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.BehaviorExpr):
                stmt.value.intent = self.context.pending_intent
                intent_consumed = True
            
            # 2. 表达式语句（如独立调用或独立行为描述行）
            elif isinstance(stmt, ast.ExprStmt):
                if isinstance(stmt.value, ast.BehaviorExpr):
                    stmt.value.intent = self.context.pending_intent
                    intent_consumed = True
                elif isinstance(stmt.value, ast.Call):
                    # Call 节点本身支持 intent 字段
                    if stmt.value.intent is None:
                        stmt.value.intent = self.context.pending_intent
                        intent_consumed = True
            
            if intent_consumed:
                self.context.pending_intent = None
            else:
                # 若语句无法自然消费意图，则报告警告
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

    def class_declaration(self) -> ast.ClassDef:
        start_token = self.stream.previous()
        name = self.stream.consume(TokenType.IDENTIFIER, "Expect class name.").value
        self.stream.consume(TokenType.COLON, "Expect ':' before class body.")
        
        class_node = self._loc(ast.ClassDef(name=name, body=[], methods=[], fields=[]), start_token)
        
        # Enter Class Scope
        self.scope_manager.enter_scope(ScopeType.CLASS)
        class_node.scope = self.scope_manager.current_scope
        
        # Pre-scan class members
        self._run_pre_scanner()
        
        body = self.statement.block()
        
        # Categorize body elements
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.LLMFunctionDef)):
                class_node.methods.append(stmt)
            elif isinstance(stmt, ast.Assign):
                class_node.fields.append(stmt)
            else:
                # Other statements in class body (e.g. print) are allowed but not common
                pass
        
        # Exit Class Scope
        self.scope_manager.exit_scope()
        
        class_node.body = body
        return class_node

    def parameters(self) -> List[ast.arg]:
        params = []
        if not self.stream.check(TokenType.RPAREN):
            while True:
                # 1. Handle special 'self' parameter
                if self.stream.match(TokenType.SELF):
                    name_token = self.stream.previous()
                    # 'self' has no explicit type annotation in ibci, it's implicit
                    param_node = self._loc(ast.arg(arg="self", annotation=None), name_token)
                    params.append(param_node)
                else:
                    # 2. Standard typed parameter: Type Name
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

    def llm_body(self) -> tuple[Optional[List[Union[str, ast.Expr]]], Optional[List[Union[str, ast.Expr]]]]:
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

    def parse_llm_section_content(self) -> List[Union[str, ast.Expr]]:
        segments = []
        while not self.stream.is_at_end():
            if self.stream.check(TokenType.LLM_SYS) or self.stream.check(TokenType.LLM_USER) or self.stream.check(TokenType.LLM_END):
                break
            
            if self.stream.match(TokenType.RAW_TEXT):
                segments.append(self.stream.previous().value)
            elif self.stream.match(TokenType.NEWLINE):
                segments.append("\n")
            elif self.stream.match(TokenType.PARAM_PLACEHOLDER):
                placeholder_token = self.stream.previous()
                # Extract expression string from $__expr__
                full_name = placeholder_token.value
                expr_str = full_name[3:-2] # Strip $__ and __
                
                # Use a temporary token stream to parse the internal expression
                from core.compiler.lexer.lexer import Lexer
                from core.compiler.parser.core.token_stream import TokenStream as ParserTokenStream
                
                sub_lexer = Lexer(expr_str)
                sub_tokens = sub_lexer.tokenize()
                if sub_tokens and sub_tokens[-1].type == TokenType.EOF:
                    sub_tokens.pop()
                
                if sub_tokens:
                    old_stream = self.stream
                    # Temporarily replace the stream in context
                    self.context.stream = ParserTokenStream(sub_tokens, self.issue_tracker)
                    try:
                        node = self.expression.parse_expression()
                        segments.append(node)
                    finally:
                        self.context.stream = old_stream
                else:
                    # Fallback for empty placeholders if they somehow occur
                    segments.append("")
            else:
                raise self.stream.error(self.stream.peek(), "Unexpected token in LLM section content.")
        
        return segments
