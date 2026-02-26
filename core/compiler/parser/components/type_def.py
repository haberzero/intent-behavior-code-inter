from core.types.lexer_types import TokenType
from core.types import parser_types as ast
from core.compiler.parser.core.component import BaseComponent

class TypeComponent(BaseComponent):
    def parse_type_annotation(self) -> ast.Expr:
        start_token = self.stream.peek()
        # 1. Base Type
        base_type = None
        if self.stream.check(TokenType.IDENTIFIER):
            # Check if it's a valid type in symbol table
            if self.scope_manager.is_type(self.stream.peek().value):
                self.stream.advance()
                base_type = self._loc(ast.Name(id=self.stream.previous().value, ctx='Load'), self.stream.previous())
            else:
                # Fallback: Assume it's a type (e.g. forward reference or user type not yet fully registered)
                self.stream.advance()
                base_type = self._loc(ast.Name(id=self.stream.previous().value, ctx='Load'), self.stream.previous())
        else:
            raise self.stream.error(self.stream.peek(), "Expect type name.")

        # 2. Generics
        if self.stream.match(TokenType.LBRACKET):
            elts = []
            while True:
                elts.append(self.parse_type_annotation())
                if not self.stream.match(TokenType.COMMA):
                    break
            
            self.stream.consume(TokenType.RBRACKET, "Expect ']' after type arguments.")
            
            if len(elts) == 1:
                slice_expr = elts[0]
            else:
                slice_expr = self._loc(ast.ListExpr(elts=elts, ctx='Load'), start_token)
            
            return self._loc(ast.Subscript(value=base_type, slice=slice_expr, ctx='Load'), start_token)
            
        return base_type
