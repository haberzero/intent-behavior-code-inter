from typing import Dict, Optional, List, Union
from core.compiler.common.tokens import TokenType
from core.compiler.parser.core.token_stream import ParseControlFlowError
from core.kernel import ast as ast
from core.compiler.parser.core.syntax import IbPrecedence, IbParseRule
from core.compiler.parser.core.component import BaseComponent
from core.compiler.parser.core.syntax import ID_SELF, OP_MAP

# 表达式位置 ``lambda(...) (...)`` 与 ``lambda(...)`` 形式消歧的前瞻上限。
# 取 1024 是源代码中单个 lambda 参数列表 + 函数体表达式 token 数的保守上界
# （典型 lambda 表达式不超过几十 token）；超出该上限的写法在实际代码中极
# 罕见，回退为 "无参形式" 不会引入二义性——后续 parse_expression 仍会按表
# 达式语法继续消费，错误会以 PAR_002 形式正常报告。
_MAX_LAMBDA_LOOKAHEAD_TOKENS = 1024

class ExpressionComponent(BaseComponent):
    def __init__(self, context):
        super().__init__(context)
        self.rules: Dict[TokenType, IbParseRule] = {}
        self.register_rules()

    def register(self, type: TokenType, prefix, infix, precedence):
        self.rules[type] = IbParseRule(prefix, infix, precedence)

    def get_rule(self, type: TokenType) -> IbParseRule:
        return self.rules.get(type, IbParseRule(None, None, IbPrecedence.LOWEST))

    def parse_expression(self, precedence: IbPrecedence = IbPrecedence.LOWEST) -> ast.IbExpr:
        return self.parse_precedence(precedence)

    def parse_precedence(self, precedence: IbPrecedence) -> ast.IbExpr:
        token = self.stream.advance()
        rule = self.get_rule(token.type)
        prefix = rule.prefix
        if prefix is None:
            raise self.stream.error(token, f"Expect expression. Got {token.type}", code="PAR_002")
        
        left = prefix()
        
        while precedence < self.get_rule(self.stream.peek().type).precedence:
            token = self.stream.advance()
            infix = self.get_rule(token.type).infix
            if infix is None:
                return left
            left = infix(left)
            
        return left

    def register_rules(self):
        # Literals and Identifiers
        self.register(TokenType.IDENTIFIER, self.variable, None, IbPrecedence.LOWEST)
        self.register(TokenType.SELF, self.self_expr, None, IbPrecedence.LOWEST)
        self.register(TokenType.NUMBER, self.number, None, IbPrecedence.LOWEST)
        self.register(TokenType.STRING, self.string, None, IbPrecedence.LOWEST)
        self.register(TokenType.TRUE, self.boolean, None, IbPrecedence.LOWEST)
        self.register(TokenType.FALSE, self.boolean, None, IbPrecedence.LOWEST)
        self.register(TokenType.NONE, self.none_expr, None, IbPrecedence.LOWEST)
        self.register(TokenType.UNCERTAIN, self.uncertain_expr, None, IbPrecedence.LOWEST)
        
        # Grouping and Collections
        self.register(TokenType.LPAREN, self.grouping, self.call, IbPrecedence.CALL)
        self.register(TokenType.LBRACKET, self.list_display, self.subscript, IbPrecedence.CALL)
        self.register(TokenType.LBRACE, self.dict_display, None, IbPrecedence.LOWEST)
        self.register(TokenType.COMMA, None, self.tuple_expr, IbPrecedence.TUPLE)
        
        # Unary Operations
        self.register(TokenType.MINUS, self.unary, self.binary, IbPrecedence.TERM)
        self.register(TokenType.PLUS, None, self.binary, IbPrecedence.TERM)
        self.register(TokenType.NOT, self.unary, self.not_in_binary, IbPrecedence.COMPARISON)
        self.register(TokenType.BIT_NOT, self.unary, None, IbPrecedence.UNARY)
        
        # Binary Operations
        self.register(TokenType.STAR, None, self.binary, IbPrecedence.FACTOR)
        self.register(TokenType.STAR_STAR, None, self.pow_binary, IbPrecedence.POW)
        self.register(TokenType.SLASH, None, self.binary, IbPrecedence.FACTOR)
        self.register(TokenType.FLOOR_DIV, None, self.binary, IbPrecedence.FACTOR)
        self.register(TokenType.PERCENT, None, self.binary, IbPrecedence.FACTOR)
        
        # Bitwise Operations
        self.register(TokenType.BIT_AND, None, self.binary, IbPrecedence.BIT_AND)
        self.register(TokenType.BIT_OR, None, self.binary, IbPrecedence.BIT_OR)
        self.register(TokenType.BIT_XOR, None, self.binary, IbPrecedence.BIT_XOR)
        self.register(TokenType.LSHIFT, None, self.binary, IbPrecedence.SHIFT)
        self.register(TokenType.RSHIFT, None, self.binary, IbPrecedence.SHIFT)
        
        # Comparisons
        self.register(TokenType.GT, None, self.binary, IbPrecedence.COMPARISON)
        self.register(TokenType.GE, None, self.binary, IbPrecedence.COMPARISON)
        self.register(TokenType.LT, None, self.binary, IbPrecedence.COMPARISON)
        self.register(TokenType.LE, None, self.binary, IbPrecedence.COMPARISON)
        self.register(TokenType.EQ, None, self.binary, IbPrecedence.EQUALITY)
        self.register(TokenType.NE, None, self.binary, IbPrecedence.EQUALITY)

        # Containment operators: in / not in (comparison-level precedence)
        self.register(TokenType.IN, None, self.in_binary, IbPrecedence.COMPARISON)

        # Identity operators: is / is not (comparison-level precedence)
        self.register(TokenType.IS, None, self.is_binary, IbPrecedence.COMPARISON)
        
        # Logical Operations
        self.register(TokenType.AND, None, self.logical, IbPrecedence.AND)
        self.register(TokenType.OR, None, self.logical, IbPrecedence.OR)
        
        # Ternary operators:
        #   - C-style:      condition ? body : orelse
        #   - Python-style: body if condition else orelse
        # Both register at ASSIGNMENT precedence (just above LOWEST). When `if`
        # appears as a Pratt infix in an expression context, it parses as the
        # Python-style ternary; statement-level `if`/`for ... if filter:` is
        # unaffected because those callers parse expressions at ASSIGNMENT
        # precedence (so IF infix is not picked up).
        self.register(TokenType.QUESTION, None, self.ternary, IbPrecedence.ASSIGNMENT)
        self.register(TokenType.IF, None, self.if_else_ternary, IbPrecedence.ASSIGNMENT)
        
        # Calls and Attributes
        self.register(TokenType.DOT, None, self.dot, IbPrecedence.CALL)
        
        # Behavior
        self.register(TokenType.BEHAVIOR_MARKER, self.behavior_expression, None, IbPrecedence.LOWEST)

        # Variable Reference
        self.register(TokenType.VAR_REF, self.var_ref_expr, None, IbPrecedence.LOWEST)

        # Parameterized lambda / snapshot expressions (M1)
        # 仅在表达式位置生效；旧的 `TYPE lambda NAME = EXPR` 形式由 declaration parser
        # 在变量声明位置消费 LAMBDA/SNAPSHOT token，不会触达此 prefix handler。
        self.register(TokenType.LAMBDA, self.lambda_expr, None, IbPrecedence.LOWEST)
        self.register(TokenType.SNAPSHOT, self.lambda_expr, None, IbPrecedence.LOWEST)

    # --- Pratt Parser Handlers ---

    def variable(self) -> ast.IbExpr:
        return self._loc(ast.IbName(id=self.stream.previous().value, ctx='Load'), self.stream.previous())

    def var_ref_expr(self) -> ast.IbExpr:
        token = self.stream.previous()
        # $name -> IbName(id=name)
        # $(expr) -> expr (Not implemented yet, but we could)
        name = token.value[1:]
        if not name:
            raise self.stream.error(token, "Variable reference cannot be empty.", code="PAR_002")
        return self._loc(ast.IbName(id=name, ctx='Load'), token)

    def self_expr(self) -> ast.IbExpr:
        token = self.stream.previous()
        # 使用语法常量，消除硬编码字符串
        return self._loc(ast.IbName(id=ID_SELF, ctx='Load'), token)

    def number(self) -> ast.IbExpr:
        value = self.stream.previous().value
        if '.' in value or 'e' in value or 'E' in value:
            num = float(value)
        else:
            num = int(value, 0)
        return self._loc(ast.IbConstant(value=num), self.stream.previous())

    def string(self) -> ast.IbExpr:
        return self._loc(ast.IbConstant(value=self.stream.previous().value), self.stream.previous())

    def boolean(self) -> ast.IbExpr:
        token = self.stream.previous()
        # 基于 Token 类型判定，消除字符串硬编码
        val = (token.type == TokenType.TRUE)
        return self._loc(ast.IbConstant(value=val), token)

    def none_expr(self) -> ast.IbExpr:
        token = self.stream.previous()
        # 使用标准 NONE Token，消除 Python None 直接引用
        return self._loc(ast.IbConstant(value=None), token)

    def uncertain_expr(self) -> ast.IbExpr:
        token = self.stream.previous()
        # 使用内部哨兵字符串标记 Uncertain 字面量，序列化后可安全往返
        return self._loc(ast.IbConstant(value="__IBCI_UNCERTAIN_LITERAL__"), token)

    def grouping(self) -> ast.IbExpr:

        # 语法歧义解析：(Type) expr [Cast] vs (expr) [Grouping]
        # 由于 Type 可以是复杂的标识符、属性或下标访问，LL(1) 无法区分。
        # 我们采用推测性前瞻（Speculative Lookahead）模式进行判定。
        
        if self.stream.peek().type in (TokenType.IDENTIFIER, TokenType.AUTO):
            checkpoint = self.stream.get_checkpoint()
            _behavior_cast_detected = False

            # 开启静默前瞻模式，防止类型解析失败产生误导性的语法错误报告。
            with self.stream.speculate():
                try:
                    # 尝试以前瞻方式解析类型标注
                    type_node = self.context.type_parser.parse_type_annotation()
                    if self.stream.match(TokenType.RPAREN):
                        # 确认为类型转换 (Cast) 语法路径
                        value = self.parse_precedence(IbPrecedence.UNARY)
                        
                        # [DEPRECATED] (Type) @~...~ 语法已废弃，发出硬错误。
                        # 正确写法：TYPE fn varname = lambda: @~...~ 或 TYPE fn varname = snapshot: @~...~
                        if isinstance(value, ast.IbBehaviorExpr):
                            _behavior_cast_detected = True
                            raise ParseControlFlowError()
                        
                        return self._loc(ast.IbCastExpr(type_annotation=type_node, value=value), type_node)
                except ParseControlFlowError:
                    pass
            
            # 在 speculate 上下文外发出硬错误，确保记录到真实的 issue_tracker
            if _behavior_cast_detected:
                raise self.stream.error(
                    self.stream.peek(),
                    "Cast expression '(Type) @~...~' is no longer supported. "
                    "Use 'TYPE fn varname = lambda: @~...~' or 'TYPE fn varname = snapshot: @~...~' instead.",
                    code="PAR_010"
                )
            
            # 路径回退：若非 Cast，则回退到检查点按普通分组表达式解析
            self.stream.restore_checkpoint(checkpoint)

        expr = self.parse_expression()
        self.stream.consume(TokenType.RPAREN, "Expect ')' after expression.")
        return expr
    
    def _extract_type_name(self, type_node: ast.IbASTNode) -> str:
        """从类型节点中提取类型名称"""
        if isinstance(type_node, ast.IbName):
            return type_node.id
        if isinstance(type_node, ast.IbAttribute):
            # 处理 Type.attr 形式
            value_name = self._extract_type_name(type_node.value)
            return f"{value_name}.{type_node.attr}" if value_name else type_node.attr
        return ""
    
    def list_display(self) -> ast.IbExpr:
        start_token = self.stream.previous()
        elts = []
        if not self.stream.check(TokenType.RBRACKET):
            while True:
                elts.append(self.parse_expression(IbPrecedence.TUPLE))
                if not self.stream.match(TokenType.COMMA):
                    break
        end_token = self.stream.consume(TokenType.RBRACKET, "Expect ']' after list elements.")
        return self._loc(ast.IbListExpr(elts=elts, ctx='Load'), start_token, end_token)

    def dict_display(self) -> ast.IbExpr:
        start_token = self.stream.previous()
        keys = []
        values = []
        if not self.stream.check(TokenType.RBRACE):
            while True:
                keys.append(self.parse_expression(IbPrecedence.TUPLE))
                self.stream.consume(TokenType.COLON, "Expect ':' after dict key.")
                values.append(self.parse_expression(IbPrecedence.TUPLE))
                if not self.stream.match(TokenType.COMMA):
                    break
        end_token = self.stream.consume(TokenType.RBRACE, "Expect '}' after dict entries.")
        return self._loc(ast.IbDict(keys=keys, values=values), start_token, end_token)

    def unary(self) -> ast.IbExpr:
        op_token = self.stream.previous()
        # 基于 TokenType 枚举从 OP_MAP 获取运算符，彻底消除字符串比对
        op = OP_MAP.get(op_token.type, op_token.type.name)
        operand = self.parse_precedence(IbPrecedence.UNARY)
        return self._loc(ast.IbUnaryOp(op=op, operand=operand), op_token)

    def pow_binary(self, left: ast.IbExpr) -> ast.IbExpr:
        """右结合幂运算符 **：parse 右侧时使用比当前优先级低一级的 FACTOR，
        使得 a ** b ** c 解析为 a ** (b ** c)。"""
        op_token = self.stream.previous()
        right = self.parse_precedence(IbPrecedence.FACTOR)
        return self._loc(ast.IbBinOp(left=left, op="**", right=right), left, right)

    def binary(self, left: ast.IbExpr) -> ast.IbExpr:
        op_token = self.stream.previous()
        # 基于 TokenType 枚举从 OP_MAP 获取运算符，彻底消除字符串比对
        op_str = OP_MAP.get(op_token.type, op_token.type.name)
        
        rule = self.get_rule(op_token.type)
        right = self.parse_precedence(rule.precedence)
        
        # 处理链式比较 (Chained Comparison)
        if op_token.type in (TokenType.GT, TokenType.GE, TokenType.LT, TokenType.LE, TokenType.EQ, TokenType.NE):
            if isinstance(left, ast.IbCompare):
                left.ops.append(op_str)
                left.comparators.append(right)
                return self._extend_loc(left, right)
            return self._loc(ast.IbCompare(left=left, ops=[op_str], comparators=[right]), left, right)
            
        return self._loc(ast.IbBinOp(left=left, op=op_str, right=right), left, right)

    def logical(self, left: ast.IbExpr) -> ast.IbExpr:
        op_token = self.stream.previous()
        # 使用 OP_MAP 映射逻辑运算符，消除硬编码字符串
        op = OP_MAP.get(op_token.type, op_token.type.name)
        rule = self.get_rule(op_token.type)
        right = self.parse_precedence(rule.precedence)
        
        if isinstance(left, ast.IbBoolOp) and left.op == op:
            left.values.append(right)
            return self._extend_loc(left, right)
            
        return self._loc(ast.IbBoolOp(op=op, values=[left, right]), left, right)

    def ternary(self, left: ast.IbExpr) -> ast.IbExpr:
        """C 风格三元运算符：condition ? body : orelse"""
        question_token = self.stream.previous()
        # 解析真值分支（在 COLON 之前停止，因为 COLON 无 infix 规则，优先级为 LOWEST）
        body = self.parse_expression(IbPrecedence.LOWEST)
        self.stream.consume(TokenType.COLON, "Expect ':' in ternary expression 'cond ? expr : expr'.")
        # 解析假值分支（右结合：再次从 LOWEST 开始，可嵌套三元）
        orelse = self.parse_expression(IbPrecedence.LOWEST)
        return self._loc(ast.IbIfExp(test=left, body=body, orelse=orelse), left, orelse)

    def if_else_ternary(self, left: ast.IbExpr) -> ast.IbExpr:
        """Python 风格三元运算符：body if condition else orelse

        左值 `left` 已被预先解析为 body。本方法消费 `if cond else orelse` 部分。
        与 C 风格 `?:` 等价；解析为同一 IbIfExp AST 节点。

        注意：调用者（for-loop 的 iter 表达式）需以 ASSIGNMENT 优先级调用
        parse_expression 以避免误吞作为过滤器关键字的 `if`。
        """
        if_token = self.stream.previous()
        # 解析条件，停在 ELSE 之前。由于 ELSE 没有 infix 规则，
        # 用 LOWEST 即可（与 `?:` 中 body 的处理一致）。
        cond = self.parse_expression(IbPrecedence.LOWEST)
        self.stream.consume(
            TokenType.ELSE,
            "Expect 'else' in ternary expression 'body if cond else orelse'.",
        )
        # 假值分支：右结合，允许嵌套（再次从 LOWEST 开始）。
        orelse = self.parse_expression(IbPrecedence.LOWEST)
        return self._loc(ast.IbIfExp(test=cond, body=left, orelse=orelse), left, orelse)

    def in_binary(self, left: ast.IbExpr) -> ast.IbExpr:
        """成员检测运算符：elem in container"""
        right = self.parse_precedence(IbPrecedence.COMPARISON)
        return self._loc(ast.IbCompare(left=left, ops=["in"], comparators=[right]), left, right)

    def not_in_binary(self, left: ast.IbExpr) -> ast.IbExpr:
        """成员非检测运算符：elem not in container（NOT 作为 infix 时消费 IN）"""
        in_token = self.stream.consume(TokenType.IN, "Expect 'in' after 'not' in 'not in' expression.")
        right = self.parse_precedence(IbPrecedence.COMPARISON)
        return self._loc(ast.IbCompare(left=left, ops=["not in"], comparators=[right]), left, right)

    def is_binary(self, left: ast.IbExpr) -> ast.IbExpr:
        """身份检测运算符：x is y / x is not y"""
        # 检查是否是 'is not' 复合运算符
        if self.stream.match(TokenType.NOT):
            right = self.parse_precedence(IbPrecedence.COMPARISON)
            return self._loc(ast.IbCompare(left=left, ops=["is not"], comparators=[right]), left, right)
        right = self.parse_precedence(IbPrecedence.COMPARISON)
        return self._loc(ast.IbCompare(left=left, ops=["is"], comparators=[right]), left, right)

    def call(self, left: ast.IbExpr) -> ast.IbCall:
        arguments = []
        if not self.stream.check(TokenType.RPAREN):
            while True:
                if self.stream.is_at_end():
                    raise self.stream.error(self.stream.peek(), "Unterminated argument list.", code="PAR_004")
                arguments.append(self.parse_expression(IbPrecedence.TUPLE))
                if not self.stream.match(TokenType.COMMA):
                    break
        end_token = self.stream.consume(TokenType.RPAREN, "Expect ')' after arguments.")
        
        # 意图节点化：不再向 Call 注入 intent 属性
        return self._loc(ast.IbCall(func=left, args=arguments, keywords=[]), left, end_token)

    def dot(self, left: ast.IbExpr) -> ast.IbExpr:
        name = self.stream.consume(TokenType.IDENTIFIER, "Expect property name after '.'.")
        return self._loc(ast.IbAttribute(value=left, attr=name.value, ctx='Load'), left, name)

    def tuple_expr(self, left: ast.IbExpr) -> ast.IbExpr:
        elts = [left]
        # 修正元组解析：第一个逗号已被 parse_precedence 消费
        # 我们必须至少解析一个后续元素
        if not self.stream.check(TokenType.RPAREN) and not self.stream.check(TokenType.RBRACKET) and not self.stream.check(TokenType.RBRACE):
            elts.append(self.parse_precedence(IbPrecedence.TUPLE))
            
        while self.stream.match(TokenType.COMMA):
            if self.stream.check(TokenType.RPAREN) or self.stream.check(TokenType.RBRACKET) or self.stream.check(TokenType.RBRACE):
                break
            elts.append(self.parse_precedence(IbPrecedence.TUPLE))
        return self._loc(ast.IbTuple(elts=elts, ctx='Load'), left, elts[-1])

    def subscript(self, left: ast.IbExpr) -> ast.IbSubscript:
        """解析下标或切片：obj[index] 或 obj[start:end:step]"""
        slice_node = self._parse_slice_or_index()
        end_token = self.stream.consume(TokenType.RBRACKET, "Expect ']' after subscript.")
        return self._loc(ast.IbSubscript(value=left, slice=slice_node, ctx='Load'), left, end_token)

    def _parse_slice_or_index(self) -> ast.IbExpr:
        """解析切片或单点索引"""
        if self.stream.match(TokenType.COLON):
            return self._parse_slice_rest(lower=None, colon_token=self.stream.previous())

        if self.stream.check(TokenType.MINUS):
            expr = self._parse_slice_expression()
        else:
            expr = self.parse_expression()

        if self.stream.match(TokenType.COLON):
            return self._parse_slice_rest(lower=expr, colon_token=self.stream.previous())

        return expr

    def _parse_slice_rest(self, lower: Optional[ast.IbExpr], colon_token) -> ast.IbSlice:
        """辅助解析切片的后续部分"""
        upper = None
        if not self.stream.check(TokenType.COLON, TokenType.RBRACKET):
            upper = self._parse_slice_expression()

        step = None
        if self.stream.match(TokenType.COLON):
            if not self.stream.check(TokenType.RBRACKET):
                step = self._parse_slice_expression()

        return self._loc(ast.IbSlice(lower=lower, upper=upper, step=step), colon_token)

    def _parse_slice_expression(self) -> ast.IbExpr:
        """解析切片表达式中的数字，支持负数"""
        start_token = self.stream.peek()
        if self.stream.match(TokenType.MINUS):
            if self.stream.check(TokenType.NUMBER):
                num_token = self.stream.advance()
                negative_num = ast.IbConstant(
                    value=-int(num_token.value, 0)
                )
                return self._loc(negative_num, start_token)
            else:
                self.stream.rewind()
        return self.parse_expression()

    def behavior_expression(self) -> ast.IbBehaviorExpr:
        start_token = self.stream.previous()
        # Extract tag from @tag~
        tag = ""
        if start_token.value.startswith("@") and start_token.value.endswith("~"):
            tag = start_token.value[1:-1]
            
        segments = []
        
        while not self.stream.check(TokenType.BEHAVIOR_MARKER):
            if self.stream.is_at_end():
                raise self.stream.error(self.stream.peek(), "Unterminated behavior expression.", code="PAR_004")
                
            if self.stream.match(TokenType.RAW_TEXT):
                segments.append(self.stream.previous().value)
            elif self.stream.match(TokenType.VAR_REF):
                var_token = self.stream.previous()
                var_name = var_token.value[1:] # Strip $
                node = self._parse_complex_access(var_name, var_token)
                segments.append(node)
            elif self.stream.match(TokenType.STRING):
                # 行为描述块内的带引号字符串字面量 (如 MOCK:LIST:["a","b","c"])
                # 保留原始引号包裹，确保内容按原样传递给 LLM
                segments.append('"' + self.stream.previous().value + '"')
            else:
                # 其他 token 以其文本值追加，保持行为描述完整性
                segments.append(self.stream.previous().value if self.stream.advance() else "")
        
        self.stream.consume(TokenType.BEHAVIOR_MARKER, "Expect closing '~'.")
        
        return self._loc(ast.IbBehaviorExpr(segments=segments, tag=tag), start_token)

    def lambda_expr(self) -> ast.IbExpr:
        """
        参数化 lambda/snapshot 表达式。

        全部支持的形式（``:`` 为唯一 body 起始符）::

            lambda: EXPR                         — 无参
            lambda(PARAMS): EXPR                 — 有参
            snapshot: EXPR                       — snapshot 完全对称
            snapshot(PARAMS): EXPR

        返回类型标注**必须**写在声明侧，不允许写在表达式侧::

            int fn f = lambda: EXPR              — 声明 f 返回 int
            int fn f = lambda(PARAMS): EXPR      — 声明 f 带参且返回 int
            tuple[int, str] fn p = make_parser() — 从工厂获取时也可标注

        body 是单一表达式，解析优先级为 LOWEST，在当前 token 行结束
        （NEWLINE/EOF）时自然终止（由 parse_expression 处理）。
        """
        keyword_token = self.stream.previous()
        deferred_mode = "lambda" if keyword_token.type == TokenType.LAMBDA else "snapshot"

        params: List[ast.IbASTNode] = []
        returns_node: Optional[ast.IbExpr] = None
        type_parser = self.context.type_parser

        # ------------------------------------------------------------------ #
        # 1. 无参：`lambda: EXPR` / `lambda -> TYPE: EXPR`                   #
        # ------------------------------------------------------------------ #
        if self.stream.check(TokenType.ARROW):
            # D2：表达式侧 `-> TYPE` 合法化
            self.stream.advance()  # consume '->'
            returns_node = type_parser.parse_type_annotation()
            self.stream.consume(
                TokenType.COLON,
                f"Expect ':' after return type annotation in '{deferred_mode}' expression.",
            )
            body = self.parse_expression(IbPrecedence.LOWEST)

        elif self.stream.check(TokenType.COLON):
            self.stream.advance()  # consume ':'
            body = self.parse_expression(IbPrecedence.LOWEST)

        # ------------------------------------------------------------------ #
        # 2. 括号开头：有参形式 `lambda(PARAMS): EXPR`                        #
        # ------------------------------------------------------------------ #
        elif self.stream.check(TokenType.LPAREN):
            if not self._lambda_lookahead_is_param_form():
                raise self.stream.error(
                    self.stream.peek(),
                    f"Expect ':' after '{deferred_mode}' parameter list, or ':' directly after '{deferred_mode}' keyword. "
                    f"Parenthesis-only body forms are not supported; use '{deferred_mode}: EXPR' or '{deferred_mode}(PARAMS): EXPR'.",
                    code="PAR_002",
                )

            # 解析参数列表
            self.stream.consume(TokenType.LPAREN, f"Expect '(' after '{deferred_mode}' keyword.")
            decl = self.context.declaration_parser
            if decl is None:
                raise self.stream.error(
                    keyword_token,
                    "Internal: declaration parser not wired; cannot parse lambda parameters.",
                    code="PAR_002",
                )
            params = decl.parameters()
            self.stream.consume(TokenType.RPAREN, f"Expect ')' after '{deferred_mode}' parameter list.")

            # D2：表达式侧 `-> TYPE` 合法化（有参形式）
            if self.stream.check(TokenType.ARROW):
                self.stream.advance()  # consume '->'
                returns_node = type_parser.parse_type_annotation()

            # Body 必须以 ':' 起始
            self.stream.consume(TokenType.COLON, f"Expect ':' to introduce '{deferred_mode}' body expression.")
            body = self.parse_expression(IbPrecedence.LOWEST)

        else:
            raise self.stream.error(
                self.stream.peek(),
                f"Expect ':' or '(' after '{deferred_mode}' keyword in expression position.",
                code="PAR_002",
            )

        node = ast.IbLambdaExpr(params=params, body=body, deferred_mode=deferred_mode, returns=returns_node)
        return self._loc(node, keyword_token, self.stream.previous())

    def _lambda_lookahead_is_param_form(self) -> bool:
        """
        前瞻判断 ``lambda(...): ...`` 形式。

        此时 stream 已消费 ``lambda``/``snapshot`` 关键字，且当前 peek(0) 为 LPAREN。
        在 token 流上做平衡括号扫描；若第一个 RPAREN 之后紧接的 token 为
        COLON（``:``）或 ARROW（``->`` — 仅用于前瞻识别；ARROW 会在后续步骤被拒绝并报错），
        则视为有参形式（参数列表形式）。
        扫描严格只读，不修改 stream 位置。
        """
        depth = 0
        offset = 0
        while offset < _MAX_LAMBDA_LOOKAHEAD_TOKENS:
            t = self.stream.peek(offset)
            if t.type == TokenType.EOF or t.type == TokenType.NEWLINE:
                return False
            if t.type == TokenType.LPAREN:
                depth += 1
            elif t.type == TokenType.RPAREN:
                depth -= 1
                if depth == 0:
                    next_t = self.stream.peek(offset + 1)
                    return next_t.type in (TokenType.ARROW, TokenType.COLON)
            offset += 1
        return False

    def _parse_complex_access(self, var_name: str, var_token) -> ast.IbExpr:
        """Helper to parse complex access like $obj.attr[0] after a $var_ref."""
        # Create initial Name node
        node = self._loc(ast.IbName(id=var_name, ctx='Load'), var_token)
        
        # Support complex access: $obj.attr, $obj[index]
        while True:
            if self.stream.match(TokenType.DOT):
                dot_token = self.stream.previous()
                attr_name = self.stream.consume(TokenType.IDENTIFIER, "Expect property name after '.'.")
                node = self._loc(ast.IbAttribute(value=node, attr=attr_name.value, ctx='Load'), dot_token)
            elif self.stream.match(TokenType.LBRACKET):
                lbracket_token = self.stream.previous()
                # 使用统一的切片/索引解析器
                slice_node = self._parse_slice_or_index()
                self.stream.consume(TokenType.RBRACKET, "Expect ']' after subscript.")
                node = self._loc(ast.IbSubscript(value=node, slice=slice_node, ctx='Load'), lbracket_token)
            else:
                break
        return node
