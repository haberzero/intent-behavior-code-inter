from typing import Dict, Optional, List, Union
from core.domain.tokens import TokenType
from core.domain import ast as ast
from core.domain.ast import IbPrecedence, IbParseRule
from core.compiler.parser.core.component import BaseComponent

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
        self.register(TokenType.BOOL, self.boolean, None, IbPrecedence.LOWEST)
        self.register(TokenType.NONE, self.none_expr, None, IbPrecedence.LOWEST)
        
        # Grouping and Collections
        self.register(TokenType.LPAREN, self.grouping, self.call, IbPrecedence.CALL)
        self.register(TokenType.LBRACKET, self.list_display, self.subscript, IbPrecedence.CALL)
        self.register(TokenType.LBRACE, self.dict_display, None, IbPrecedence.LOWEST)
        
        # Unary Operations
        self.register(TokenType.MINUS, self.unary, self.binary, IbPrecedence.TERM)
        self.register(TokenType.PLUS, None, self.binary, IbPrecedence.TERM)
        self.register(TokenType.NOT, self.unary, None, IbPrecedence.UNARY)
        self.register(TokenType.BIT_NOT, self.unary, None, IbPrecedence.UNARY)
        
        # Binary Operations
        self.register(TokenType.STAR, None, self.binary, IbPrecedence.FACTOR)
        self.register(TokenType.SLASH, None, self.binary, IbPrecedence.FACTOR)
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

    # --- Pratt Parser Handlers ---

    def variable(self) -> ast.IbExpr:
        return self._loc(ast.IbName(id=self.stream.previous().value, ctx='Load'), self.stream.previous())

    def self_expr(self) -> ast.IbExpr:
        return self._loc(ast.IbName(id='self', ctx='Load'), self.stream.previous())

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
        return self._loc(ast.IbConstant(value=self.stream.previous().value == 'True'), self.stream.previous())

    def none_expr(self) -> ast.IbExpr:
        return self._loc(ast.IbConstant(value=None), self.stream.previous())

    def grouping(self) -> ast.IbExpr:
        # Check for Cast Expression: (Type) Expr
        # Heuristic: (ID) followed by something that is not an operator
        if self.stream.check(TokenType.IDENTIFIER) and self.stream.peek(1).type == TokenType.RPAREN:
            # Look ahead to see if it's followed by a unary expression start
            # This is a bit tricky without a full recognizer here, but (ID) ID is a strong signal
            next_after_rparen = self.stream.peek(2)
            if next_after_rparen.type in (TokenType.IDENTIFIER, TokenType.NUMBER, TokenType.STRING, TokenType.LPAREN, TokenType.LBRACKET, TokenType.BEHAVIOR_MARKER):
                type_token = self.stream.advance() # ID
                self.stream.consume(TokenType.RPAREN, "Expect ')' after cast type.")
                value = self.parse_precedence(IbPrecedence.UNARY)
                return self._loc(ast.IbCastExpr(type_name=type_token.value, value=value), type_token)
        
        expr = self.parse_expression()
        self.stream.consume(TokenType.RPAREN, "Expect ')' after expression.")
        return expr
    
    def list_display(self) -> ast.IbExpr:
        start_token = self.stream.previous()
        elts = []
        if not self.stream.check(TokenType.RBRACKET):
            while True:
                elts.append(self.parse_expression())
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
                keys.append(self.parse_expression())
                self.stream.consume(TokenType.COLON, "Expect ':' after dict key.")
                values.append(self.parse_expression())
                if not self.stream.match(TokenType.COMMA):
                    break
        end_token = self.stream.consume(TokenType.RBRACE, "Expect '}' after dict entries.")
        return self._loc(ast.IbDict(keys=keys, values=values), start_token, end_token)

    def unary(self) -> ast.IbExpr:
        op_token = self.stream.previous()
        op = op_token.type.name
        operand = self.parse_precedence(IbPrecedence.UNARY)
        op_map = {"MINUS": "-", "PLUS": "+", "NOT": "not", "BIT_NOT": "~"}
        return self._loc(ast.IbUnaryOp(op=op_map.get(op, op), operand=operand), op_token, operand)

    def binary(self, left: ast.IbExpr) -> ast.IbExpr:
        op_token = self.stream.previous()
        op = op_token.type.name
        rule = self.get_rule(op_token.type)
        right = self.parse_precedence(rule.precedence)
        
        op_map = {
            "PLUS": "+", "MINUS": "-", "STAR": "*", "SLASH": "/", "PERCENT": "%",
            "GT": ">", "GE": ">=", "LT": "<", "LE": "<=", "EQ": "==", "NE": "!=",
            "BIT_AND": "&", "BIT_OR": "|", "BIT_XOR": "^", "LSHIFT": "<<", "RSHIFT": ">>"
        }
        op_str = op_map.get(op, op)
        
        comparison_ops = ("GT", "GE", "LT", "LE", "EQ", "NE")
        
        if op in comparison_ops:
            if isinstance(left, ast.IbCompare):
                left.ops.append(op_str)
                left.comparators.append(right)
                return self._extend_loc(left, right)
            return self._loc(ast.IbCompare(left=left, ops=[op_str], comparators=[right]), left, right)
        
        return self._loc(ast.IbBinOp(left=left, op=op_str, right=right), left, right)

    def logical(self, left: ast.IbExpr) -> ast.IbExpr:
        op_token = self.stream.previous()
        op = "and" if op_token.type == TokenType.AND else "or"
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
                arguments.append(self.parse_expression())
                if not self.stream.match(TokenType.COMMA):
                    break
        end_token = self.stream.consume(TokenType.RPAREN, "Expect ')' after arguments.")
        
        # [NEW] 意图节点化：不再向 Call 注入 intent 属性
        return self._loc(ast.IbCall(func=left, args=arguments, keywords=[]), left, end_token)

    def dot(self, left: ast.IbExpr) -> ast.IbExpr:
        name = self.stream.consume(TokenType.IDENTIFIER, "Expect property name after '.'.")
        return self._loc(ast.IbAttribute(value=left, attr=name.value, ctx='Load'), left, name)

    def subscript(self, left: ast.IbExpr) -> ast.IbSubscript:
        slice_expr = self.parse_expression()
        end_token = self.stream.consume(TokenType.RBRACKET, "Expect ']' after subscript.")
        return self._loc(ast.IbSubscript(value=left, slice=slice_expr, ctx='Load'), left, end_token)

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
            else:
                self.stream.advance()
        
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
                # Now we can use the standard expression parser for the index!
                slice_expr = self.parse_expression()
                self.stream.consume(TokenType.RBRACKET, "Expect ']' after subscript.")
                node = self._loc(ast.IbSubscript(value=node, slice=slice_expr, ctx='Load'), lbracket_token)
            else:
                break
        return node
