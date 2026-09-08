from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional
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
    LAMBDA = auto()
    SNAPSHOT = auto()
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
    FN = auto()          # fn keyword: callable type inference (like auto but for callables)
    GLOBAL = auto()
    NONLOCAL = auto()
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
    PROTOCOL = auto()
    IMPLEMENTS = auto()
    IMPL = auto()
    SELF = auto()
    BIND = auto()

    # LLM 异常处理关键字（llmexcept 帧机制载体；llm 函数语法已删除）
    LLM_EXCEPT = auto()
    RETRY = auto()

    # 异步关键字
    AWAIT = auto()
    YIELD = auto()

    # 并发/通信关键字
    CHAN = auto()
    SLOT = auto()

    # 覆层机制关键字（临时覆层声明 + 作用域化启用）
    OVERLAY = auto()   # impl overlay for T：临时覆层声明
    WITH = auto()      # with overlay(T.m): 作用域化启用

    # 标识符与字面量
    IDENTIFIER = auto()
    NUMBER = auto()
    STRING = auto()
    TRUE = auto()
    FALSE = auto()
    NONE = auto()
    UNCERTAIN = auto()

    # 运算符
    ASSIGN = auto()
    ARROW = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    STAR_STAR = auto()  # **（幂运算）
    SLASH = auto()
    FLOOR_DIV = auto()  # //（整除）
    PERCENT = auto()

    # 复合赋值
    PLUS_ASSIGN = auto()
    MINUS_ASSIGN = auto()
    STAR_ASSIGN = auto()
    STAR_STAR_ASSIGN = auto()  # **=
    SLASH_ASSIGN = auto()
    FLOOR_DIV_ASSIGN = auto()  # //=
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
    QUESTION = auto()
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
    TAG = auto()           # 意图标签 #tag_name（仅在 IN_INTENT 状态下产生）
    RAW_TEXT = auto()
    VAR_REF = auto()
    EMBEDDED_PARAM = auto()

class LexerMode(Enum):
    NORMAL = auto()

class SubState(Enum):
    NORMAL = auto()
    IN_STRING = auto()
    IN_TRIPLE_STRING = auto()
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
    # 跨行续行标记：生成该 token 时处于未闭合构造（括号/方括号/花括号
    # 跨行未闭合）内且 token 与构造起点不同行时，记录构造起点 (line, col)。
    # 解析错误位置归位消费（错误卡住在续行行时归位到构造起点）。
    continuation_start: Optional[tuple] = None

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