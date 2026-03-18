from dataclasses import dataclass, field
from typing import List, Optional, Union, Any
from enum import IntEnum, Enum, auto
from .issue_atomic import Location
from .intent_logic import IntentMode


# --- Scene ---

class IbScene(Enum):
    GENERAL = auto()
    BRANCH = auto()
    LOOP = auto()

# --- Precedence & ParseRule ---

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

# --- AST Nodes ---

@dataclass(eq=False, unsafe_hash=True)
class IbASTNode:
    """所有 AST 节点的基类"""
    lineno: int = 0
    col_offset: int = 0
    end_lineno: Optional[int] = None
    end_col_offset: Optional[int] = None

    def get_location(self) -> Location:
        """获取节点的物理位置对象 (Domain 层对齐)"""
        return Location(
            line=self.lineno,
            column=self.col_offset,
            end_line=self.end_lineno,
            end_column=self.end_col_offset
        )

    @property
    def line(self) -> int:
        return self.lineno

    @property
    def column(self) -> int:
        return self.col_offset

    @property
    def end_line(self) -> Optional[int]:
        return self.end_lineno

    @property
    def end_column(self) -> Optional[int]:
        return self.end_col_offset

    @property
    def length(self) -> int:
        if self.end_col_offset is not None and self.end_lineno == self.lineno:
            return max(1, self.end_col_offset - self.col_offset)
        return 1

    @property
    def creates_scope(self) -> bool:
        """Indicates if this node establishes a new symbol scope."""
        return False

@dataclass(kw_only=True, eq=False)
class IbStmt(IbASTNode):
    """语句节点基类"""
    # [IES 2.1] 统一容错机制：所有语句均可附加 LLM 异常处理块
    llm_fallback: List['IbStmt'] = field(default_factory=list)

    @property
    def supports_llm_fallback(self) -> bool:
        """
        [IES 2.1] 指示该语句是否支持附加 llm except 容错块。
        默认支持，极简控制流语句（如 pass/break）需显式禁用。
        """
        return True

@dataclass(kw_only=True, eq=False)
class IbExpr(IbASTNode):
    """表达式节点基类"""
    pass

# --- Intent Info ---

@dataclass(kw_only=True, eq=False)
class IbIntentInfo(IbASTNode):
    """意图元数据信息"""
    mode: IntentMode # [IES 2.1] 切换为枚举
    tag: Optional[str] = None # Optional tag for precise removal/masking
    content: str # Raw content or constant string
    segments: Optional[List[Union[str, 'IbExpr']]] = None # Interpolated segments for comments like @ "..."
    expr: Optional['IbExpr'] = None # Dynamic expression for 'intent expr:'

    @property
    def is_override(self) -> bool:
        return self.mode == IntentMode.OVERRIDE

    @property
    def is_remove(self) -> bool:
        return self.mode == IntentMode.REMOVE

    def resolve_content(self, context: Any, evaluator: Any = None) -> str:
        """
        编译器阶段的意图解析：尽可能返回静态内容。
        """
        return str(self.content).strip()

# --- Module ---

@dataclass(kw_only=True, eq=False)
class IbModule(IbASTNode):
    body: List[IbStmt] = field(default_factory=list)
    file_path: Optional[str] = None

    @property
    def creates_scope(self) -> bool:
        return True

    def get_location(self) -> Location:
        loc = super().get_location()
        loc.file_path = self.file_path
        return loc

# --- Statements ---

@dataclass(kw_only=True, eq=False)
class IbFunctionDef(IbStmt):
    name: str
    args: List[Union['IbArg', 'IbTypeAnnotatedExpr']]
    body: List[IbStmt]
    returns: Optional[IbExpr] = None
    
    @property
    def creates_scope(self) -> bool:
        return True

@dataclass(kw_only=True, eq=False)
class IbClassDef(IbStmt):
    name: str
    body: List[IbStmt] # Includes methods and class variables
    parent: Optional[str] = None # Parent class name
    methods: List[Union['IbFunctionDef', 'IbLLMFunctionDef']] = field(default_factory=list)
    fields: List['IbAssign'] = field(default_factory=list)
    
    @property
    def creates_scope(self) -> bool:
        return True

@dataclass(kw_only=True, eq=False)
class IbLLMFunctionDef(IbStmt):
    name: str
    args: List[Union['IbArg', 'IbTypeAnnotatedExpr']]
    sys_prompt: Optional[List[Union[str, IbExpr]]]
    user_prompt: Optional[List[Union[str, IbExpr]]]
    returns: Optional[IbExpr] = None
    
    @property
    def creates_scope(self) -> bool:
        return True

@dataclass(kw_only=True, eq=False)
class IbGlobalStmt(IbStmt):
    names: List[str]

@dataclass(kw_only=True, eq=False)
class IbReturn(IbStmt):
    value: Optional[IbExpr] = None

    @property
    def supports_llm_fallback(self) -> bool: return False

@dataclass(kw_only=True, eq=False)
class IbAssign(IbStmt):
    targets: List[IbExpr]
    value: Optional[IbExpr]

@dataclass(kw_only=True, eq=False)
class IbAugAssign(IbStmt):
    target: IbExpr
    op: str
    value: IbExpr

@dataclass(kw_only=True, eq=False)
class IbFor(IbStmt):
    target: Optional[IbExpr]
    iter: IbExpr
    body: List[IbStmt]
    orelse: List[IbStmt] = field(default_factory=list)

@dataclass(kw_only=True, eq=False)
class IbWhile(IbStmt):
    test: IbExpr
    body: List[IbStmt]
    orelse: List[IbStmt] = field(default_factory=list)

