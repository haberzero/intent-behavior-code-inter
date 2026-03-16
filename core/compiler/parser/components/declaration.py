from typing import List, Optional, Union, TYPE_CHECKING
from core.compiler.lexer.tokens import TokenType, Token
from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.core.token_stream import TokenStream as ParserTokenStream
from core.domain import ast as ast
from core.domain.issue import Severity
from core.compiler.parser.core.component import BaseComponent
from core.compiler.parser.core.recognizer import SyntaxRecognizer, SyntaxRole
from core.compiler.parser.core.token_stream import TokenStream, ParseControlFlowError

if TYPE_CHECKING:
    from core.compiler.parser.components.expression import ExpressionComponent
    from core.compiler.parser.components.statement import StatementComponent
    from core.compiler.parser.components.type_def import TypeComponent

class DeclarationComponent(BaseComponent):
    def __init__(self, context):
        super().__init__(context)
        # self.expression = expr_component <-- Removed, use context
        # self.statement = stmt_component <-- Removed, use context
        # self.type_def = type_component <-- Removed, use context
        
        # Link statement component back to this declaration component <-- Removed, handled by Mediator

    @property
    def expression(self) -> 'ExpressionComponent':
        return self.context.expression_parser

    @property
    def statement(self) -> 'StatementComponent':
        return self.context.statement_parser

    @property
    def type_def(self) -> 'TypeComponent':
        return self.context.type_parser

    def parse_declaration(self) -> Optional[ast.IbStmt]:
        role = SyntaxRecognizer.get_role(self.stream)
        
        # [NEW] 提前消费待处理意图注释，准备进行侧表涂抹关联
        # 无论是什么类型的语句，都应该在这里消费意图，防止遗留到子节点
        pending_intents = self.context.consume_intents()

        stmt = None
        if role in (SyntaxRole.INTENT_MARKER, SyntaxRole.INTENT_DEFINITION):
            # [IES 2.0] 统一交由 StatementComponent 处理意图标记与语句
            stmt = self.statement.parse_statement()
        elif role == SyntaxRole.FUNCTION_DEFINITION:
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
        
        if pending_intents and stmt is not None:
            # [NEW] 涂抹式关联：暂存在节点对象上，由 SemanticAnalyzer 转入侧表，实现 AST 扁平化
            setattr(stmt, "_pending_intents", pending_intents)
            
        return stmt

    def intent_declaration(self) -> ast.IbIntentStmt:
        start_token = self.stream.previous() # intent
        
        is_exclusive = False
        if self.stream.match(TokenType.NOT): # !
            is_exclusive = True
            
        # 允许表达式而非仅字符串
        intent_expr = self.expression.parse_expression()
        
        self.stream.consume(TokenType.COLON, "Expect ':' before intent body.")
        
        body = self.statement.block()
        end_token = self.stream.previous() # DEDENT
        
        # 将表达式封装为 IntentInfo
        # 如果是 Constant 且为 string，则填充 content
        content = ""
        if isinstance(intent_expr, ast.IbConstant) and isinstance(intent_expr.value, str):
            content = intent_expr.value
            intent_expr = None
            
        info = ast.IbIntentInfo(
            mode="!" if is_exclusive else "", 
            content=content, 
            expr=intent_expr,
            lineno=start_token.line,
            col_offset=start_token.column
        )
        return self._loc(ast.IbIntentStmt(intent=info, body=body, is_exclusive=is_exclusive), start_token, end_token)

    def variable_declaration(self, explicit_var: bool = False) -> ast.IbAssign:
        type_token = None
        type_annotation = None
        
        if explicit_var:
            # 'var' keyword already consumed
            type_token = self.stream.previous()
            
            # [IES 2.1 Axiom] 从元数据注册表解析 'var' 标识符，消除硬编码
            var_name = "var"
            if self.context.metadata:
                var_desc = self.context.metadata.resolve("var")
                if var_desc:
                    var_name = var_desc.name
            
            type_annotation = self._loc(ast.IbName(id=var_name, ctx='Load'), type_token)
            
            name_token = self.stream.consume(TokenType.IDENTIFIER, "Expect variable name.")
            
            # Optional type override: var x: int = 1
            if self.stream.match(TokenType.COLON):
                type_annotation = self.type_def.parse_type_annotation()
        else:
            # Parse type annotation: int x = 1
            start_token = self.stream.peek()
            type_annotation = self.type_def.parse_type_annotation()
            type_token = start_token
            name_token = self.stream.consume(TokenType.IDENTIFIER, "Expect variable name.")

        target = self._loc(ast.IbName(id=name_token.value, ctx='Store'), name_token)
        if type_annotation:
            target = self._loc(ast.IbTypeAnnotatedExpr(target=target, annotation=type_annotation), type_token)
        
        value = None
        if self.stream.match(TokenType.ASSIGN):
            value = self.expression.parse_expression()
        
        self.stream.consume_end_of_statement("Expect newline after variable declaration.")
        end_token = self.stream.previous()
        
        # 解析可选的 llmexcept 块
        llm_fallback = self.statement._parse_llm_fallback()
        if llm_fallback:
             end_token = self.stream.previous()
             
        stmt = self._loc(ast.IbAssign(targets=[target], value=value), type_token, end_token)
        
        if llm_fallback:
            stmt.llm_fallback = llm_fallback
        return stmt

    def function_declaration(self) -> ast.IbFunctionDef:
        start_token = self.stream.previous()
        name = self.stream.consume(TokenType.IDENTIFIER, "Expect function name.").value
        self.stream.consume(TokenType.LPAREN, "Expect '(' after function name.")
        args = self.parameters()
        self.stream.consume(TokenType.RPAREN, "Expect ')' after parameters.")
        
        returns = None
        if self.stream.match(TokenType.ARROW):
            returns = self.type_def.parse_type_annotation()
            
        self.stream.consume(TokenType.COLON, "Expect ':' before function body.")
        
        func_node = self._loc(ast.IbFunctionDef(name=name, args=args, body=[], returns=returns), start_token)
        
        body = self.statement.block()
        func_node.body = body
        return self._extend_loc(func_node, self.stream.previous())

    def llm_function_declaration(self) -> ast.IbLLMFunctionDef:
        start_token = self.stream.previous()
        name = self.stream.consume(TokenType.IDENTIFIER, "Expect LLM function name.").value
        self.stream.consume(TokenType.LPAREN, "Expect '(' after function name.")
        args = self.parameters()
        self.stream.consume(TokenType.RPAREN, "Expect ')' after parameters.")
        
        returns = None
        if self.stream.match(TokenType.ARROW):
            returns = self.type_def.parse_type_annotation()
            
        self.stream.consume(TokenType.COLON, "Expect ':' before function body.")
        
        llm_node = self._loc(ast.IbLLMFunctionDef(name=name, args=args, sys_prompt=None, user_prompt=None, returns=returns), start_token)
        
        sys_prompt, user_prompt = self.llm_body()
        llm_node.sys_prompt = sys_prompt
        llm_node.user_prompt = user_prompt
        
        return self._extend_loc(llm_node, self.stream.previous())

    def class_declaration(self) -> ast.IbClassDef:
        start_token = self.stream.previous()
        name = self.stream.consume(TokenType.IDENTIFIER, "Expect class name.").value
        
        parent = None
        if self.stream.match(TokenType.LPAREN):
            parent = self.stream.consume(TokenType.IDENTIFIER, "Expect parent class name.").value
            self.stream.consume(TokenType.RPAREN, "Expect ')' after parent class name.")
            
        self.stream.consume(TokenType.COLON, "Expect ':' before class body.")
        
        class_node = self._loc(ast.IbClassDef(name=name, parent=parent, body=[], methods=[], fields=[]), start_token)
        
        body = self.statement.block()
        
        # Categorize body elements
        for stmt in body:
            if isinstance(stmt, (ast.IbFunctionDef, ast.IbLLMFunctionDef)):
                class_node.methods.append(stmt)
            elif isinstance(stmt, ast.IbAssign):
                class_node.fields.append(stmt)
            else:
                # Other statements in class body (e.g. print) are allowed but not common
                pass
        
        class_node.body = body
        return self._extend_loc(class_node, self.stream.previous())

    def parameters(self) -> List[ast.IbArg]:
        params = []
        if not self.stream.check(TokenType.RPAREN):
            while True:
                # [REMOVED] 特殊的 self 处理逻辑已被移除，改为隐式注入
                
                # Standard typed parameter: Type Name
                annotation = self.type_def.parse_type_annotation(ast.IbPrecedence.TUPLE)
                name_token = self.stream.consume(TokenType.IDENTIFIER, "Expect parameter name.")
                
                param_node = self._loc(ast.IbArg(arg=name_token.value), name_token)
                if annotation:
                    param_node = self._loc(ast.IbTypeAnnotatedExpr(target=param_node, annotation=annotation), name_token)
                params.append(param_node)
                    
                if not self.stream.match(TokenType.COMMA):
                    break
        return params

    def llm_body(self) -> tuple[Optional[List[Union[str, ast.IbExpr]]], Optional[List[Union[str, ast.IbExpr]]]]:
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
                raise self.stream.error(self.stream.peek(), "Unexpected token in LLM block. Expect '__sys__', '__user__', or 'llmend'.", code="PAR_002")

        self.stream.consume(TokenType.LLM_END, "Expect 'llmend' to close LLM block.")
        return sys_prompt, user_prompt

    def parse_llm_section_content(self) -> List[Union[str, ast.IbExpr]]:
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
                raise self.stream.error(self.stream.peek(), "Unexpected token in LLM section content.", code="PAR_002")
        
        return segments
