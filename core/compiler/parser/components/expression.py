from typing import Dict, Optional, List, Union
from core.base.diagnostics.codes import PAR_DEPRECATED_CAST_SYNTAX, PAR_POSITIONAL_AFTER_KEYWORD, PAR_UNEXPECTED_EOF, PAR_UNEXPECTED_TOKEN
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
# 达式语法继续消费，错误会以 PAR_UNEXPECTED_TOKEN 形式正常报告。
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
            raise self.stream.error(token, f"Expect expression. Got {token.type}", code=PAR_UNEXPECTED_TOKEN)
        
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

        # Await (显式等待一个 Waitable)
        self.register(TokenType.AWAIT, self.await_expr, None, IbPrecedence.UNARY)

        # Yield (惰性生成器产出值)
        self.register(TokenType.YIELD, self.yield_expr, None, IbPrecedence.LOWEST)

        # 并发/通信：chan/slot 构造函数前缀
        self.register(TokenType.CHAN, self.chan_expr, None, IbPrecedence.UNARY)
        self.register(TokenType.SLOT, self.slot_expr, None, IbPrecedence.UNARY)
        
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

        # Parameterized lambda / snapshot expressions
        # 在表达式位置消费 LAMBDA/SNAPSHOT token，构建 IbLambdaExpr。
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
            raise self.stream.error(token, "Variable reference cannot be empty.", code=PAR_UNEXPECTED_TOKEN)
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
            cast_node: Optional[ast.IbExpr] = None

            # 开启静默前瞻模式，防止类型解析失败产生误导性的语法错误报告。
            # try/except 必须包在 with 外侧，否则 ParseControlFlowError
            # 在 with 内被捕获会导致 temp_tracker 合并到 issue_tracker。
            try:
                with self.stream.speculate():
                    # 尝试以前瞻方式解析类型标注
                    type_node = self.context.type_parser.parse_type_annotation()
                    if self.stream.match(TokenType.RPAREN):
                        # 链式下标消歧：
                        # 当 type_node 自身含下标（IbSubscript）且 RPAREN 之后紧跟 `[` 时，
                        # 几乎必然是链式下标而非 cast。触发回退。
                        if isinstance(type_node, ast.IbSubscript) and self.stream.check(TokenType.LBRACKET):
                            raise ParseControlFlowError()

                        # 确认为类型转换 (Cast) 语法路径
                        value = self.parse_precedence(IbPrecedence.UNARY)

                        # (Type) @~...~ 语法不支持，发出错误。
                        # 正确写法：fn varname = lambda -> TYPE: @~...~
                        if isinstance(value, ast.IbBehaviorExpr):
                            _behavior_cast_detected = True
                            raise ParseControlFlowError()

                        # 缓存结果，with 正常退出后再 return；不在 with 内 return，
                        # 以保证 PCFE 失败路径与成功路径走同一套出口机制。
                        cast_node = self._loc(ast.IbCastExpr(type_annotation=type_node, value=value), type_node)
                    else:
                        # 类型标注解析成功但未匹配到 RPAREN，非 cast 语法
                        raise ParseControlFlowError()
            except ParseControlFlowError:
                cast_node = None

            if cast_node is not None:
                return cast_node

            # 在 speculate 上下文外发出硬错误，确保记录到真实的 issue_tracker
            if _behavior_cast_detected:
                raise self.stream.error(
                    self.stream.peek(),
                    "Cast expression '(Type) @~...~' is no longer supported. "
                    "Use 'fn varname = lambda -> TYPE: @~...~' or 'fn varname = snapshot -> TYPE: @~...~' instead.",
                    code=PAR_DEPRECATED_CAST_SYNTAX
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

    def await_expr(self) -> ast.IbExpr:
        """``await <expr>``：显式等待一个 Waitable 完成，返回其结果。

        操作数求值为 ``Waitable``（LLMFuture / HostAwaitable）；VM 对该
        Waitable ``yield`` 挂起，恢复后返回 ``result()``。作为 UNARY 优先级
        前缀：``await x + 1`` 解析为 ``(await x) + 1``（与 Pythona await 一致）。
        """
        op_token = self.stream.previous()
        operand = self.parse_precedence(IbPrecedence.UNARY)
        return self._loc(ast.IbAwaitExpr(value=operand), op_token)

    def yield_expr(self) -> ast.IbExpr:
        """``yield <expr>`` / ``yield from <expr>``：惰性生成器产出 / 委托。

        含 ``yield`` 的函数为惰性生成器：``yield x`` 挂起产出值 ``x``，迭代
        恢复。``yield from <expr>`` 把子迭代对象的每个产出逐值透传为当前
        生成器的产出（子生成器委托）。两者均以 LOWEST 优先级
        解析操作数——``yield x + 1`` 产出 ``x + 1``（与 Python 一致，yield 是
        低优先级语句级关键字）。无操作数（``yield``）产出 ``None``。
        """
        op_token = self.stream.previous()
        if self.stream.match(TokenType.FROM):
            operand = self.parse_precedence(IbPrecedence.LOWEST)
            return self._loc(ast.IbYieldFromExpr(value=operand), op_token)
        operand = self.parse_precedence(IbPrecedence.LOWEST)
        return self._loc(ast.IbYieldExpr(value=operand), op_token)

    def _expr_name(self, node: Optional[ast.IbExpr]) -> Optional[str]:
        """AST 表达式节点 → 名称字符串（供 chan/slot 的 type_name/mode/name 字段）。

        统一形状判别（IbName/.id、IbConstant/.value、IbAttribute 全限定名、
        IbSubscript 基名），替代链式 hasattr 探测 + ``str()`` 兜底——后者对
        dataclass 节点产生含 lineno/col 噪音的无意义名（点分类型还会被截断为
        接收者名）。
        """
        if node is None:
            return None
        if isinstance(node, ast.IbName):
            return node.id
        if isinstance(node, ast.IbConstant):
            return str(node.value) if node.value is not None else None
        if isinstance(node, ast.IbAttribute):
            base = self._expr_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        if isinstance(node, ast.IbSubscript):
            # 泛型实参由语义层 resolve_typeref 结构化处理；这里只承载基名
            return self._expr_name(node.value)
        return None

    def chan_expr(self) -> ast.IbExpr:
        """``chan(T, mode=..., buffer=...)`` 或 ``chan T(...)`` —— Channel 构造。

        首参 ``T`` 为元素类型名，经 ``type_parser.parse_type_annotation`` 解析为
        类型引用（``str``/``int`` 等注册类型名）；其余参数（mode/buffer/name）
        走通用表达式解析。
        """
        op_token = self.stream.previous()
        type_name = None
        mode = "message"
        buffer = 0
        name = None

        if self.stream.match(TokenType.LPAREN):
            # 函数形态：chan(T, ...) —— 首参是类型名
            if not self.stream.check(TokenType.RPAREN):
                type_ann = self.context.type_parser.parse_type_annotation()
                type_name = self._expr_name(type_ann)
                # 可选位置参数：第二参可作 mode（chan(str, "stream")）
                if self.stream.match(TokenType.COMMA):
                    if self.stream.check(TokenType.STRING) and not (
                        self.stream.peek(1).type == TokenType.ASSIGN
                    ):
                        mode_token = self.stream.advance()
                        mode = mode_token.value
                    # 关键字参数（mode=/buffer=/name=）——逗号已由上方 match 消费，
                    # 流停在首关键字处，_parse_chan_kwargs 兼容"已消费逗号"形态。
                    kw = self._parse_chan_kwargs()
                    if kw is not None:
                        m, b, n = kw
                        if m is not None:
                            mode = m
                        if b:
                            buffer = b
                        if n is not None:
                            name = n
                # 剩余关键字参数（mode=/buffer=/name=）
                if mode in ("message", "stream", "pubsub"):
                    kw = self._parse_chan_kwargs()
                    if kw is not None:
                        m, b, n = kw
                        if m is not None:
                            mode = m
                        if b:
                            buffer = b
                        if n is not None:
                            name = n
            self.stream.consume(TokenType.RPAREN, "Expect ')' after chan arguments.")
        else:
            # 声明式形态：chan T(...) —— 解析类型注解后接参数
            type_ann = self.context.type_parser.parse_type_annotation()
            type_name = self._expr_name(type_ann)
            if self.stream.match(TokenType.LPAREN):
                while self.stream.match(TokenType.COMMA):
                    if self.stream.check(TokenType.IDENTIFIER) and self.stream.peek(1).type == TokenType.ASSIGN:
                        kw_token = self.stream.advance()
                        self.stream.advance()
                        kw_val = self.parse_precedence(IbPrecedence.UNARY)
                        if kw_token.value == "mode":
                            mode = self._expr_name(kw_val)
                        elif kw_token.value == "buffer":
                            if isinstance(kw_val, ast.IbConstant) and isinstance(kw_val.value, int) and not isinstance(kw_val.value, bool):
                                buffer = kw_val.value
                            else:
                                raise self.stream.error(kw_token, "chan 'buffer=' expects an integer literal.", code=PAR_UNEXPECTED_TOKEN)
                        elif kw_token.value == "name":
                            name = self._expr_name(kw_val)
                self.stream.consume(TokenType.RPAREN, "Expect ')' after chan declaration.")

        return self._loc(ast.IbChannelExpr(type_name=type_name, mode=mode, buffer=buffer, name=name), op_token)

    def _parse_chan_kwargs(self):
        """解析 ``chan`` 的具名参数（mode=/buffer=/name=），返回 ``(mode, buffer, name)`` 或 None。

        兼容两种流位置：调用方已消费首个逗号（流停在首关键字处，如函数形态
        ``chan(T, mode=...)``），或流停在逗号前（后续关键字参数）——按
        "关键字直接位于当前位置 / 逗号后关键字"两种形态统一处理。
        """
        mode = None
        buffer = 0
        name = None
        matched_any = False
        while True:
            if self.stream.check(TokenType.IDENTIFIER) and self.stream.peek(1).type == TokenType.ASSIGN:
                pass  # 已停在关键字处（调用方已消费首个逗号）
            elif self.stream.match(TokenType.COMMA):
                # 停在逗号前：消费逗号后必须是关键字，否则结束
                if not (self.stream.check(TokenType.IDENTIFIER) and self.stream.peek(1).type == TokenType.ASSIGN):
                    break
            else:
                break
            kw_token = self.stream.advance()
            self.stream.advance()  # '='
            kw_val = self.parse_precedence(IbPrecedence.UNARY)
            if kw_token.value == "mode":
                mode = self._expr_name(kw_val)
            elif kw_token.value == "buffer":
                if isinstance(kw_val, ast.IbConstant) and isinstance(kw_val.value, int) and not isinstance(kw_val.value, bool):
                    buffer = kw_val.value
                else:
                    raise self.stream.error(kw_token, "chan 'buffer=' expects an integer literal.", code=PAR_UNEXPECTED_TOKEN)
            elif kw_token.value == "name":
                name = self._expr_name(kw_val)
            matched_any = True
        return (mode, buffer, name) if matched_any else None

    def slot_expr(self) -> ast.IbExpr:
        """``slot(name, value)`` 或 ``slot T(name)`` —— Slot 构造。"""
        op_token = self.stream.previous()
        type_name = None
        name = None
        value = None
        if self.stream.match(TokenType.LPAREN):
            # 函数形态：slot(name, value)
            if not self.stream.check(TokenType.RPAREN):
                first = self.parse_precedence(IbPrecedence.UNARY)
                name = self._expr_name(first)
                if self.stream.match(TokenType.COMMA):
                    value = self.parse_precedence(IbPrecedence.UNARY)
            self.stream.consume(TokenType.RPAREN, "Expect ')' after slot arguments.")
        else:
            # 声明式形态：slot T(name)
            type_ann = self.context.type_parser.parse_type_annotation()
            type_name = self._expr_name(type_ann)
            self.stream.consume(TokenType.LPAREN, "Expect '(' after slot type.")
            name = self.stream.consume(TokenType.IDENTIFIER, "Expect slot name.").value
            if self.stream.match(TokenType.COMMA):
                value = self.parse_precedence(IbPrecedence.UNARY)
            self.stream.consume(TokenType.RPAREN, "Expect ')' after slot name.")
        return self._loc(ast.IbSlotExpr(name=name or "", type_name=type_name, value=value), op_token)

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
        arguments: List[ast.IbExpr] = []
        keywords: List[ast.IbKeyword] = []
        seen_keyword = False
        if not self.stream.check(TokenType.RPAREN):
            while True:
                if self.stream.is_at_end():
                    raise self.stream.error(self.stream.peek(), "Unterminated argument list.", code=PAR_UNEXPECTED_EOF)

                if self.stream.match(TokenType.STAR_STAR):
                    # **expr 字典解包 -> IbKeyword(arg=None)
                    value = self.parse_expression(IbPrecedence.TUPLE)
                    keywords.append(self._loc(ast.IbKeyword(arg=None, value=value), self.stream.previous(), value))
                    seen_keyword = True
                elif self.stream.match(TokenType.STAR):
                    # *expr 序列解包 -> IbStarred（不得出现在具名实参之后）
                    if seen_keyword:
                        raise self.stream.error(
                            self.stream.previous(),
                            "Positional argument cannot follow keyword argument.",
                            code=PAR_POSITIONAL_AFTER_KEYWORD,
                        )
                    value = self.parse_expression(IbPrecedence.TUPLE)
                    arguments.append(self._loc(ast.IbStarred(value=value), self.stream.previous(), value))
                else:
                    arg = self.parse_expression(IbPrecedence.TUPLE)
                    if isinstance(arg, ast.IbName) and self.stream.match(TokenType.ASSIGN):
                        # 具名参数：name = value
                        value = self.parse_expression(IbPrecedence.TUPLE)
                        keywords.append(self._loc(ast.IbKeyword(arg=arg.id, value=value), arg, value))
                        seen_keyword = True
                    else:
                        if seen_keyword:
                            raise self.stream.error(
                                self.stream.previous(),
                                "Positional argument cannot follow keyword argument.",
                                code=PAR_POSITIONAL_AFTER_KEYWORD,
                            )
                        arguments.append(arg)

                if not self.stream.match(TokenType.COMMA):
                    break
        end_token = self.stream.consume(TokenType.RPAREN, "Expect ')' after arguments.")

        return self._loc(ast.IbCall(func=left, args=arguments, keywords=keywords), left, end_token)

    def dot(self, left: ast.IbExpr) -> ast.IbExpr:
        name = self._consume_member_name()
        return self._loc(ast.IbAttribute(value=left, attr=name, ctx='Load'), left)

    def _consume_member_name(self) -> str:
        """消费成员名：IDENTIFIER 或标识符样关键字（如 ``iruntime.snapshot``）。

        ``snapshot``/``fn``/``auto``/``chan`` 等关键字在点访问后可作为成员名
        （关键字保留字限制不适用于成员位置——Python 的 ``obj.<name>`` 语义）。
        运算符等非标识符 token 仍被拒绝。
        """
        tok = self.stream.peek()
        if tok.type == TokenType.IDENTIFIER:
            return self.stream.advance().value
        # 关键字：仅当其 source 文本是合法标识符时才接受（排除运算符等）
        val = tok.value or ""
        if val and val.isidentifier():
            self.stream.advance()
            return val
        return self.stream.consume(TokenType.IDENTIFIER, "Expect property name after '.'.").value

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
                raise self.stream.error(self.stream.peek(), "Unterminated behavior expression.", code=PAR_UNEXPECTED_EOF)
                
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

            lambda: EXPR                         — 无参，返回类型推导
            lambda -> TYPE: EXPR                 — 无参，显式返回类型
            lambda(PARAMS): EXPR                 — 有参，返回类型推导
            lambda(PARAMS) -> TYPE: EXPR         — 有参，显式返回类型
            snapshot: EXPR                       — snapshot 完全对称
            snapshot -> TYPE: EXPR
            snapshot(PARAMS): EXPR
            snapshot(PARAMS) -> TYPE: EXPR

        返回类型标注**写在表达式侧**（``-> TYPE``）::

            fn f = lambda -> int: EXPR           — 声明 f 返回 int
            fn f = lambda(int x) -> int: EXPR    — 声明 f 有参且返回 int
            fn p = make_parser()                 — 从工厂获取时类型由 fn 推导

        body 是单一表达式，解析优先级为 LOWEST，在当前 token 行结束
        （NEWLINE/EOF）时自然终止（由 parse_expression 处理）。
        """
        keyword_token = self.stream.previous()
        capture_mode = "lambda" if keyword_token.type == TokenType.LAMBDA else "snapshot"

        params: List[ast.IbASTNode] = []
        returns_node: Optional[ast.IbExpr] = None
        type_parser = self.context.type_parser

        # ------------------------------------------------------------------ #
        # 1. 无参：`lambda: EXPR` / `lambda -> TYPE: EXPR`                   #
        # ------------------------------------------------------------------ #
        if self.stream.check(TokenType.ARROW):
            # 表达式侧 `-> TYPE` 合法化
            self.stream.advance()  # consume '->'
            returns_node = type_parser.parse_type_annotation()
            self.stream.consume(
                TokenType.COLON,
                f"Expect ':' after return type annotation in '{capture_mode}' expression.",
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
                    f"Expect ':' after '{capture_mode}' parameter list, or ':' directly after '{capture_mode}' keyword. "
                    f"Parenthesis-only body forms are not supported; use '{capture_mode}: EXPR' or '{capture_mode}(PARAMS): EXPR'.",
                    code=PAR_UNEXPECTED_TOKEN,
                )

            # 解析参数列表
            self.stream.consume(TokenType.LPAREN, f"Expect '(' after '{capture_mode}' keyword.")
            decl = self.context.declaration_parser
            if decl is None:
                raise self.stream.error(
                    keyword_token,
                    "Internal: declaration parser not wired; cannot parse lambda parameters.",
                    code=PAR_UNEXPECTED_TOKEN,
                )
            params = decl.parameters()
            self.stream.consume(TokenType.RPAREN, f"Expect ')' after '{capture_mode}' parameter list.")

            # 表达式侧 `-> TYPE` 合法化（有参形式）
            if self.stream.check(TokenType.ARROW):
                self.stream.advance()  # consume '->'
                returns_node = type_parser.parse_type_annotation()

            # Body 必须以 ':' 起始
            self.stream.consume(TokenType.COLON, f"Expect ':' to introduce '{capture_mode}' body expression.")
            body = self.parse_expression(IbPrecedence.LOWEST)

        else:
            raise self.stream.error(
                self.stream.peek(),
                f"Expect ':' or '(' after '{capture_mode}' keyword in expression position.",
                code=PAR_UNEXPECTED_TOKEN,
            )

        node = ast.IbLambdaExpr(params=params, body=body, capture_mode=capture_mode, returns=returns_node)
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
                attr_name = self._consume_member_name()
                node = self._loc(ast.IbAttribute(value=node, attr=attr_name, ctx='Load'), dot_token)
            elif self.stream.match(TokenType.LBRACKET):
                lbracket_token = self.stream.previous()
                # 使用统一的切片/索引解析器
                slice_node = self._parse_slice_or_index()
                self.stream.consume(TokenType.RBRACKET, "Expect ']' after subscript.")
                node = self._loc(ast.IbSubscript(value=node, slice=slice_node, ctx='Load'), lbracket_token)
            else:
                break
        return node
