from core.compiler.lexer.tokens import TokenType
from core.domain import ast as ast
from core.compiler.parser.core.component import BaseComponent
from core.compiler.parser.core.syntax import ID_CALLABLE

class TypeComponent(BaseComponent):
    """
    Component for parsing type annotations (e.g., int, list[str], callable).
    Now purely token-based, leaving type validation to semantic analysis.
    """
    def parse_type_annotation(self, precedence: int = 0) -> ast.IbExpr:
        start_token = self.stream.peek()
        # 1. Base Type (Identifier or 'callable')
        base_type = None
        if self.stream.match(TokenType.IDENTIFIER):
            name_token = self.stream.previous()
            base_type = self._loc(ast.IbName(id=name_token.value, ctx='Load'), name_token)
            
            # 1.1 Support dotted names for types: db_plugin.Database
            while self.stream.match(TokenType.DOT):
                dot_token = self.stream.previous()
                member_token = self.stream.consume(TokenType.IDENTIFIER, "Expect member name after '.' in type annotation.")
                base_type = self._loc(ast.IbAttribute(value=base_type, attr=member_token.value, ctx='Load'), dot_token)
                
        elif self.stream.match(TokenType.CALLABLE):
            token = self.stream.previous()
            # [IES 2.1 Refactor] 使用语法常量，消除硬编码字符串
            callable_name = ID_CALLABLE
            if self.context.metadata:
                callable_desc = self.context.metadata.resolve(ID_CALLABLE)
                if callable_desc:
                    callable_name = callable_desc.name
            
            base_type = self._loc(ast.IbName(id=callable_name, ctx='Load'), token)
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
