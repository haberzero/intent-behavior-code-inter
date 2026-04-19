from typing import Dict, Optional, List, Union
from core.compiler.common.tokens import TokenType
from core.compiler.parser.core.token_stream import ParseControlFlowError
from core.kernel import ast as ast
from core.compiler.parser.core.syntax import IbPrecedence, IbParseRule
from core.compiler.parser.core.component import BaseComponent
from core.compiler.parser.core.syntax import ID_SELF, OP_MAP

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
        
        # Grouping and Collections
        self.register(TokenType.LPAREN, self.grouping, self.call, IbPrecedence.CALL)
        self.register(TokenType.LBRACKET, self.list_display, self.subscript, IbPrecedence.CALL)
        self.register(TokenType.LBRACE, self.dict_display, None, IbPrecedence.LOWEST)
        self.register(TokenType.COMMA, None, self.tuple_expr, IbPrecedence.TUPLE)
        
        # Unary Operations
        self.register(TokenType.MINUS, self.unary, self.binary, IbPrecedence.TERM)
        self.register(TokenType.PLUS, None, self.binary, IbPrecedence.TERM)
        self.register(TokenType.NOT, self.unary, None, IbPrecedence.UNARY)
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
        
        # Logical Operations
        self.register(TokenType.AND, None, self.logical, IbPrecedence.AND)
        self.register(TokenType.OR, None, self.logical, IbPrecedence.OR)
        
        # Calls and Attributes
        self.register(TokenType.DOT, None, self.dot, IbPrecedence.CALL)
        
        # Behavior
        self.register(TokenType.BEHAVIOR_MARKER, self.behavior_expression, None, IbPrecedence.LOWEST)
        
        # Variable Reference
        self.register(TokenType.VAR_REF, self.var_ref_expr, None, IbPrecedence.LOWEST)

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
            num = int(value)
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
                        # 正确写法：int lambda varname = @~...~ 或 int snapshot varname = @~...~
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
                    "Use 'int lambda varname = @~...~' or 'int snapshot varname = @~...~' instead.",
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
                    value=-int(num_token.value)
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
                # 行为描述块内的带引号字符串字面量 (如 MOCK:["a","b","c"])
                # 保留原始引号包裹，确保内容按原样传递给 LLM
                segments.append('"' + self.stream.previous().value + '"')
            else:
                # 其他 token 以其文本值追加，保持行为描述完整性
                segments.append(self.stream.previous().value if self.stream.advance() else "")
        
        self.stream.consume(TokenType.BEHAVIOR_MARKER, "Expect closing '~'.")
        
        return self._loc(ast.IbBehaviorExpr(segments=segments, tag=tag), start_token)

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