@dataclass(kw_only=True, eq=False)
class IbIf(IbStmt):
    test: IbExpr
    body: List[IbStmt]
    orelse: List[IbStmt] = field(default_factory=list)

@dataclass(kw_only=True, eq=False)
class IbTry(IbStmt):
    body: List[IbStmt]
    handlers: List['IbExceptHandler']
    orelse: List[IbStmt] = field(default_factory=list)
    finalbody: List[IbStmt] = field(default_factory=list)

@dataclass(kw_only=True, eq=False)
class IbExceptHandler(IbASTNode):
    type: Optional[IbExpr]
    name: Optional[str]
    body: List[IbStmt]

@dataclass(kw_only=True, eq=False)
class IbRaise(IbStmt):
    exc: Optional[IbExpr]
    cause: Optional[IbExpr] = None

    @property
    def supports_llm_fallback(self) -> bool: return False

@dataclass(kw_only=True, eq=False)
class IbImport(IbStmt):
    names: List['IbAlias']

    @property
    def supports_llm_fallback(self) -> bool: return False

@dataclass(kw_only=True, eq=False)
class IbImportFrom(IbStmt):
    module: Optional[str]
    names: List['IbAlias']
    level: int = 0

    @property
    def supports_llm_fallback(self) -> bool: return False

@dataclass(kw_only=True, eq=False)
class IbExprStmt(IbStmt):
    value: IbExpr

@dataclass(kw_only=True, eq=False)
class IbPass(IbStmt):
    @property
    def supports_llm_fallback(self) -> bool: return False

@dataclass(kw_only=True, eq=False)
class IbBreak(IbStmt):
    @property
    def supports_llm_fallback(self) -> bool: return False

@dataclass(kw_only=True, eq=False)
class IbContinue(IbStmt):
    @property
    def supports_llm_fallback(self) -> bool: return False

@dataclass(kw_only=True, eq=False)
class IbRetry(IbStmt):
    hint: Optional[IbExpr] = None  # retry "hint"

    @property
    def supports_llm_fallback(self) -> bool: return False

# IbLLMExceptionalStmt removed

# --- Expressions ---

@dataclass(kw_only=True, eq=False)
class IbBoolOp(IbExpr):
    op: str
    values: List[IbExpr]

@dataclass(kw_only=True, eq=False)
class IbBinOp(IbExpr):
    left: IbExpr
    op: str
    right: IbExpr

@dataclass(kw_only=True, eq=False)
class IbUnaryOp(IbExpr):
    op: str
    operand: IbExpr

@dataclass(kw_only=True, eq=False)
class IbIfExp(IbExpr):
    test: IbExpr
    body: IbExpr
    orelse: IbExpr

@dataclass(kw_only=True, eq=False)
class IbCastExpr(IbExpr):
    """类型转换表达式包装节点 (e.g., (int) expr)"""
    type_annotation: IbExpr  # IbName or IbSubscript (Generic)
    value: IbExpr

@dataclass(kw_only=True, eq=False)
class IbDict(IbExpr):
    keys: List[Optional[IbExpr]]
    values: List[IbExpr]

@dataclass(kw_only=True, eq=False)
class IbCompare(IbExpr):
    left: IbExpr
    ops: List[str]
    comparators: List[IbExpr]

@dataclass(kw_only=True, eq=False)
class IbIntentStmt(IbStmt):
    intent: IbIntentInfo
    body: List[IbStmt]
    is_exclusive: bool = False # intent ! { ... }

@dataclass(kw_only=True, eq=False)
class IbCall(IbExpr):
    func: IbExpr
    args: List[IbExpr]
    keywords: List['IbKeyword']

@dataclass(kw_only=True, eq=False)
class IbConstant(IbExpr):
    value: Any

@dataclass(kw_only=True, eq=False)
class IbAttribute(IbExpr):
    value: IbExpr
    attr: str
    ctx: str

@dataclass(kw_only=True, eq=False)
class IbSubscript(IbExpr):
    value: IbExpr
    slice: IbExpr
    ctx: str

@dataclass(kw_only=True, eq=False)
class IbName(IbExpr):
    id: str
    ctx: str

@dataclass(kw_only=True, eq=False)
class IbTuple(IbExpr):
    elts: List[IbExpr]
    ctx: str

@dataclass(kw_only=True, eq=False)
class IbListExpr(IbExpr):
    elts: List[IbExpr]
    ctx: str

@dataclass(kw_only=True, eq=False)
class IbTypeAnnotatedExpr(IbExpr):
    """持有类型标注的表达式包装节点"""
    target: IbASTNode # 可以是 IbName (变量赋值) 或 IbArg (函数参数)
    annotation: IbExpr

@dataclass(kw_only=True, eq=False)
class IbFilteredExpr(IbExpr):
    """带过滤条件的表达式包装节点 (e.g., expr if filter)"""
    expr: IbExpr
    filter: IbExpr

@dataclass(kw_only=True, eq=False)
class IbBehaviorExpr(IbExpr):
    segments: List[Union[str, IbExpr]]
    tag: str = ""

# --- Helpers ---

@dataclass(kw_only=True, eq=False)
class IbArg(IbASTNode):
    arg: str


@dataclass(kw_only=True, eq=False)
class IbKeyword(IbASTNode):
    arg: Optional[str]
    value: IbExpr

@dataclass(kw_only=True, eq=False)
class IbAlias(IbASTNode):
    name: str
    asname: Optional[str] = None
