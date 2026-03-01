from enum import Enum, auto
from typing import Optional
from core.types.lexer_types import TokenType
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
    BLOCK_MARKER = auto()          # INDENT / DEDENT
    OTHER = auto()

class SyntaxRecognizer:
    """
    Stateless decider for identifying the role of a syntax construct.
    Does not advance the main stream.
    """
    
    @staticmethod
    def get_role(stream: TokenStream, scope_manager=None) -> SyntaxRole:
        token = stream.peek()
        
        if token.type == TokenType.INTENT:
            return SyntaxRole.INTENT_MARKER
        
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
        
        if token.type == TokenType.VAR:
            return SyntaxRole.VARIABLE_DECLARATION
        
        # Check for implicit declaration: Type Name
        if token.type == TokenType.IDENTIFIER:
            if SyntaxRecognizer._is_declaration_lookahead(stream, scope_manager):
                return SyntaxRole.VARIABLE_DECLARATION
            
        return SyntaxRole.EXPRESSION_STATEMENT

    @staticmethod
    def _is_declaration_lookahead(stream: TokenStream, scope_manager) -> bool:
        """
        Deep lookahead to distinguish between 'Type Name' and 'Name = Expr'.
        Handles generics like 'list[int] x'.
        """
        # 1. Check if the current identifier is a known type (if scope_manager provided)
        if scope_manager and scope_manager.is_type(stream.peek().value):
            # Known type, check what follows
            next_token = stream.peek(1)
            if next_token.type == TokenType.IDENTIFIER:
                return True
            if next_token.type == TokenType.LBRACKET:
                return SyntaxRecognizer._check_generic_lookahead(stream, 1)
        
        # 2. Heuristic check: 'ID ID' is almost always a declaration in IBC-Inter
        # e.g., 'int x', 'MyType y'
        if stream.peek(1).type == TokenType.IDENTIFIER:
            return True
            
        # 3. Heuristic check: 'ID [ ... ] ID'
        if stream.peek(1).type == TokenType.LBRACKET:
            return SyntaxRecognizer._check_generic_lookahead(stream, 1)
            
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
                    # Found closing bracket. Check if next is an identifier.
                    next_t = stream.peek(current_offset + 1)
                    return next_t.type == TokenType.IDENTIFIER
            
            current_offset += 1
            if current_offset > 100: # Safety limit
                return False
