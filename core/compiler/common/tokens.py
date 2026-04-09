from enum import Enum, auto
from dataclasses import dataclass
from core.base.source_atomic import Location

class TokenType(Enum):
    # 结构控制
    INDENT = auto()
    DEDENT = auto()
    NEWLINE = auto()
    EOF = auto()

    # 关键字
    IMPORT = auto()
    FROM = auto()
    FUNC = auto()
    RETURN = auto()
    CALLABLE = auto()
    IF = auto()
    ELIF = auto()
    ELSE = auto()
    SWITCH = auto()
    CASE = auto()
    DEFAULT = auto()
    FOR = auto()
    WHILE = auto()
    IN = auto()
    AUTO = auto()
    GLOBAL = auto()
    PASS = auto()
    BREAK = auto()
    CONTINUE = auto()
    AS = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    IS = auto()
    TRY = auto()
    EXCEPT = auto()
    FINALLY = auto()
    RAISE = auto()
    CLASS = auto()
    SELF = auto()

    # LLM 关键字
    LLM_DEF = auto()
    LLM_END = auto()
    LLM_SYS = auto()
    LLM_USER = auto()
    LLM_RETRY_HINT = auto()
    LLM_EXCEPT = auto()
    RETRY = auto()
    LLM_RETRY = auto()

    # 标识符与字面量
    IDENTIFIER = auto()
    NUMBER = auto()
    STRING = auto()
    TRUE = auto()
    FALSE = auto()
    NONE = auto()

    # 运算符
    ASSIGN = auto()
    ARROW = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()

    # 复合赋值
    PLUS_ASSIGN = auto()
    MINUS_ASSIGN = auto()
    STAR_ASSIGN = auto()
    SLASH_ASSIGN = auto()
    PERCENT_ASSIGN = auto()

    # 位运算
    BIT_AND = auto()
    BIT_OR = auto()
    BIT_XOR = auto()
    BIT_NOT = auto()
    LSHIFT = auto()
    RSHIFT = auto()

    # 分隔符
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LBRACE = auto()
    RBRACE = auto()
    COLON = auto()
    COMMA = auto()
    DOT = auto()

    # 比较运算
    EQ = auto()
    NE = auto()
    GT = auto()
    LT = auto()
    GE = auto()
    LE = auto()

    # 行为与提示词
    BEHAVIOR_MARKER = auto()
    INTENT = auto()
    RAW_TEXT = auto()
    VAR_REF = auto()
    EMBEDDED_PARAM = auto()

class LexerMode(Enum):
    NORMAL = auto()
    LLM_BLOCK = auto()

class SubState(Enum):
    NORMAL = auto()
    IN_STRING = auto()
    IN_BEHAVIOR = auto()
    IN_INTENT = auto()

@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int
    end_line: int = 0
    end_column: int = 0
    is_at_line_start: bool = False

    @property
    def length(self) -> int:
        return len(self.value) if self.value else 1

    def get_location(self) -> Location:
        return Location(
            line=self.line,
            column=self.column,
            end_line=self.end_line,
            end_column=self.end_column,
            length=len(self.value) if self.value else 1
        )