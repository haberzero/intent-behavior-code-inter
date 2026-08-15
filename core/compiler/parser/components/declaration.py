from typing import List, Optional, Union, TYPE_CHECKING
from core.base.diagnostics.codes import PAR_INVALID_SYNTAX, PAR_UNEXPECTED_TOKEN
from core.compiler.common.tokens import TokenType, Token

from core.compiler.parser.core.token_stream import TokenStream as ParserTokenStream
from core.kernel import ast as ast
from core.kernel.issue import Severity
from core.compiler.parser.core.component import BaseComponent
from core.compiler.parser.core.syntax import ID_AUTO, IbPrecedence
from core.kernel.intent_logic import IntentMode
from core.compiler.parser.core.recognizer import SyntaxRecognizer, SyntaxRole
from core.compiler.parser.core.token_stream import TokenStream, ParseControlFlowError
from core.compiler.parser.components.type_def import ID_FN

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

        stmt = None
        if role == SyntaxRole.LLM_EXCEPT:
            self.stream.advance()  # 消费 llmexcept keyword
            stmt = self.statement.llm_except_statement()
        elif role == SyntaxRole.INTENT_MARKER:
            # 统一交由 StatementComponent 处理意图标记与语句
            stmt = self.statement.parse_statement()
        elif role == SyntaxRole.FUNCTION_DEFINITION:
            self.stream.advance() # func
            stmt = self.function_declaration()
        elif role == SyntaxRole.LLM_DEFINITION:
            stmt = self.llm_function_declaration()
        elif role == SyntaxRole.CLASS_DEFINITION:
            self.stream.advance() # class
            stmt = self.class_declaration()
        elif role == SyntaxRole.PROTOCOL_DEFINITION:
            self.stream.advance() # protocol
            stmt = self.protocol_declaration()
        elif role == SyntaxRole.IMPL_DEFINITION:
            self.stream.advance() # impl
            stmt = self.impl_declaration()
        elif role == SyntaxRole.VARIABLE_DECLARATION:
            explicit_auto = self.stream.match(TokenType.AUTO)
            explicit_fn = (not explicit_auto) and self.stream.match(TokenType.FN)
            stmt = self.variable_declaration(explicit_auto=explicit_auto, explicit_fn=explicit_fn)
        else:
            stmt = self.statement.parse_statement()
        
        return stmt

    def variable_declaration(self, explicit_auto: bool = False, explicit_fn: bool = False) -> ast.IbAssign:
        """
        变量/资产声明。
        格式：
        1. auto x = 1 (推导类型)
        2. fn f = myFunc (可调用类型推导，类似 auto 但限于可调用)
        3. int x = 1 (显式类型)
        4. auto x: int = 1 (显式覆盖)
        5. (int x, int y) = (10, 20) (元组解包声明)
        """
        # Handle tuple destructuring declaration: (int x, int y) = expr
        if not explicit_auto and not explicit_fn and self.stream.check(TokenType.LPAREN):
            return self._tuple_variable_declaration()

        type_token = None
        type_annotation = None
        
        if explicit_auto:
            # 'auto' keyword already consumed
            type_token = self.stream.previous()
            
            # 使用语法常量，消除硬编码
            auto_name = ID_AUTO
            if self.context.metadata:
                auto_desc = self.context.metadata.resolve(ID_AUTO)
                if auto_desc:
                    auto_name = auto_desc.name
            
            type_annotation = self._loc(ast.IbName(id=auto_name, ctx='Load'), type_token)

            name_token = self.stream.consume(TokenType.IDENTIFIER, "Expect variable name.")
            
            # Optional type override: auto x: int = 1
            if self.stream.match(TokenType.COLON):
                type_annotation = self.type_def.parse_type_annotation()
        elif explicit_fn:
            # 'fn' keyword already consumed — callable type inference
            type_token = self.stream.previous()
            # check for fn[(...)→(...)] callable signature form before
            # defaulting to bare fn type annotation.
            if self.stream.check(TokenType.LBRACKET):
                callable_sig = self.type_def._try_parse_callable_sig(type_token)
                if callable_sig is not None:
                    type_annotation = callable_sig
                else:
                    type_annotation = self._loc(ast.IbName(id=ID_FN, ctx='Load'), type_token)
            else:
                type_annotation = self._loc(ast.IbName(id=ID_FN, ctx='Load'), type_token)
            name_token = self.stream.consume(TokenType.IDENTIFIER, "Expect variable name after 'fn'.")
        else:
            # Parse type annotation: int x = 1, str name = "hi", etc.
            start_token = self.stream.peek()
            type_annotation = self.type_def.parse_type_annotation()
            type_token = start_token

            # Reject 'RETURN_TYPE fn NAME' pattern: declaration-side return type is not supported.
            # Use expression-side syntax: `fn NAME = lambda -> TYPE: EXPR`
            # For example: `fn f = lambda -> int: 1 + 1` or `fn f = lambda(int a) -> str: "hi"`.
            if self.stream.match(TokenType.FN):
                fn_token = self.stream.previous()
                raise self.stream.error(
                    fn_token,
                    "Declaration-side return type annotation 'TYPE fn NAME = ...' is not supported. "
                    "Return types must be specified on the expression side: 'fn NAME = lambda -> TYPE: EXPR'. "
                    "For example: 'fn f = lambda -> int: 1 + 1' or 'fn f = lambda(int a) -> str: \"hi\"'.",
                    code=PAR_INVALID_SYNTAX,
                )
            else:
                name_token = self.stream.consume(TokenType.IDENTIFIER, "Expect variable name.")

        target = self._loc(ast.IbName(id=name_token.value, ctx='Store'), name_token)
        if type_annotation:
            target = self._loc(ast.IbTypeAnnotatedExpr(target=target, annotation=type_annotation), type_token)

        # 裸列形式元组解包：`int a, int b = t` / `auto a, auto b = t` / `int a, str b = (1, "x")`
        # 与括号形式 `(int a, int b) = t` 等价。要求所有分量同样以变量声明开头
        # （即每个分量都需要 type / auto / fn 引导，允许其后再带类型注解的标识符）。
        if self.stream.check(TokenType.COMMA):
            elts = [target]
            while self.stream.match(TokenType.COMMA):
                elt_type_token = self.stream.peek()
                if self.stream.match(TokenType.AUTO):
                    auto_name = ID_AUTO
                    if self.context.metadata:
                        auto_desc = self.context.metadata.resolve(ID_AUTO)
                        if auto_desc:
                            auto_name = auto_desc.name
                    elt_annotation = self._loc(ast.IbName(id=auto_name, ctx='Load'), elt_type_token)
                else:
                    elt_annotation = self.type_def.parse_type_annotation()
                elt_name_token = self.stream.consume(TokenType.IDENTIFIER, "Expect variable name in tuple destructuring.")
                elt_name_node = self._loc(ast.IbName(id=elt_name_token.value, ctx='Store'), elt_name_token)
                elt = self._loc(
                    ast.IbTypeAnnotatedExpr(target=elt_name_node, annotation=elt_annotation),
                    elt_type_token,
                )
                elts.append(elt)

            tuple_target = self._loc(ast.IbTuple(elts=elts, ctx='Store'), type_token)

            value = None
            if self.stream.match(TokenType.ASSIGN):
                value = self.expression.parse_expression()

            self.stream.consume_end_of_statement("Expect newline after tuple destructuring declaration.")
            end_token = self.stream.previous()

            return self._loc(
                ast.IbAssign(targets=[tuple_target], value=value),
                type_token, end_token,
            )

        value = None
        if self.stream.match(TokenType.ASSIGN):
            value = self.expression.parse_expression()

        self.stream.consume_end_of_statement("Expect newline after variable declaration.")
        end_token = self.stream.previous()

        return self._loc(
            ast.IbAssign(targets=[target], value=value),
            type_token, end_token
        )

    def _tuple_variable_declaration(self) -> ast.IbAssign:
        """Parse (int x, int y) = expr tuple destructuring declaration."""
        start_token = self.stream.peek()
        self.stream.consume(TokenType.LPAREN, "Expect '('.")
        
        targets = []
        while not self.stream.check(TokenType.RPAREN) and not self.stream.is_at_end():
            type_token = self.stream.peek()
            type_annotation = self.type_def.parse_type_annotation()
            name_token = self.stream.consume(TokenType.IDENTIFIER, "Expect variable name.")
            name_node = self._loc(ast.IbName(id=name_token.value, ctx='Store'), name_token)
            target = self._loc(ast.IbTypeAnnotatedExpr(target=name_node, annotation=type_annotation), type_token)
            targets.append(target)
            if not self.stream.match(TokenType.COMMA):
                break
        
        self.stream.consume(TokenType.RPAREN, "Expect ')' after tuple declaration.")
        
        tuple_target = self._loc(ast.IbTuple(elts=targets, ctx='Store'), start_token)
        
        value = None
        if self.stream.match(TokenType.ASSIGN):
            value = self.expression.parse_expression()
        
        self.stream.consume_end_of_statement("Expect newline after declaration.")
        end_token = self.stream.previous()
        
        return self._loc(ast.IbAssign(targets=[tuple_target], value=value), start_token, end_token)

    def function_declaration(self) -> ast.IbFunctionDef:
        start_token = self.stream.previous()
        name = self.stream.consume(TokenType.IDENTIFIER, "Expect function name.").value

        type_params = []
        type_param_bounds = {}
        if self.stream.match(TokenType.LBRACKET):
            # 泛型函数：func identity[T](T x) -> T / func first[T: Proto](...)
            while True:
                tp_name = self.stream.consume(TokenType.IDENTIFIER, "Expect type parameter name.").value
                type_params.append(tp_name)
                if self.stream.match(TokenType.COLON):
                    bound = self.stream.consume(
                        TokenType.IDENTIFIER,
                        "Expect protocol name after ':' in type parameter bound.",
                    ).value
                    type_param_bounds[tp_name] = bound
                if not self.stream.match(TokenType.COMMA):
                    break
            self.stream.consume(TokenType.RBRACKET, "Expect ']' after type parameters.")

        self.stream.consume(TokenType.LPAREN, "Expect '(' after function name.")
        args = self.parameters()
        self.stream.consume(TokenType.RPAREN, "Expect ')' after parameters.")
        
        returns = None
        if self.stream.match(TokenType.ARROW):
            returns = self.type_def.parse_type_annotation()
            
        self.stream.consume(TokenType.COLON, "Expect ':' before function body.")
        
        func_node = self._loc(
            ast.IbFunctionDef(
                name=name, args=args, body=[], returns=returns,
                type_params=type_params, type_param_bounds=type_param_bounds,
            ),
            start_token,
        )
        
        body = self.statement.block()
        func_node.body = body
        return self._extend_loc(func_node, self.stream.previous())

    def llm_function_declaration(self) -> ast.IbLLMFunctionDef:
        start_token = self.stream.previous()
        self.stream.advance()
        if self.stream.check(TokenType.FUNC):
            self.stream.advance()
        name = self.stream.consume(TokenType.IDENTIFIER, "Expect LLM function name.").value
        self.stream.consume(TokenType.LPAREN, "Expect '(' after function name.")
        args = self.parameters()
        self.stream.consume(TokenType.RPAREN, "Expect ')' after parameters.")
        
        returns = None
        if self.stream.match(TokenType.ARROW):
            returns = self.type_def.parse_type_annotation()
            
        self.stream.consume(TokenType.COLON, "Expect ':' before function body.")
        
        llm_node = self._loc(ast.IbLLMFunctionDef(name=name, args=args, sys_prompt=None, user_prompt=None, retry_hint=None, returns=returns), start_token)
        
        sys_prompt, user_prompt, retry_hint = self.llm_body()
        llm_node.sys_prompt = sys_prompt
        llm_node.user_prompt = user_prompt
        llm_node.retry_hint = retry_hint
        
        return self._extend_loc(llm_node, self.stream.previous())

    def impl_declaration(self) -> ast.IbImplDef:
        """Parse a retroactive implementation declaration.

        Syntax::

            impl SomeProtocol for SomeType:
                func method(self, ...) -> Ret:
                    ...

        The body is optional: an empty body keeps the declaration-only
        form (record the protocol on the type), while a body of function
        definitions supplies missing protocol methods retroactively.
        """
        start_token = self.stream.previous()
        protocol_name = self.stream.consume(TokenType.IDENTIFIER, "Expect protocol name after 'impl'.").value
        self.stream.consume(TokenType.FOR, "Expect 'for' in impl declaration.")
        type_name = self.stream.consume(TokenType.IDENTIFIER, "Expect type name after 'for'.").value
        self.stream.consume(TokenType.COLON, "Expect ':' after impl declaration.")

        node = self._loc(
            ast.IbImplDef(protocol_name=protocol_name, type_name=type_name),
            start_token,
        )

        # 空 body（仅声明）或方法块：行尾后跟缩进即方法块。
        if not self.stream.match(TokenType.NEWLINE):
            raise self.stream.error(
                self.stream.peek(),
                "Expect newline after impl declaration.",
                code=PAR_UNEXPECTED_TOKEN,
            )
        if self.stream.match(TokenType.INDENT):
            # 方法块：func / llm func 方法定义（其它语句由 parser 拒绝）
            body: List[ast.IbStmt] = []
            while not self.stream.check(TokenType.DEDENT) and not self.stream.is_at_end():
                if self.stream.match(TokenType.NEWLINE):
                    continue
                if self.stream.check(TokenType.FUNC):
                    self.stream.advance()  # 消费 func
                    body.append(self.function_declaration())
                elif self.stream.check(TokenType.LLM_DEF):
                    body.append(self.llm_function_declaration())
                else:
                    raise self.stream.error(
                        self.stream.peek(),
                        "Only 'func' method definitions are allowed in an impl block.",
                        code=PAR_UNEXPECTED_TOKEN,
                    )
            self.stream.consume(TokenType.DEDENT, "Expect dedent after impl block.")
            node.body = body
            return self._extend_loc(node, self.stream.previous())
        return node

    def protocol_declaration(self) -> ast.IbProtocolDef:
        """Parse a protocol declaration.

        Syntax::

            protocol Name:
                func method(self, ...) -> Ret:
                    pass

        The method bodies are ignored; only signatures are kept in the
        protocol's TypeDef members.
        """
        start_token = self.stream.previous()
        name = self.stream.consume(TokenType.IDENTIFIER, "Expect protocol name.").value

        type_params = []
        if self.stream.match(TokenType.LBRACKET):
            while True:
                type_params.append(
                    self.stream.consume(TokenType.IDENTIFIER, "Expect protocol type parameter name.").value
                )
                if not self.stream.match(TokenType.COMMA):
                    break
            self.stream.consume(TokenType.RBRACKET, "Expect ']' after protocol type parameters.")

        parent = None
        if self.stream.match(TokenType.LPAREN):
            parent = self.stream.consume(TokenType.IDENTIFIER, "Expect parent protocol name.").value
            self.stream.consume(TokenType.RPAREN, "Expect ')' after parent protocol name.")

        self.stream.consume(TokenType.COLON, "Expect ':' before protocol body.")

        node = self._loc(
            ast.IbProtocolDef(name=name, parent=parent, type_params=type_params, body=[], methods=[]),
            start_token,
        )
        body = self.statement.block()
        node.body = body
        for stmt in body:
            if isinstance(stmt, ast.IbFunctionDef):
                node.methods.append(stmt)
        return self._extend_loc(node, self.stream.previous())


    def class_declaration(self) -> ast.IbClassDef:
        start_token = self.stream.previous()
        name = self.stream.consume(TokenType.IDENTIFIER, "Expect class name.").value

        type_params = []
        type_param_bounds = {}
        if self.stream.match(TokenType.LBRACKET):
            # 泛型类型参数：class Box[T] / class Box[T, U] / class Box[T: Proto]
            while True:
                tp_name = self.stream.consume(TokenType.IDENTIFIER, "Expect type parameter name.").value
                type_params.append(tp_name)
                if self.stream.match(TokenType.COLON):
                    bound = self.stream.consume(
                        TokenType.IDENTIFIER,
                        "Expect protocol name after ':' in type parameter bound.",
                    ).value
                    type_param_bounds[tp_name] = bound
                if not self.stream.match(TokenType.COMMA):
                    break
            self.stream.consume(TokenType.RBRACKET, "Expect ']' after type parameters.")
            if not type_params:
                raise self.stream.error(
                    self.stream.previous(),
                    "Type parameters must not be empty (e.g. class Box[T]).",
                    code=PAR_UNEXPECTED_TOKEN,
                )

        parent = None
        parent_args = []
        if self.stream.match(TokenType.LPAREN):
            parent = self.stream.consume(TokenType.IDENTIFIER, "Expect parent class name.").value
            # 父类泛型实参：class Sub[T](Box[T])
            if self.stream.match(TokenType.LBRACKET):
                while True:
                    parent_args.append(
                        self.stream.consume(TokenType.IDENTIFIER, "Expect parent type argument name.").value
                    )
                    if not self.stream.match(TokenType.COMMA):
                        break
                self.stream.consume(TokenType.RBRACKET, "Expect ']' after parent type arguments.")
            self.stream.consume(TokenType.RPAREN, "Expect ')' after parent class name.")

        implements = []
        implements_args = {}
        if self.stream.match(TokenType.IMPLEMENTS):
            while True:
                proto_name = self.stream.consume(TokenType.IDENTIFIER, "Expect protocol name after 'implements'.").value
                args = []
                if self.stream.match(TokenType.LBRACKET):
                    while True:
                        args.append(
                            self.stream.consume(TokenType.IDENTIFIER, "Expect protocol type argument.").value
                        )
                        if not self.stream.match(TokenType.COMMA):
                            break
                    self.stream.consume(TokenType.RBRACKET, "Expect ']' after protocol type arguments.")
                implements.append(proto_name)
                if args:
                    implements_args[proto_name] = args
                if not self.stream.match(TokenType.COMMA):
                    break

        self.stream.consume(TokenType.COLON, "Expect ':' before class body.")

        class_node = self._loc(
            ast.IbClassDef(name=name, parent=parent, parent_args=parent_args,
                           type_params=type_params, type_param_bounds=type_param_bounds,
                           implements=implements, implements_args=implements_args,
                           body=[], methods=[], fields=[]),
            start_token,
        )
        
        body = self.statement.block()
        
        # Categorize body elements
        for stmt in body:
            if isinstance(stmt, ast.IbFunctionDef):
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
            saw_var_pos = False
            saw_var_kw = False
            saw_default = False
            while True:
                if saw_var_kw:
                    raise self.stream.error(self.stream.peek(), "Parameter cannot follow '**kwargs'.", code=PAR_UNEXPECTED_TOKEN)
                if self.stream.check(TokenType.SELF):
                    self.stream.advance()
                    if not self.stream.match(TokenType.COMMA):
                        break
                    continue

                kind = ast.ARG_POSITIONAL_OR_KEYWORD
                if self.stream.match(TokenType.STAR_STAR):
                    kind = ast.ARG_VAR_KEYWORD
                elif self.stream.match(TokenType.STAR):
                    kind = ast.ARG_VAR_POSITIONAL

                if kind == ast.ARG_VAR_KEYWORD and saw_var_kw:
                    raise self.stream.error(self.stream.previous(), "Duplicate '**kwargs' parameter.", code=PAR_UNEXPECTED_TOKEN)
                if kind == ast.ARG_VAR_POSITIONAL and saw_var_pos:
                    raise self.stream.error(self.stream.previous(), "Duplicate '*args' parameter.", code=PAR_UNEXPECTED_TOKEN)

                if kind == ast.ARG_POSITIONAL_OR_KEYWORD:
                    annotation = self.type_def.parse_type_annotation(IbPrecedence.TUPLE)
                    name_token = self.stream.consume(TokenType.IDENTIFIER, "Expect parameter name.")

                    default = None
                    if self.stream.match(TokenType.ASSIGN):
                        # 默认值表达式以 TUPLE 优先级解析，避免吞掉后续参数分隔逗号
                        default = self.expression.parse_expression(IbPrecedence.TUPLE)
                        saw_default = True

                    # *args 之后的普通参数为 keyword-only（Python 语义）
                    if saw_var_pos:
                        kind = ast.ARG_KEYWORD_ONLY

                    param_node = self._loc(ast.IbArg(arg=name_token.value, annotation=annotation, default=default, kind=kind), name_token)
                else:
                    # *args / **kwargs：无类型标注、无默认值
                    name_token = self.stream.consume(TokenType.IDENTIFIER, "Expect parameter name.")
                    param_node = self._loc(ast.IbArg(arg=name_token.value, annotation=None, default=None, kind=kind), name_token)
                    if kind == ast.ARG_VAR_POSITIONAL:
                        saw_var_pos = True
                    else:
                        saw_var_kw = True

                if kind != ast.ARG_VAR_POSITIONAL and kind != ast.ARG_VAR_KEYWORD:
                    if saw_default and param_node.default is None and not saw_var_pos:
                        # 默认值后不允许出现无默认值的普通参数（keyword-only 除外）
                        raise self.stream.error(
                            self.stream.previous(),
                            f"Parameter '{param_node.arg}' cannot follow a parameter with a default value.",
                            code=PAR_UNEXPECTED_TOKEN,
                        )

                params.append(param_node)

                if not self.stream.match(TokenType.COMMA):
                    break
        return params

    def llm_body(self) -> tuple[Optional[List[Union[str, ast.IbExpr]]], Optional[List[Union[str, ast.IbExpr]]], Optional[List[Union[str, ast.IbExpr]]]]:
        self.stream.consume(TokenType.NEWLINE, "Expect newline before LLM block.")
        
        sys_prompt = None
        user_prompt = None
        retry_hint = None
        
        while not self.stream.check(TokenType.LLM_END) and not self.stream.is_at_end():
            if self.stream.match(TokenType.LLM_SYS):
                sys_prompt = self.parse_llm_section_content()
            elif self.stream.match(TokenType.LLM_USER):
                user_prompt = self.parse_llm_section_content()
            elif self.stream.match(TokenType.LLM_RETRY_HINT):
                retry_hint = self.parse_llm_section_content()
            elif self.stream.match(TokenType.NEWLINE):
                continue
            else:
                raise self.stream.error(self.stream.peek(), "Unexpected token in LLM block. Expect '__sys__', '__user__', '__llmretry__', or 'llmend'.", code=PAR_UNEXPECTED_TOKEN)

        self.stream.consume(TokenType.LLM_END, "Expect 'llmend' to close LLM block.")
        return sys_prompt, user_prompt, retry_hint

    def parse_llm_section_content(self) -> List[Union[str, ast.IbExpr]]:
        segments = []
        while not self.stream.is_at_end():
            if self.stream.check(TokenType.LLM_SYS) or self.stream.check(TokenType.LLM_USER) or self.stream.check(TokenType.LLM_RETRY_HINT) or self.stream.check(TokenType.LLM_END):
                break

            if self.stream.match(TokenType.RAW_TEXT):
                segments.append(self.stream.previous().value)
            elif self.stream.match(TokenType.NEWLINE):
                segments.append("\n")
            elif self.stream.match(TokenType.VAR_REF):
                # 支持 $变量名 格式
                # 注意：只有当变量名是 llm 函数参数时才会被替换，否则作为普通文本
                token = self.stream.previous()
                var_name = token.value
                var_ref = self._loc(ast.IbName(id=var_name, ctx='Load'), token)
                segments.append(var_ref)
            else:
                raise self.stream.error(self.stream.peek(), "Unexpected token in LLM section content.", code=PAR_UNEXPECTED_TOKEN)

        return segments
