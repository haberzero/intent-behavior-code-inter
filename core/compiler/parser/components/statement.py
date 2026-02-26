from typing import List, Optional
from core.types.lexer_types import TokenType
from core.types import parser_types as ast
from core.compiler.parser.core.component import BaseComponent
from core.compiler.parser.components.expression import ExpressionComponent

class StatementComponent(BaseComponent):
    def __init__(self, context, expression_component: ExpressionComponent):
        super().__init__(context)
        self.expression = expression_component
        # We need access to declaration component for block parsing?
        # Yes, blocks contain declarations.
        # But this creates a circular dependency if StatementComponent imports DeclarationComponent
        # and DeclarationComponent imports StatementComponent.
        # We can pass declaration_component or use a callback/facade for parsing declarations.
        # For now, let's assume MainParser handles the dispatch or we pass a callback.
        self.decl_parser = None # Set later

    def set_decl_parser(self, decl_parser):
        self.decl_parser = decl_parser

    def parse_statement(self) -> ast.Stmt:
        if self.stream.match(TokenType.RETURN):
            return self.return_statement()
        if self.stream.match(TokenType.IF):
            return self.if_statement()
        if self.stream.match(TokenType.WHILE):
            return self.while_statement()
        if self.stream.match(TokenType.FOR):
            return self.for_statement()
        if self.stream.match(TokenType.TRY):
            return self.try_statement()
        if self.stream.match(TokenType.RAISE):
            return self.raise_statement()
        if self.stream.match(TokenType.PASS):
            start = self.stream.previous()
            self.stream.consume_end_of_statement("Expect newline after pass.")
            return self._loc(ast.Pass(), start)
        if self.stream.match(TokenType.BREAK):
            start = self.stream.previous()
            self.stream.consume_end_of_statement("Expect newline after break.")
            return self._loc(ast.Break(), start)
        if self.stream.match(TokenType.CONTINUE):
            start = self.stream.previous()
            self.stream.consume_end_of_statement("Expect newline after continue.")
            return self._loc(ast.Continue(), start)
        if self.stream.match(TokenType.RETRY):
            start = self.stream.previous()
            self.stream.consume_end_of_statement("Expect newline after retry.")
            return self._loc(ast.Retry(), start)
        
        # We assume imports are handled by ImportComponent and dispatched by MainParser
        # But if statement() is called inside a block, we might encounter import?
        # If imports are allowed in blocks (not recommended usually but maybe supported),
        # MainParser should dispatch to ImportComponent.
        # Here we only handle control flow and expressions.
        
        return self.expression_statement()

    def return_statement(self) -> ast.Return:
        start_token = self.stream.previous()
        value = None
        if not self.stream.check(TokenType.NEWLINE) and not self.stream.is_at_end():
            value = self.expression.parse_expression()
        self.stream.consume_end_of_statement("Expect newline after return.")
        return self._loc(ast.Return(value=value), start_token)

    def if_statement(self) -> ast.If:
        start_token = self.stream.previous()
        
        # 1. Parse initial IF
        test = self.expression.parse_expression()
        self._set_scene_recursive(test, ast.Scene.BRANCH)
        self.stream.consume(TokenType.COLON, "Expect ':' after if condition.")
        body = self.block()
        
        llm_fallback = None
        if self.stream.match(TokenType.LLM_EXCEPT):
            self.stream.consume(TokenType.COLON, "Expect ':' after llmexcept.")
            llm_fallback = self.block()
            
        root_if = self._loc(ast.If(test=test, body=body, orelse=[], llm_fallback=llm_fallback), start_token)
        last_node = root_if
        
        # 2. Parse ELIF chain
        while self.stream.match(TokenType.ELIF):
            elif_start = self.stream.previous()
            elif_test = self.expression.parse_expression()
            self._set_scene_recursive(elif_test, ast.Scene.BRANCH)
            self.stream.consume(TokenType.COLON, "Expect ':' after elif condition.")
            elif_body = self.block()
            
            elif_fallback = None
            if self.stream.match(TokenType.LLM_EXCEPT):
                self.stream.consume(TokenType.COLON, "Expect ':' after llmexcept.")
                elif_fallback = self.block()
                
            new_if = self._loc(ast.If(test=elif_test, body=elif_body, orelse=[], llm_fallback=elif_fallback), elif_start)
            last_node.orelse = [new_if]
            last_node = new_if
            
        # 3. Parse ELSE
        if self.stream.match(TokenType.ELSE):
            self.stream.consume(TokenType.COLON, "Expect ':' after else.")
            last_node.orelse = self.block()
            
        # 4. Final LLM_EXCEPT for the whole chain (if root doesn't have one)
        if self.stream.match(TokenType.LLM_EXCEPT):
            self.stream.consume(TokenType.COLON, "Expect ':' after llmexcept.")
            final_fallback = self.block()
            if root_if.llm_fallback is None:
                root_if.llm_fallback = final_fallback
            elif last_node != root_if and last_node.llm_fallback is None:
                # If root has one, but last node (elif) doesn't, attach to last node
                last_node.llm_fallback = final_fallback
            # else: root already has one, this might be a double llmexcept which is usually okay or ignored
            
        return root_if

    def while_statement(self) -> ast.While:
        start_token = self.stream.previous()
        test = self.expression.parse_expression()
        self._set_scene_recursive(test, ast.Scene.LOOP)
        self.stream.consume(TokenType.COLON, "Expect ':' after condition.")
        body = self.block()
        
        llm_fallback: Optional[List[ast.Stmt]] = None
        if self.stream.match(TokenType.LLM_EXCEPT):
            self.stream.consume(TokenType.COLON, "Expect ':' after llmexcept.")
            llm_fallback = self.block()
            
        return self._loc(ast.While(test=test, body=body, orelse=[], llm_fallback=llm_fallback), start_token)

    def for_statement(self) -> ast.For:
        start_token = self.stream.previous()
        
        expr1 = self.expression.parse_expression()
        self._set_scene_recursive(expr1, ast.Scene.LOOP)
        
        target = None
        iter_expr = None
        
        if self.stream.match(TokenType.IN):
            # Case: for i in list
            target = expr1
            iter_expr = self.expression.parse_expression()
            self._set_scene_recursive(iter_expr, ast.Scene.LOOP)
        elif self.stream.check(TokenType.COLON):
            # Case: for 10:  or  for ~behavior~:
            target = None
            iter_expr = expr1
        else:
            raise self.stream.error(self.stream.peek(), "Expect 'in' or ':' in for statement.")
            
        self.stream.consume(TokenType.COLON, "Expect ':' after for loop iterator.")
        body = self.block()
        
        llm_fallback: Optional[List[ast.Stmt]] = None
        if self.stream.match(TokenType.LLM_EXCEPT):
            self.stream.consume(TokenType.COLON, "Expect ':' after llmexcept.")
            llm_fallback = self.block()
            
        return self._loc(ast.For(target=target, iter=iter_expr, body=body, orelse=[], llm_fallback=llm_fallback), start_token)

    def expression_statement(self) -> ast.Stmt:
        expr = self.expression.parse_expression()
        
        # Check if it's an assignment or compound assignment
        if self.stream.match(TokenType.ASSIGN):
            value = self.expression.parse_expression()
            self.stream.consume_end_of_statement("Expect newline after assignment.")
            return self._loc(ast.Assign(targets=[expr], value=value), self.stream.previous())
        
        # Compound assignments
        compound_ops = {
            TokenType.PLUS_ASSIGN: '+', TokenType.MINUS_ASSIGN: '-',
            TokenType.STAR_ASSIGN: '*', TokenType.SLASH_ASSIGN: '/',
            TokenType.PERCENT_ASSIGN: '%'
        }
        
        for token_type, op_str in compound_ops.items():
            if self.stream.match(token_type):
                value = self.expression.parse_expression()
                self.stream.consume_end_of_statement("Expect newline after compound assignment.")
                return self._loc(ast.AugAssign(target=expr, op=op_str, value=value), self.stream.previous())
            
        self.stream.consume_end_of_statement("Expect newline after expression.")
        return self._loc(ast.ExprStmt(value=expr), self.stream.previous())

    def block(self) -> List[ast.Stmt]:
        self.stream.consume(TokenType.NEWLINE, "Expect newline before block.")
        self.stream.consume(TokenType.INDENT, "Expect indent after block start.")
        stmts = []
        while not self.stream.check(TokenType.DEDENT) and not self.stream.is_at_end():
            if self.stream.match(TokenType.NEWLINE):
                continue
            
            # Delegate to declaration parser (which handles both declarations and statements)
            if self.decl_parser:
                stmt = self.decl_parser.parse_declaration()
                if stmt:
                    stmts.append(stmt)
            else:
                # Fallback if not linked?
                raise Exception("Declaration parser not linked to StatementComponent")

        self.stream.consume(TokenType.DEDENT, "Expect dedent after block.")
        return stmts

    def try_statement(self) -> ast.Try:
        start_token = self.stream.previous()
        self.stream.consume(TokenType.COLON, "Expect ':' after try.")
        body = self.block()
        
        handlers = []
        while self.stream.match(TokenType.EXCEPT):
            handler_start = self.stream.previous()
            type_expr = None
            name = None
            
            if not self.stream.check(TokenType.COLON):
                type_expr = self.expression.parse_expression()
                if self.stream.match(TokenType.AS):
                    name_token = self.stream.consume(TokenType.IDENTIFIER, "Expect exception name after 'as'.")
                    name = name_token.value
            
            self.stream.consume(TokenType.COLON, "Expect ':' after except.")
            handler_body = self.block()
            handlers.append(self._loc(ast.ExceptHandler(type=type_expr, name=name, body=handler_body), handler_start))
        
        orelse = []
        if self.stream.match(TokenType.ELSE):
            self.stream.consume(TokenType.COLON, "Expect ':' after else.")
            orelse = self.block()
            
        finalbody = []
        if self.stream.match(TokenType.FINALLY):
            self.stream.consume(TokenType.COLON, "Expect ':' after finally.")
            finalbody = self.block()
            
        if not handlers and not finalbody:
             raise self.stream.error(start_token, "Expect 'except' or 'finally' after 'try'.")
             
        return self._loc(ast.Try(body=body, handlers=handlers, orelse=orelse, finalbody=finalbody), start_token)

    def raise_statement(self) -> ast.Raise:
        start_token = self.stream.previous()
        exc = None
        if not self.stream.check(TokenType.NEWLINE) and not self.stream.is_at_end():
            exc = self.expression.parse_expression()
        self.stream.consume_end_of_statement("Expect newline after raise.")
        return self._loc(ast.Raise(exc=exc), start_token)
