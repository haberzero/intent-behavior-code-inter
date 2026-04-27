from core.compiler.common.tokens import TokenType
from core.compiler.parser.core.syntax import ID_AUTO
from core.kernel import ast as ast
from core.compiler.parser.core.component import BaseComponent

ID_FN = "fn"  # sentinel name for the fn callable-type-inference keyword

class TypeComponent(BaseComponent):
    """
    Component for parsing type annotations (e.g., int, list[str]).
    Now purely token-based, leaving type validation to semantic analysis.
    """
    def parse_type_annotation(self, precedence: int = 0) -> ast.IbExpr:
        start_token = self.stream.peek()
        # 1. Base Type (Identifier or reserved keyword used as a type)
        base_type = None
        if self.stream.match(TokenType.IDENTIFIER):
            name_token = self.stream.previous()
            base_type = self._loc(ast.IbName(id=name_token.value, ctx='Load'), name_token)
            
            # 1.1 Support dotted names for types: db_plugin.Database
            while self.stream.match(TokenType.DOT):
                dot_token = self.stream.previous()
                member_token = self.stream.consume(TokenType.IDENTIFIER, "Expect member name after '.' in type annotation.")
                base_type = self._loc(ast.IbAttribute(value=base_type, attr=member_token.value, ctx='Load'), dot_token)
        elif self.stream.match(TokenType.AUTO):
            # Allow 'auto' as a return-type annotation: func f() -> auto:
            name_token = self.stream.previous()
            base_type = self._loc(ast.IbName(id=ID_AUTO, ctx='Load'), name_token)
        elif self.stream.match(TokenType.FN):
            # Allow 'fn' as a type annotation: fn f = myFunc
            name_token = self.stream.previous()
            base_type = self._loc(ast.IbName(id=ID_FN, ctx='Load'), name_token)
        else:
            raise self.stream.error(self.stream.peek(), "Expect type name.", code="PAR_001")

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
                slice_expr = self._loc(ast.IbTuple(elts=elts, ctx='Load'), start_token)
            
            return self._loc(ast.IbSubscript(value=base_type, slice=slice_expr, ctx='Load'), start_token)
            
        return base_type
