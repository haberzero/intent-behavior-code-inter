from enum import IntEnum
from typing import Dict
from core.compiler.lexer.tokens import TokenType

# --- Precedence & ParseRule (Parser Core Syntax) ---

class IbPrecedence(IntEnum):
    LOWEST = 0
    ASSIGNMENT = 1  # =
    TUPLE = 2       # ,
    OR = 3          # or
    AND = 4         # and
    BIT_OR = 5      # |
    BIT_XOR = 6     # ^
    BIT_AND = 7     # &
    EQUALITY = 8    # == !=
    COMPARISON = 8  # < > <= >= Same precedence as EQUALITY
    SHIFT = 9       # << >>
    TERM = 10        # + -
    FACTOR = 11     # * / %
    UNARY = 12      # ! - +
    CALL = 13       # . ()
    PRIMARY = 14

class IbParseRule:
    def __init__(self, prefix, infix, precedence):
        self.prefix = prefix
        self.infix = infix
        self.precedence = precedence


# --- Syntax Constants (IES 2.1) ---

# Identifier constants for keyword tokens
ID_SELF: str = "self"
ID_VAR: str = "var"
ID_CALLABLE: str = "callable"

# Operator mapping: TokenType -> operator string
OP_MAP: Dict[TokenType, str] = {
    # Arithmetic operators
    TokenType.PLUS: "+",
    TokenType.MINUS: "-",
    TokenType.STAR: "*",
    TokenType.SLASH: "/",
    TokenType.PERCENT: "%",

    # Bitwise operators
    TokenType.BIT_AND: "&",
    TokenType.BIT_OR: "|",
    TokenType.BIT_XOR: "^",
    TokenType.LSHIFT: "<<",
    TokenType.RSHIFT: ">>",
    TokenType.BIT_NOT: "~",

    # Comparison operators
    TokenType.LT: "<",
    TokenType.LE: "<=",
    TokenType.GT: ">",
    TokenType.GE: ">=",
    TokenType.EQ: "==",
    TokenType.NE: "!=",

    # Logical operators
    TokenType.AND: "and",
    TokenType.OR: "or",
    TokenType.NOT: "not",
}

# Compound assignment operator mapping: TokenType -> operator string
COMPOUND_OP_MAP: Dict[TokenType, str] = {
    TokenType.PLUS_ASSIGN: "+=",
    TokenType.MINUS_ASSIGN: "-=",
    TokenType.STAR_ASSIGN: "*=",
    TokenType.SLASH_ASSIGN: "/=",
    TokenType.PERCENT_ASSIGN: "%=",
}
