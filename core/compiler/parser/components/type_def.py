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
            # D3: also handle callable signature form: fn[(param_types) -> return_type]
            name_token = self.stream.previous()
            base_type = self._loc(ast.IbName(id=ID_FN, ctx='Load'), name_token)
            # Peek ahead: if '[' follows, try to parse as a callable signature.
            # We use a speculative lookahead: if the bracket contains '(', it's a
            # callable sig; otherwise it's a generic subscript (falls through below).
            if self.stream.check(TokenType.LBRACKET):
                callable_sig = self._try_parse_callable_sig(name_token)
                if callable_sig is not None:
                    return callable_sig
                # Not a callable sig — fall through to the generic subscript path.
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

    # ---------------------------------------------------------------------- #
    # D3: callable signature parsing                                          #
    # ---------------------------------------------------------------------- #

    def _try_parse_callable_sig(self, fn_token) -> ast.IbCallableType:
        """
        Speculatively attempt to parse a D3 callable signature of the form::

            fn[(param_type, ...) -> return_type]

        Callable if the bracket content starts with ``(``.  Returns an
        ``IbCallableType`` node on success, or ``None`` if the content does
        not match the callable signature form (caller falls back to the
        generic subscript path).

        Grammar::

            callable_sig  ::= '[' '(' type_list ')' '->' type ']'
            type_list     ::= type (',' type)*
                            | empty
        """
        # We already know '[' is next; consume it speculatively.
        # If the content is not a callable sig we need to un-consume.
        # TokenStream supports save/restore for this.
        saved_pos = self.stream.get_checkpoint()
        try:
            self.stream.advance()  # consume '['
            if not self.stream.check(TokenType.LPAREN):
                # Not a callable sig — restore and return None
                self.stream.restore_checkpoint(saved_pos)
                return None

            # Parse the callable signature: (type, ...) -> return_type
            return self._parse_fn_signature(fn_token)
        except Exception:
            self.stream.restore_checkpoint(saved_pos)
            return None

    def _parse_fn_signature(self, fn_token) -> ast.IbCallableType:
        """
        Parse the callable signature body after ``fn[`` has been consumed.

        Expects::   ``(type_list) -> return_type ]``

        Returns an ``IbCallableType`` node.
        """
        self.stream.consume(TokenType.LPAREN, "Expect '(' in callable signature 'fn[(param_types) -> return_type]'.")
        
        param_types = []
        if not self.stream.check(TokenType.RPAREN):
            while True:
                param_types.append(self.parse_type_annotation())
                if not self.stream.match(TokenType.COMMA):
                    break
        
        self.stream.consume(TokenType.RPAREN, "Expect ')' after parameter types in callable signature.")
        self.stream.consume(TokenType.ARROW, "Expect '->' in callable signature 'fn[(params) -> return_type]'.")
        
        return_type = self.parse_type_annotation()
        
        self.stream.consume(TokenType.RBRACKET, "Expect ']' to close callable signature 'fn[(params) -> return_type]'.")
        
        node = ast.IbCallableType(param_types=param_types, return_type=return_type)
        return self._loc(node, fn_token)

