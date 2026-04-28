from enum import Enum, auto
from typing import Optional
from core.compiler.common.tokens import TokenType
from core.compiler.parser.core.token_stream import TokenStream

class SyntaxRole(Enum):
    VARIABLE_DECLARATION = auto()  # Explicit/Implicit type declaration
    FUNCTION_DEFINITION = auto()   # Traditional function
    LLM_DEFINITION = auto()        # LLM function
    CLASS_DEFINITION = auto()      # class MyClass
    IMPORT_STATEMENT = auto()      # import / from ... import
    CONTROL_FLOW = auto()          # if / for / while / elif / else
    RETURN_STATEMENT = auto()      # return
    EXPRESSION_STATEMENT = auto()  # Assignment or pure expression
    INTENT_MARKER = auto()         # @ intent
    LLM_EXCEPT = auto()            # llmexcept: ...
    BLOCK_MARKER = auto()          # INDENT / DEDENT
    OTHER = auto()

class SyntaxRecognizer:
    """
    Stateless decider for identifying the role of a syntax construct.
    Does not advance the main stream.
    """
    
    @staticmethod
    def get_role(stream: TokenStream) -> SyntaxRole:
        token = stream.peek()
        
        if token.type == TokenType.INTENT:
            return SyntaxRole.INTENT_MARKER
        
        if token.type == TokenType.LLM_EXCEPT:
            return SyntaxRole.LLM_EXCEPT
        
        if token.type in (TokenType.INDENT, TokenType.DEDENT):
            return SyntaxRole.BLOCK_MARKER
        
        if token.type == TokenType.FUNC:
            return SyntaxRole.FUNCTION_DEFINITION
        
        if token.type == TokenType.LLM_DEF:
            return SyntaxRole.LLM_DEFINITION
        
        if token.type == TokenType.CLASS:
            return SyntaxRole.CLASS_DEFINITION
        
        if token.type in (TokenType.IMPORT, TokenType.FROM):
            return SyntaxRole.IMPORT_STATEMENT
        
        if token.type in (TokenType.IF, TokenType.FOR, TokenType.WHILE, TokenType.ELIF, TokenType.ELSE):
            return SyntaxRole.CONTROL_FLOW
        
        if token.type == TokenType.RETURN:
            return SyntaxRole.RETURN_STATEMENT
        
        if token.type == TokenType.AUTO:
            return SyntaxRole.VARIABLE_DECLARATION
        
        if token.type == TokenType.FN:
            return SyntaxRole.VARIABLE_DECLARATION
        
        # Check for implicit declaration: Type Name (e.g., int x, MyClass c)
        if token.type == TokenType.IDENTIFIER:
            if SyntaxRecognizer._is_declaration_lookahead(stream):
                return SyntaxRole.VARIABLE_DECLARATION
        
        # Check for typed tuple: (int x, int y)
        if token.type == TokenType.LPAREN:
             if SyntaxRecognizer._is_typed_tuple_lookahead(stream):
                 return SyntaxRole.VARIABLE_DECLARATION
            
        return SyntaxRole.EXPRESSION_STATEMENT

    @staticmethod
    def _is_typed_tuple_lookahead(stream: TokenStream) -> bool:
        """
        Check if (ID ID, ID ID) or (Type Name, Type Name) exists.
        Handles (int x, int y) or (list[int] x, str y).
        """
        # Skip '('
        offset = 1
        
        # We need to find at least one 'Type Name' inside the parentheses
        # followed by a comma or ')'
        while True:
            t = stream.peek(offset)
            if t.type in (TokenType.EOF, TokenType.NEWLINE, TokenType.RPAREN):
                break
            
            # Check for a single declaration: Type Name
            if t.type == TokenType.IDENTIFIER:
                # Use the existing declaration logic starting from current offset
                # We need a modified version of _is_declaration_lookahead that works with an offset
                if SyntaxRecognizer._check_declaration_at_offset(stream, offset):
                    return True
            
            # If it's not a declaration, it might be a comma or just a value.
            # But we only care if we find a typed declaration.
            offset += 1
            if offset > 20: # Safety limit for lookahead
                break
                
        return False

    @staticmethod
    def _check_declaration_at_offset(stream: TokenStream, offset: int) -> bool:
        """Lookahead at a specific offset to see if it's a Type Name declaration."""
        current = offset
        
        # 1. Skip dotted names
        while stream.peek(current).type == TokenType.IDENTIFIER:
            if stream.peek(current + 1).type == TokenType.DOT:
                current += 2
            else:
                break
        
        # 2. Check next token
        next_t = stream.peek(current + 1)
        if next_t.type in (TokenType.IDENTIFIER, TokenType.FN):
            return True
            
        # 3. Check generics
        if next_t.type == TokenType.LBRACKET:
            return SyntaxRecognizer._check_generic_lookahead(stream, current + 1)
            
        return False

    @staticmethod
    def _is_declaration_lookahead(stream: TokenStream) -> bool:
        """
        Pure token-based lookahead to distinguish between 'Type Name' and 'Name = Expr'.
        Handles generics like 'list[int] x' and dotted types 'a.b x'.
        """
        current_offset = 0
        
        # 1. Skip dotted names: a.b.c
        while stream.peek(current_offset).type == TokenType.IDENTIFIER:
            if stream.peek(current_offset + 1).type == TokenType.DOT:
                current_offset += 2
            else:
                break
        
        # Now we are at the end of the base type name
        next_t = stream.peek(current_offset + 1)
        
        # 2. Heuristic check: '... ID ID' (e.g., 'int x', 'a.b y')
        if next_t.type == TokenType.IDENTIFIER:
            return True
            
        # 2b. Heuristic check: '... ID lambda/snapshot/fn ID' (e.g., 'int fn f', 'int lambda x')
        if next_t.type in (TokenType.LAMBDA, TokenType.SNAPSHOT, TokenType.FN):
            return True
            
        # 3. Heuristic check: '... ID [ ... ] ID' (e.g., 'list[int] x', 'a.b[int] y')
        if next_t.type == TokenType.LBRACKET:
            return SyntaxRecognizer._check_generic_lookahead(stream, current_offset + 1)
            
        return False

    @staticmethod
    def _check_generic_lookahead(stream: TokenStream, offset: int) -> bool:
        bracket_depth = 0
        current_offset = offset
        
        while True:
            t = stream.peek(current_offset)
            if t.type == TokenType.EOF or t.type == TokenType.NEWLINE:
                return False
                
            if t.type == TokenType.LBRACKET:
                bracket_depth += 1
            elif t.type == TokenType.RBRACKET:
                bracket_depth -= 1
                if bracket_depth == 0:
                    # Found closing bracket. Check if next is an identifier, lambda, snapshot, or fn.
                    next_t = stream.peek(current_offset + 1)
                    return next_t.type in (TokenType.IDENTIFIER, TokenType.LAMBDA, TokenType.SNAPSHOT, TokenType.FN)
            
            current_offset += 1
            if current_offset > 100: # Safety limit
                return False
