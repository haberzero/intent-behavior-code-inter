from typing import List, Optional, TYPE_CHECKING
from core.compiler.common.tokens import TokenType
from core.compiler.parser.core.token_stream import ParseControlFlowError
from core.kernel import ast as ast
from core.kernel.intent_logic import IntentMode
from core.compiler.parser.core.component import BaseComponent
from core.compiler.parser.core.syntax import ID_VAR, COMPOUND_OP_MAP

if TYPE_CHECKING:
    from core.compiler.parser.components.expression import ExpressionComponent
    from core.compiler.parser.components.declaration import DeclarationComponent

class StatementComponent(BaseComponent):
    def __init__(self, context):
        super().__init__(context)
        # self.expression = expression_component  <-- Removed, use context
        # self.decl_parser = None <-- Removed, use context

    @property
    def expression(self) -> 'ExpressionComponent':
        return self.context.expression_parser

    @property
    def decl_parser(self) -> 'DeclarationComponent':
        return self.context.declaration_parser

    # Removed set_decl_parser method

    def parse_statement(self) -> ast.IbStmt:
        """所有语句的统一入口"""
        return self._parse_statement_core()

    def _parse_statement_core(self) -> ast.IbStmt:
        """核心语句解析逻辑"""
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
            return self._loc(ast.IbPass(), start)
        if self.stream.match(TokenType.BREAK):
            start = self.stream.previous()
            self.stream.consume_end_of_statement("Expect newline after break.")
            return self._loc(ast.IbBreak(), start)
        if self.stream.match(TokenType.CONTINUE):
            start = self.stream.previous()
            self.stream.consume_end_of_statement("Expect newline after continue.")
            return self._loc(ast.IbContinue(), start)
        if self.stream.match(TokenType.RETRY):
            start = self.stream.previous()
            hint = None
            if self.stream.check(TokenType.STRING):
                hint = self.expression.parse_expression()
            self.stream.consume_end_of_statement("Expect newline after retry.")
            return self._loc(ast.IbRetry(hint=hint), start)
        
        if self.stream.match(TokenType.LLM_EXCEPT):
            return self.llm_except_statement()
        
        if self.stream.match(TokenType.INTENT_STMT):
            return self.intent_statement()
        if self.stream.match(TokenType.INTENT):
            return self.at_intent_shorthand()
        

        # 严禁在非顶层（如代码块、函数、类内部）使用 import。
        # 这一限制保证了调度器（Scheduler）可以高效地进行“无副作用”的依赖扫描。
        if self.stream.check(TokenType.IMPORT) or self.stream.check(TokenType.FROM):
            raise self.stream.error(self.stream.peek(), 
                             "Import statements are only allowed at the top level of a module.", 
                             code="PAR_002")
        
        return self.expression_statement()

    def return_statement(self) -> ast.IbReturn:
        start_token = self.stream.previous()
        value = None
        if not self.stream.check(TokenType.NEWLINE) and not self.stream.is_at_end():
            value = self.expression.parse_expression()
        self.stream.consume_end_of_statement("Expect newline after return.")
        return self._loc(ast.IbReturn(value=value), start_token)

    def global_statement(self) -> ast.IbGlobalStmt:
        start_token = self.stream.previous()
        names = []
        while True:
            name_token = self.stream.consume(TokenType.IDENTIFIER, "Expect variable name in global declaration.")
            names.append(name_token.value)
            if not self.stream.match(TokenType.COMMA):
                break
        self.stream.consume_end_of_statement("Expect newline after global declaration.")
        return self._loc(ast.IbGlobalStmt(names=names), start_token)

    def llm_except_statement(self) -> ast.IbLLMExceptionalStmt:
        """
        解析 llmexcept 语句。
        llmexcept 是一个独立的语句，它的 target 应该由前一个语句提供。
        在语义分析阶段进行合法性检查。
        
        语法：
            statement
            llmexcept:
                statements...
            
            statement
            llmexcept retry "hint"
        """
        start_token = self.stream.previous()
        
        # 消费换行符
        while self.stream.check(TokenType.NEWLINE):
            self.stream.advance()
        
        # 检查是否是 llmexcept retry 形式
        if self.stream.match(TokenType.RETRY):
            # llmexcept retry "hint"
            hint = None
            if self.stream.check(TokenType.STRING):
                hint = self.expression.parse_expression()
            
            retry_stmt = self._loc(ast.IbRetry(hint=hint), self.stream.previous())
            self.stream.consume_end_of_statement("Expect newline after llmexcept retry.")
            
            return self._loc(
                ast.IbLLMExceptionalStmt(target=None, body=[retry_stmt]),
                start_token
            )
        
        # llmexcept: 形式
        self.stream.consume(TokenType.COLON, "Expect ':' after llmexcept.")
        
        # 解析 llmexcept 块
        body = self.llm_except_body()
        
        return self._loc(
            ast.IbLLMExceptionalStmt(target=None, body=body),
            start_token
        )

    def llm_except_body(self) -> List[ast.IbStmt]:
        """
        解析 llmexcept 块的内容。
        使用与 block() 相同的缩进检测机制。
        """
        self.stream.consume(TokenType.NEWLINE, "Expect newline before llmexcept body.")
        self.stream.consume(TokenType.INDENT, "Expect indent after llmexcept ':'.")
        
        body = []
        while not self.stream.check(TokenType.DEDENT) and not self.stream.is_at_end():
            if self.stream.match(TokenType.NEWLINE):
                continue
            
            # llmexcept 块内的语句不再处理 llmexcept
            stmt = self.parse_statement()
            body.append(stmt)
        
        self.stream.consume(TokenType.DEDENT, "Expect dedent after llmexcept body.")
        return body

    def intent_statement(self) -> ast.IbIntentStmt:
        """Parse 'intent "content": block'"""
        start_token = self.stream.previous()
        
        # 1. Parse content (string or variable)
        intent_info = self._parse_intent_info(start_token)
        
        # 2. Parse block
        self.stream.consume(TokenType.COLON, "Expect ':' after intent.")
        body = self.block()
        
        return self._loc(ast.IbIntentStmt(intent=intent_info, body=body), start_token)

    def at_intent_shorthand(self) -> ast.IbStmt:
        """Parse '@ "content" \n statement'"""
        start_token = self.stream.previous()
        
        # 1. Parse content
        intent_info = self._parse_intent_info(start_token)
        
        # 2. 压入 Pending Intents，下一个被解析的语句将自动关联它
        self.context.push_intent(intent_info)
        
        # 3. 解析下一个语句作为主体
        # 使用 consume_end_of_statement 处理换行或 EOF
        self.stream.consume_end_of_statement("Expect newline after @ shorthand.")
        
        # 重要：使用 declaration() 而非 parse_statement()，以支持 @ 下面的 var/func 定义
        return self.context.declaration_parser.parse_declaration()

    def _parse_intent_info(self, start_token) -> ast.IbIntentInfo:
        """Parse 'mode "content"' or 'mode identifier'"""
        # 1. Parse mode
        mode = IntentMode.APPEND
        token_val = start_token.value
        
        if token_val.startswith("@"):
            mode_char = token_val[1:]
            if mode_char == "+": mode = IntentMode.APPEND
            elif mode_char == "!": mode = IntentMode.OVERRIDE
            elif mode_char == "-": mode = IntentMode.REMOVE
        else:
            # Handle 'intent ! "content":'
            if self.stream.match(TokenType.NOT):
                mode = IntentMode.OVERRIDE
            elif self.stream.match(TokenType.PLUS):
                mode = IntentMode.APPEND
            elif self.stream.match(TokenType.MINUS):
                mode = IntentMode.REMOVE
            
            # 支持模式别名，消除硬编码字符串
            elif self.stream.check(TokenType.IDENTIFIER):
                peek_val = self.stream.peek().value.lower()
                if peek_val in ("append", "add"):
                    self.stream.advance()
                    mode = IntentMode.APPEND
                elif peek_val in ("override", "exclusive"):
                    self.stream.advance()
                    mode = IntentMode.OVERRIDE
                elif peek_val in ("remove", "delete"):
                    self.stream.advance()
                    mode = IntentMode.REMOVE
            
        segments = []
        tag = None
        
        while not self.stream.check(TokenType.COLON) and not self.stream.check(TokenType.NEWLINE) and not self.stream.is_at_end():
            if self.stream.match(TokenType.RAW_TEXT):
                val = self.stream.previous().value
                # 解析意图标签 #tag
                # TODO 应该从lexer开始就提供支持。现在是临时方案
                if tag is None and not segments and val.startswith("#"):
                    # 尝试提取标签
                    import re
                    match = re.match(r"^#([a-zA-Z0-9_]+)\s*", val)
                    if match:
                        tag = match.group(1)
                        remaining = val[match.end():]
                        if remaining:
                            segments.append(remaining)
                        continue
                segments.append(val)
            elif self.stream.match(TokenType.STRING):
                val = self.stream.previous().value
                # Strip quotes if present
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                segments.append(val)
            elif self.stream.check(TokenType.VAR_REF):
                # Variable reference $var or $(expr)
                # Use check instead of match, so parse_expression can consume the token
                segments.append(self.expression.parse_expression())
            else:

                # 尝试解析表达式段。若解析失败则停止消费意图内容。
                # 开启静默前瞻模式，防止解析失败污染诊断状态。
                with self.stream.speculate():
                    try:
                        segments.append(self.expression.parse_expression())
                    except ParseControlFlowError:
                        break
                
        # If single segment and it's a string, we can flatten it
        content = "".join([s if isinstance(s, str) else str(s) for s in segments]).strip()
        return ast.IbIntentInfo(mode=mode, content=content, segments=segments, tag=tag)


    def if_statement(self) -> ast.IbStmt:
        start_token = self.stream.previous()
        
        # 1. Parse initial IF
        test = self.expression.parse_expression()
        self.stream.consume(TokenType.COLON, "Expect ':' after if condition.")
        body = self.block()
        end_token = self.stream.previous() # DEDENT
        
        root_if = self._loc(ast.IbIf(test=test, body=body, orelse=[]), start_token, end_token)
        last_node = root_if
        
        # 2. Parse ELIF chain
        while self.stream.match(TokenType.ELIF):
            elif_start = self.stream.previous()
            elif_test = self.expression.parse_expression()
            self.stream.consume(TokenType.COLON, "Expect ':' after elif condition.")
            elif_body = self.block()
            elif_end = self.stream.previous() # DEDENT
            
            new_if = self._loc(ast.IbIf(test=elif_test, body=elif_body, orelse=[]), elif_start, elif_end)
            last_node.orelse = [new_if]
            last_node = new_if
            # Extend root if range to cover elif
            self._extend_loc(root_if, elif_end)
            
        # 3. Parse ELSE
        if self.stream.match(TokenType.ELSE):
            self.stream.consume(TokenType.COLON, "Expect ':' after else.")
            last_node.orelse = self.block()
            else_end = self.stream.previous() # DEDENT
            # Extend root if range to cover else
            self._extend_loc(root_if, else_end)
            
        return root_if

    def while_statement(self) -> ast.IbStmt:
        start_token = self.stream.previous()
        test = self.expression.parse_expression()
        
        # Parse optional filter: while x > 0 if is_ready():
        if self.stream.match(TokenType.IF):
            filter_expr = self.expression.parse_expression()
            test = self._loc(ast.IbFilteredExpr(expr=test, filter=filter_expr), start_token)
            
        self.stream.consume(TokenType.COLON, "Expect ':' after condition.")
        body = self.block()
        end_token = self.stream.previous() # DEDENT
        
        return self._loc(ast.IbWhile(test=test, body=body, orelse=[]), start_token, end_token)

    def for_statement(self) -> ast.IbStmt:
        start_token = self.stream.previous()
        
        # 支持带类型标注的循环目标 (e.g. for str name in names)
        # 或者元组声明 (e.g. for (int x, int y) in coords)
        from core.compiler.parser.core.recognizer import SyntaxRecognizer, SyntaxRole
        
        target_candidate = None
        if SyntaxRecognizer.get_role(self.stream) == SyntaxRole.VARIABLE_DECLARATION:
            # 这是一个带类型的声明作为目标
            target_candidate = self._parse_for_loop_target()
        else:
            target_candidate = self.expression.parse_expression()
        
        target = None
        iter_expr = None
        
        if self.stream.match(TokenType.IN):
            # 情况 1: for i in list  或  for str name in names
            target = target_candidate
            iter_expr = self.expression.parse_expression()
        elif self.stream.check(TokenType.COLON):
            # 情况 2: for 10:  或  for @~...~: (条件驱动模式)
            # 此时 target_candidate 实际上就是迭代/条件表达式
            target = None
            iter_expr = target_candidate
        else:
            raise self.stream.error(self.stream.peek(), "Expect 'in' or ':' in for statement.", code="PAR_001")
            
        if self.stream.match(TokenType.IF):
            filter_expr = self.expression.parse_expression()
            iter_expr = self._loc(ast.IbFilteredExpr(expr=iter_expr, filter=filter_expr), self.stream.previous())
            
        self.stream.consume(TokenType.COLON, "Expect ':' after for loop iterator.")
        body = self.block()
        end_token = self.stream.previous() # DEDENT
        
        return self._loc(ast.IbFor(target=target, iter=iter_expr, body=body, orelse=[]), start_token, end_token)

    def _parse_for_loop_target(self) -> ast.IbExpr:
        """解析循环变量目标，支持 (int x, int y) 或 str name"""
        if self.stream.match(TokenType.LPAREN):
            # 解析元组声明 (int x, int y)
            start_token = self.stream.previous()
            elts = []
            while True:
                # 递归解析单个声明
                type_node = self.context.type_parser.parse_type_annotation()
                name_token = self.stream.consume(TokenType.IDENTIFIER, "Expect loop variable name.")
                name_node = self._loc(ast.IbName(id=name_token.value, ctx='Store'), name_token)
                elts.append(self._loc(ast.IbTypeAnnotatedExpr(target=name_node, annotation=type_node), type_node))
                
                if not self.stream.match(TokenType.COMMA):
                    break
            
            end_token = self.stream.consume(TokenType.RPAREN, "Expect ')' after typed tuple.")
            return self._loc(ast.IbTuple(elts=elts, ctx='Store'), start_token, end_token)
        else:
            # 解析单个声明 str name
            type_node = self.context.type_parser.parse_type_annotation()
            name_token = self.stream.consume(TokenType.IDENTIFIER, "Expect loop variable name.")
            name_node = self._loc(ast.IbName(id=name_token.value, ctx='Store'), name_token)
            return self._loc(ast.IbTypeAnnotatedExpr(target=name_node, annotation=type_node), type_node)

    def expression_statement(self) -> ast.IbStmt:
        expr = self.expression.parse_expression()
        
        # Check if it's an assignment or compound assignment
        if self.stream.match(TokenType.ASSIGN):
            value = self.expression.parse_expression()
            self.stream.consume_end_of_statement("Expect newline after assignment.")
            return self._loc(ast.IbAssign(targets=[expr], value=value), expr)
        
        # 3. AugAssign (a += 1)
        # 使用 COMPOUND_OP_MAP 映射复合赋值运算符
        for token_type, op_str in COMPOUND_OP_MAP.items():
            if self.stream.match(token_type):
                value = self.expression.parse_expression()
                self.stream.consume_end_of_statement("Expect newline after assignment.")
                return self._loc(ast.IbAugAssign(target=expr, op=op_str, value=value), expr)
        
        # 4. Pure Expression Statement
        self.stream.consume_end_of_statement("Expect newline after expression.")
        return self._loc(ast.IbExprStmt(value=expr), expr)

    def block(self) -> List[ast.IbStmt]:
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

    def _parse_llm_fallback(self) -> Optional[List[ast.IbStmt]]:
        """Helper to parse llmexcept block or declarative retry."""
        # Skip optional newlines before llmexcept/llmretry
        # [AUDIT] 必须在 peek 之前消费换行符，否则 match 会因为位置不对而失败
        while self.stream.check(TokenType.NEWLINE):
            self.stream.advance()
            
        if self.stream.match(TokenType.LLM_EXCEPT):
            # Check for declarative retry: llmexcept retry "hint"
            if self.stream.match(TokenType.RETRY):
                hint = None
                if self.stream.check(TokenType.STRING):
                    hint = self.expression.parse_expression()
                
                retry_stmt = self._loc(ast.IbRetry(hint=hint), self.stream.previous())
                self.stream.consume_end_of_statement("Expect newline after declarative retry.")
                return [retry_stmt]
            else:
                self.stream.consume(TokenType.COLON, "Expect ':' after llmexcept.")
                return self.block()
        
        # Check for syntactic sugar: llmretry "hint"
        if self.stream.match(TokenType.LLM_RETRY):
            hint = None
            if self.stream.check(TokenType.STRING):
                hint = self.expression.parse_expression()
            
            retry_stmt = self._loc(ast.IbRetry(hint=hint), self.stream.previous())
            self.stream.consume_end_of_statement("Expect newline after llmretry sugar.")
            return [retry_stmt]

        return None

    def try_statement(self) -> ast.IbTry:
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
            handlers.append(self._loc(ast.IbExceptHandler(type=type_expr, name=name, body=handler_body), handler_start))
        
        orelse = []
        if self.stream.match(TokenType.ELSE):
            self.stream.consume(TokenType.COLON, "Expect ':' after else.")
            orelse = self.block()
            
        finalbody = []
        if self.stream.match(TokenType.FINALLY):
            self.stream.consume(TokenType.COLON, "Expect ':' after finally.")
            finalbody = self.block()
            
        if not handlers and not finalbody:
             raise self.stream.error(start_token, "Expect 'except' or 'finally' after 'try'.", code="PAR_001")
             
        return self._loc(ast.IbTry(body=body, handlers=handlers, orelse=orelse, finalbody=finalbody), start_token)

    def raise_statement(self) -> ast.IbRaise:
        start_token = self.stream.previous()
        exc = None
        if not self.stream.check(TokenType.NEWLINE) and not self.stream.is_at_end():
            exc = self.expression.parse_expression()
        self.stream.consume_end_of_statement("Expect newline after raise.")
        return self._loc(ast.IbRaise(exc=exc), start_token)
