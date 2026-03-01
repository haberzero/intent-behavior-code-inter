from typing import Dict, Optional, List, Union
from core.types.lexer_types import TokenType
from core.types import parser_types as ast
from core.types.parser_types import Precedence, ParseRule
from core.compiler.parser.core.component import BaseComponent

class ExpressionComponent(BaseComponent):
    def __init__(self, context):
        super().__init__(context)
        self.rules: Dict[TokenType, ParseRule] = {}
        self.register_rules()

    def register(self, type: TokenType, prefix, infix, precedence):
        self.rules[type] = ParseRule(prefix, infix, precedence)

    def get_rule(self, type: TokenType) -> ParseRule:
        return self.rules.get(type, ParseRule(None, None, Precedence.LOWEST))

    def parse_expression(self, precedence: Precedence = Precedence.LOWEST) -> ast.Expr:
        return self.parse_precedence(precedence)

    def parse_precedence(self, precedence: Precedence) -> ast.Expr:
        token = self.stream.advance()
        rule = self.get_rule(token.type)
        prefix = rule.prefix
        if prefix is None:
            raise self.stream.error(token, f"Expect expression. Got {token.type}")
        
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
        self.register(TokenType.IDENTIFIER, self.variable, None, Precedence.LOWEST)
        self.register(TokenType.NUMBER, self.number, None, Precedence.LOWEST)
        self.register(TokenType.STRING, self.string, None, Precedence.LOWEST)
        self.register(TokenType.BOOL, self.boolean, None, Precedence.LOWEST)
        
        # Grouping and Collections
        self.register(TokenType.LPAREN, self.grouping, self.call, Precedence.CALL)
        self.register(TokenType.LBRACKET, self.list_display, self.subscript, Precedence.CALL)
        self.register(TokenType.LBRACE, self.dict_display, None, Precedence.LOWEST)
        
        # Unary Operations
        self.register(TokenType.MINUS, self.unary, self.binary, Precedence.TERM)
        self.register(TokenType.PLUS, None, self.binary, Precedence.TERM)
        self.register(TokenType.NOT, self.unary, None, Precedence.UNARY)
        self.register(TokenType.BIT_NOT, self.unary, None, Precedence.UNARY)
        
        # Binary Operations
        self.register(TokenType.STAR, None, self.binary, Precedence.FACTOR)
        self.register(TokenType.SLASH, None, self.binary, Precedence.FACTOR)
        self.register(TokenType.PERCENT, None, self.binary, Precedence.FACTOR)
        
        # Bitwise Operations
        self.register(TokenType.BIT_AND, None, self.binary, Precedence.BIT_AND)
        self.register(TokenType.BIT_OR, None, self.binary, Precedence.BIT_OR)
        self.register(TokenType.BIT_XOR, None, self.binary, Precedence.BIT_XOR)
        self.register(TokenType.LSHIFT, None, self.binary, Precedence.SHIFT)
        self.register(TokenType.RSHIFT, None, self.binary, Precedence.SHIFT)
        
        # Comparisons
        self.register(TokenType.GT, None, self.binary, Precedence.COMPARISON)
        self.register(TokenType.GE, None, self.binary, Precedence.COMPARISON)
        self.register(TokenType.LT, None, self.binary, Precedence.COMPARISON)
        self.register(TokenType.LE, None, self.binary, Precedence.COMPARISON)
        self.register(TokenType.EQ, None, self.binary, Precedence.EQUALITY)
        self.register(TokenType.NE, None, self.binary, Precedence.EQUALITY)
        
        # Logical Operations
        self.register(TokenType.AND, None, self.logical, Precedence.AND)
        self.register(TokenType.OR, None, self.logical, Precedence.OR)
        
        # Calls and Attributes
        self.register(TokenType.DOT, None, self.dot, Precedence.CALL)
        
        # Behavior
        self.register(TokenType.BEHAVIOR_MARKER, self.behavior_expression, None, Precedence.LOWEST)

    # --- Pratt Parser Handlers ---

    def variable(self) -> ast.Expr:
        return self._loc(ast.Name(id=self.stream.previous().value, ctx='Load'), self.stream.previous())

    def number(self) -> ast.Expr:
        value = self.stream.previous().value
        if '.' in value or 'e' in value or 'E' in value:
            num = float(value)
        else:
            num = int(value)
        return self._loc(ast.Constant(value=num), self.stream.previous())

    def string(self) -> ast.Expr:
        return self._loc(ast.Constant(value=self.stream.previous().value), self.stream.previous())

    def boolean(self) -> ast.Expr:
        return self._loc(ast.Constant(value=self.stream.previous().value == 'True'), self.stream.previous())

    def grouping(self) -> ast.Expr:
        # Check for Cast Expression: (Type) Expr
        if self.stream.check(TokenType.IDENTIFIER) and self.stream.peek(1).type == TokenType.RPAREN:
            # Check if identifier is a type in symbol table
            possible_type = self.stream.peek()
            if self.scope_manager.is_type(possible_type.value):
                type_token = self.stream.advance()
                self.stream.consume(TokenType.RPAREN, "Expect ')' after cast type.")
                
                value = self.parse_precedence(Precedence.UNARY)
                return self._loc(ast.CastExpr(type_name=type_token.value, value=value), type_token)
        
        expr = self.parse_expression()
        self.stream.consume(TokenType.RPAREN, "Expect ')' after expression.")
        return expr
    
    def list_display(self) -> ast.Expr:
        start_token = self.stream.previous()
        elts = []
        if not self.stream.check(TokenType.RBRACKET):
            while True:
                elts.append(self.parse_expression())
                if not self.stream.match(TokenType.COMMA):
                    break
        self.stream.consume(TokenType.RBRACKET, "Expect ']' after list elements.")
        return self._loc(ast.ListExpr(elts=elts, ctx='Load'), start_token)

    def dict_display(self) -> ast.Expr:
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
        self.stream.consume(TokenType.RBRACE, "Expect '}' after dict entries.")
        return self._loc(ast.Dict(keys=keys, values=values), start_token)

    def unary(self) -> ast.Expr:
        op_token = self.stream.previous()
        op = op_token.type.name
        operand = self.parse_precedence(Precedence.UNARY)
        op_map = {"MINUS": "-", "PLUS": "+", "NOT": "not", "BIT_NOT": "~"}
        return self._loc(ast.UnaryOp(op=op_map.get(op, op), operand=operand), op_token)

    def binary(self, left: ast.Expr) -> ast.Expr:
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
            if isinstance(left, ast.Compare):
                left.ops.append(op_str)
                left.comparators.append(right)
                return left
            return self._loc(ast.Compare(left=left, ops=[op_str], comparators=[right]), op_token)
        
        return self._loc(ast.BinOp(left=left, op=op_str, right=right), op_token)

    def logical(self, left: ast.Expr) -> ast.Expr:
        op_token = self.stream.previous()
        op = "and" if op_token.type == TokenType.AND else "or"
        rule = self.get_rule(op_token.type)
        right = self.parse_precedence(rule.precedence)
        
        if isinstance(left, ast.BoolOp) and left.op == op:
            left.values.append(right)
            return left
            
        return self._loc(ast.BoolOp(op=op, values=[left, right]), op_token)

    def call(self, left: ast.Expr) -> ast.Call:
        start_token = self.stream.previous()
        
        intent = self.context.pending_intent
        if intent:
             self.context.pending_intent = None
            
        arguments = []
        if not self.stream.check(TokenType.RPAREN):
            while True:
                if self.stream.is_at_end():
                    raise self.stream.error(self.stream.peek(), "Unterminated argument list.")
                arguments.append(self.parse_expression())
                if not self.stream.match(TokenType.COMMA):
                    break
        self.stream.consume(TokenType.RPAREN, "Expect ')' after arguments.")
        
        return self._loc(ast.Call(func=left, args=arguments, keywords=[], intent=intent), start_token)

    def dot(self, left: ast.Expr) -> ast.Expr:
        op_token = self.stream.previous()
        name = self.stream.consume(TokenType.IDENTIFIER, "Expect property name after '.'.")
        return self._loc(ast.Attribute(value=left, attr=name.value, ctx='Load'), op_token)

    def subscript(self, left: ast.Expr) -> ast.Subscript:
        start_token = self.stream.previous()
        slice_expr = self.parse_expression()
        self.stream.consume(TokenType.RBRACKET, "Expect ']' after subscript.")
        return self._loc(ast.Subscript(value=left, slice=slice_expr, ctx='Load'), start_token)

    def behavior_expression(self) -> ast.BehaviorExpr:
        start_token = self.stream.previous()
        # Extract tag from @tag~
        tag = ""
        if start_token.value.startswith("@") and start_token.value.endswith("~"):
            tag = start_token.value[1:-1]
            
        segments = []
        
        while not self.stream.check(TokenType.BEHAVIOR_MARKER):
            if self.stream.is_at_end():
                raise self.stream.error(self.stream.peek(), "Unterminated behavior expression.")
                
            if self.stream.match(TokenType.RAW_TEXT):
                segments.append(self.stream.previous().value)
            elif self.stream.match(TokenType.VAR_REF):
                var_token = self.stream.previous()
                var_name = var_token.value[1:] # Strip $
                
                # Create initial Name node
                node = self._loc(ast.Name(id=var_name, ctx='Load'), var_token)
                
                # Support complex access within behavior expression: $obj.attr, $obj[index]
                while True:
                    if self.stream.match(TokenType.DOT):
                        dot_token = self.stream.previous()
                        attr_name = self.stream.consume(TokenType.IDENTIFIER, "Expect property name after '.'.")
                        node = self._loc(ast.Attribute(value=node, attr=attr_name.value, ctx='Load'), dot_token)
                    elif self.stream.match(TokenType.LBRACKET):
                        lbracket_token = self.stream.previous()
                        # Now we can use the standard expression parser for the index!
                        slice_expr = self.parse_expression()
                        self.stream.consume(TokenType.RBRACKET, "Expect ']' after subscript.")
                        node = self._loc(ast.Subscript(value=node, slice=slice_expr, ctx='Load'), lbracket_token)
                    else:
                        break
                
                segments.append(node)
            else:
                self.stream.advance()
        
        self.stream.consume(TokenType.BEHAVIOR_MARKER, "Expect closing '~'.")
        
        return self._loc(ast.BehaviorExpr(segments=segments, tag=tag), start_token)
