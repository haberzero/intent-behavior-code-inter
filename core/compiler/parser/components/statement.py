from typing import List, Optional, TYPE_CHECKING
from core.types.lexer_types import TokenType
from core.types import parser_types as ast
from core.compiler.parser.core.component import BaseComponent

if TYPE_CHECKING:
    from core.compiler.parser.components.expression import ExpressionComponent

class StatementComponent(BaseComponent):
    def __init__(self, context):
        super().__init__(context)
        # self.expression = expression_component  <-- Removed, use context
        # self.decl_parser = None <-- Removed, use context

    @property
    def expression(self) -> 'ExpressionComponent':
        return self.context.expression_parser

    @property
    def decl_parser(self):
        return self.context.declaration_parser

    # Removed set_decl_parser method

    def parse_statement(self) -> ast.Stmt:
        if self.stream.match(TokenType.RETURN):
            return self.return_statement()
        if self.stream.match(TokenType.GLOBAL):
            return self.global_statement()
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
            hint = None
            if self.stream.check(TokenType.STRING):
                hint = self.expression.parse_expression()
            self.stream.consume_end_of_statement("Expect newline after retry.")
            return self._loc(ast.Retry(hint=hint), start)
        
        if self.stream.match(TokenType.INTENT_STMT):
            return self.intent_statement()
        if self.stream.match(TokenType.INTENT):
            return self.at_intent_shorthand()
        
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

    def global_statement(self) -> ast.GlobalStmt:
        start_token = self.stream.previous()
        names = []
        while True:
            name_token = self.stream.consume(TokenType.IDENTIFIER, "Expect variable name in global declaration.")
            names.append(name_token.value)
            if not self.stream.match(TokenType.COMMA):
                break
        self.stream.consume_end_of_statement("Expect newline after global declaration.")
        return self._loc(ast.GlobalStmt(names=names), start_token)

    def intent_statement(self) -> ast.IntentStmt:
        """Parse 'intent "content": block'"""
        start_token = self.stream.previous()
        
        # 1. Parse content (string or variable)
        intent_info = self._parse_intent_info(start_token)
        
        # 2. Parse block
        self.stream.consume(TokenType.COLON, "Expect ':' after intent.")
        body = self.block()
        
        return self._loc(ast.IntentStmt(intent=intent_info, body=body), start_token)

    def at_intent_shorthand(self) -> ast.IntentStmt:
        """Parse '@ "content" \n statement'"""
        start_token = self.stream.previous()
        
        # 1. Parse content
        intent_info = self._parse_intent_info(start_token)
        
        # 2. Parse next statement as body
        self.stream.consume(TokenType.NEWLINE, "Expect newline after @ shorthand.")
        
        # We need to call parse_statement again.
        # Use the context to avoid circular dependency.
        next_stmt = self.context.statement_parser.parse_statement()
        return self._loc(ast.IntentStmt(intent=intent_info, body=[next_stmt]), start_token)

    def _parse_intent_info(self, start_token) -> ast.IntentInfo:
        """Helper to parse the content part of an intent (@ or intent keyword)"""
        mode = "normal"
        token_val = start_token.value
        if token_val.startswith("@"):
            mode_char = token_val[1:]
            if mode_char == "+": mode = "append"
            elif mode_char == "!": mode = "override"
            elif mode_char == "-": mode = "remove"
        else:
            # Handle 'intent ! "content":'
            if self.stream.match(TokenType.NOT):
                mode = "override"
            elif self.stream.match(TokenType.PLUS):
                mode = "append"
            elif self.stream.match(TokenType.MINUS):
                mode = "remove"
            
        segments = []
        while not self.stream.check(TokenType.COLON) and not self.stream.check(TokenType.NEWLINE) and not self.stream.is_at_end():
            if self.stream.match(TokenType.RAW_TEXT):
                segments.append(self.stream.previous().value)
            elif self.stream.match(TokenType.STRING):
                val = self.stream.previous().value
                # Strip quotes if present
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                segments.append(val)

            elif self.stream.match(TokenType.VAR_REF):
                # Variable reference $var or $(expr)
                segments.append(self.expression.parse_expression())
            else:
                # Try parsing as an expression if it's not a special token
                try:
                    segments.append(self.expression.parse_expression())
                except:
                    break
                
        # If single segment and it's a string, we can flatten it
        content = "".join([s if isinstance(s, str) else str(s) for s in segments])
        return ast.IntentInfo(mode=mode, content=content, segments=segments)


    def if_statement(self) -> ast.Stmt:
        start_token = self.stream.previous()
        
        # 1. Parse initial IF
        test = self.expression.parse_expression()
        self.stream.consume(TokenType.COLON, "Expect ':' after if condition.")
        body = self.block()
        
        llm_fallback = self._parse_llm_fallback()
            
        root_if = self._loc(ast.If(test=test, body=body, orelse=[]), start_token)
        last_node = root_if
        
        # 2. Parse ELIF chain
        while self.stream.match(TokenType.ELIF):
            elif_start = self.stream.previous()
            elif_test = self.expression.parse_expression()
            self.stream.consume(TokenType.COLON, "Expect ':' after elif condition.")
            elif_body = self.block()
            
            new_if = self._loc(ast.If(test=elif_test, body=elif_body, orelse=[]), elif_start)
            last_node.orelse = [new_if]
            last_node = new_if
            
        # 3. Parse ELSE
        if self.stream.match(TokenType.ELSE):
            self.stream.consume(TokenType.COLON, "Expect ':' after else.")
            last_node.orelse = self.block()
            
        # 4. Final LLM_EXCEPT for the whole chain
        final_fallback = self._parse_llm_fallback()
        
        # 优先使用 root 的 fallback，如果没有则使用最后的 final_fallback
        effective_fallback = llm_fallback or final_fallback
        
        if effective_fallback:
            return self._loc(ast.LLMExceptionalStmt(primary=root_if, fallback=effective_fallback), start_token)
            
        return root_if

    def while_statement(self) -> ast.Stmt:
        start_token = self.stream.previous()
        test = self.expression.parse_expression()
        self.stream.consume(TokenType.COLON, "Expect ':' after condition.")
        body = self.block()
        
        llm_fallback = self._parse_llm_fallback()
        stmt = self._loc(ast.While(test=test, body=body, orelse=[]), start_token)
        
        if llm_fallback:
            return self._loc(ast.LLMExceptionalStmt(primary=stmt, fallback=llm_fallback), start_token)
        return stmt

    def for_statement(self) -> ast.Stmt:
        start_token = self.stream.previous()
        
        expr1 = self.expression.parse_expression()
        
        target = None
        iter_expr = None
        
        if self.stream.match(TokenType.IN):
            # Case: for i in list
            target = expr1
            iter_expr = self.expression.parse_expression()
        elif self.stream.check(TokenType.COLON):
            # Case: for 10:  or  for ~behavior~:
            target = None
            iter_expr = expr1
        else:
            raise self.stream.error(self.stream.peek(), "Expect 'in' or ':' in for statement.")
            
        filter_condition = None
        if self.stream.match(TokenType.IF):
            filter_condition = self.expression.parse_expression()
            
        self.stream.consume(TokenType.COLON, "Expect ':' after for loop iterator.")
        body = self.block()
        
        llm_fallback = self._parse_llm_fallback()
        stmt = self._loc(ast.For(target=target, iter=iter_expr, body=body, orelse=[], filter_condition=filter_condition), start_token)
        
        if llm_fallback:
            return self._loc(ast.LLMExceptionalStmt(primary=stmt, fallback=llm_fallback), start_token)
        return stmt

    def expression_statement(self) -> ast.Stmt:
        expr = self.expression.parse_expression()
        
        # Check if it's an assignment or compound assignment
        if self.stream.match(TokenType.ASSIGN):
            value = self.expression.parse_expression()
            self.stream.consume_end_of_statement("Expect newline after assignment.")
            llm_fallback = self._parse_llm_fallback()
            stmt = self._loc(ast.Assign(targets=[expr], value=value), self.stream.previous())
            if llm_fallback:
                return self._loc(ast.LLMExceptionalStmt(primary=stmt, fallback=llm_fallback), self.stream.previous())
            return stmt
        
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
                llm_fallback = self._parse_llm_fallback()
                stmt = self._loc(ast.AugAssign(target=expr, op=op_str, value=value), self.stream.previous())
                if llm_fallback:
                    return self._loc(ast.LLMExceptionalStmt(primary=stmt, fallback=llm_fallback), self.stream.previous())
                return stmt
            
        self.stream.consume_end_of_statement("Expect newline after expression.")
        llm_fallback = self._parse_llm_fallback()
        stmt = self._loc(ast.ExprStmt(value=expr), self.stream.previous())
        if llm_fallback:
            return self._loc(ast.LLMExceptionalStmt(primary=stmt, fallback=llm_fallback), self.stream.previous())
        return stmt

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
                stmts.append(self.parse_statement())
                
        self.stream.consume(TokenType.DEDENT, "Expect dedent after block.")
        return stmts

    def _parse_llm_fallback(self) -> Optional[List[ast.Stmt]]:
        """Helper to parse llmexcept block or declarative retry."""
        # Skip optional newlines before llmexcept
        while self.stream.check(TokenType.NEWLINE):
            self.stream.advance()
            
        if self.stream.match(TokenType.LLM_EXCEPT):
            # Check for declarative retry: llmexcept retry "hint"
            if self.stream.match(TokenType.RETRY):
                hint = None
                if self.stream.check(TokenType.STRING):
                    hint = self.expression.parse_expression()
                
                retry_stmt = self._loc(ast.Retry(hint=hint), self.stream.previous())
                self.stream.consume_end_of_statement("Expect newline after declarative retry.")
                return [retry_stmt]
            else:
                self.stream.consume(TokenType.COLON, "Expect ':' after llmexcept.")
                return self.block()
        return None

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
             
        llm_fallback = self._parse_llm_fallback()
        stmt = self._loc(ast.Try(body=body, handlers=handlers, orelse=orelse, finalbody=finalbody), start_token)
        
        if llm_fallback:
            return self._loc(ast.LLMExceptionalStmt(primary=stmt, fallback=llm_fallback), start_token)
        return stmt

    def raise_statement(self) -> ast.Raise:
        start_token = self.stream.previous()
        exc = None
        if not self.stream.check(TokenType.NEWLINE) and not self.stream.is_at_end():
            exc = self.expression.parse_expression()
        self.stream.consume_end_of_statement("Expect newline after raise.")
        return self._loc(ast.Raise(exc=exc), start_token)
