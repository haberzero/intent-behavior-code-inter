from enum import Enum, auto
from dataclasses import dataclass

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
    FOR = auto()
    WHILE = auto()
    IN = auto()
    VAR = auto()
    PASS = auto()
    BREAK = auto()
    CONTINUE = auto()
    AS = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    IS = auto()
    NONE = auto()
    TRY = auto()
    EXCEPT = auto()
    FINALLY = auto()
    RAISE = auto()
    CLASS = auto()
    SELF = auto()
    
    # LLM 关键字
    LLM_DEF = auto()    # llm
    LLM_END = auto()    # llmend
    LLM_SYS = auto()    # __sys__
    LLM_USER = auto()   # __user__
    LLM_EXCEPT = auto() # llmexcept
    RETRY = auto()      # retry
    INTENT_STMT = auto() # intent

    # 标识符与字面量
    IDENTIFIER = auto()
    NUMBER = auto()
    STRING = auto()
    BOOL = auto()

    # 运算符
    ASSIGN = auto()         # =
    ARROW = auto()          # ->
    PLUS = auto()           # +
    MINUS = auto()          # -
    STAR = auto()           # *
    SLASH = auto()          # /
    PERCENT = auto()        # %
    
    # 复合赋值
    PLUS_ASSIGN = auto()    # +=
    MINUS_ASSIGN = auto()   # -=
    STAR_ASSIGN = auto()    # *=
    SLASH_ASSIGN = auto()   # /=
    PERCENT_ASSIGN = auto() # %=
    
    # 位运算
    BIT_AND = auto()        # &
    BIT_OR = auto()         # |
    BIT_XOR = auto()        # ^
    BIT_NOT = auto()        # ~ (当作为位非运算时)
    LSHIFT = auto()         # <<
    RSHIFT = auto()         # >>
    
    # 分隔符
    LPAREN = auto()         # (
    RPAREN = auto()         # )
    LBRACKET = auto()       # [
    RBRACKET = auto()       # ]
    LBRACE = auto()         # {
    RBRACE = auto()         # }
    COLON = auto()          # :
    COMMA = auto()          # ,
    DOT = auto()            # .
    
    # 比较运算
    EQ = auto()             # ==
    NE = auto()             # !=
    GT = auto()             # >
    LT = auto()             # <
    GE = auto()             # >=
    LE = auto()             # <=

    # 行为与提示词
    BEHAVIOR_MARKER = auto()    # @~ or @tag~ or ~
    INTENT = auto()             # @ intent
    RAW_TEXT = auto()           # 提示词或行为描述文本
    VAR_REF = auto()            # $var
    PARAM_PLACEHOLDER = auto()  # $__param__

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
