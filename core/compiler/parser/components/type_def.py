from core.types.lexer_types import TokenType
from core.types import parser_types as ast
from core.compiler.parser.core.component import BaseComponent

class TypeComponent(BaseComponent):
    """
    Component for parsing type annotations (e.g., int, list[str], callable).
    Now purely token-based, leaving type validation to semantic analysis.
    """
    def parse_type_annotation(self) -> ast.Expr:
        start_token = self.stream.peek()
        # 1. Base Type (Identifier or 'callable')
        base_type = None
        if self.stream.match(TokenType.IDENTIFIER):
            name_token = self.stream.previous()
            base_type = self._loc(ast.Name(id=name_token.value, ctx='Load'), name_token)
            
            # 1.1 Support dotted names for types: db_plugin.Database
            while self.stream.match(TokenType.DOT):
                dot_token = self.stream.previous()
                member_token = self.stream.consume(TokenType.IDENTIFIER, "Expect member name after '.' in type annotation.")
                base_type = self._loc(ast.Attribute(value=base_type, attr=member_token.value, ctx='Load'), dot_token)
                
        elif self.stream.match(TokenType.CALLABLE):
            base_type = self._loc(ast.Name(id='callable', ctx='Load'), self.stream.previous())
        else:
            raise self.stream.error(self.stream.peek(), "Expect type name.")

        # 2. Generics: list[int], dict[str, Any]
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
