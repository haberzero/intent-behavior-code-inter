from enum import IntEnum

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
