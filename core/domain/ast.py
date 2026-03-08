from dataclasses import dataclass, field
from typing import List, Optional, Union, Any, TYPE_CHECKING
from enum import IntEnum, Enum, auto

if TYPE_CHECKING:
    from core.domain.symbols import Symbol, StaticType

# --- Scene ---

class Scene(Enum):
    GENERAL = auto()
    BRANCH = auto()
    LOOP = auto()

# --- Intent Info ---

@dataclass
class IntentInfo:
    mode: str # "", "+", "!", "-"
    content: str # Raw content or constant string
    segments: Optional[List[Union[str, 'Expr']]] = None # Interpolated segments for comments like @ "..."
    expr: Optional['Expr'] = None # Dynamic expression for 'intent expr:'
    
    # Position info
    lineno: int = 0
    col_offset: int = 0

# --- Precedence & ParseRule ---

class Precedence(IntEnum):
    LOWEST = 0
    ASSIGNMENT = 1  # =
    OR = 2          # or
    AND = 3         # and
    BIT_OR = 4      # |
    BIT_XOR = 5     # ^
    BIT_AND = 6     # &
    EQUALITY = 7    # == !=
    COMPARISON = 7  # < > <= >= Same precedence as EQUALITY
    SHIFT = 8       # << >>
    TERM = 9        # + -
    FACTOR = 10     # * / %
    UNARY = 11      # ! - +
    CALL = 12       # . ()
    PRIMARY = 13

class ParseRule:
    def __init__(self, prefix, infix, precedence):
        self.prefix = prefix
        self.infix = infix
        self.precedence = precedence

# --- AST Nodes ---

import uuid

@dataclass(kw_only=True)
class ASTNode:
    """AST 节点基类"""
    lineno: int = 0
    col_offset: int = 0
    end_lineno: int = 0
    end_col_offset: int = 0
    uid: str = field(default_factory=lambda: f"node_{uuid.uuid4().hex[:8]}")
    
    @property
    def line(self) -> int:
        return self.lineno

    @property
    def column(self) -> int:
        return self.col_offset

    @property
    def creates_scope(self) -> bool:
        """Indicates if this node establishes a new symbol scope."""
        return False

@dataclass(kw_only=True)
class Stmt(ASTNode):
    """语句节点基类"""
    pass

@dataclass(kw_only=True)
class Expr(ASTNode):
    """表达式节点基类"""
    pass

# --- Module ---

@dataclass
class Module(ASTNode):
    body: List[Stmt] = field(default_factory=list)
    file_path: Optional[str] = None

    @property
    def creates_scope(self) -> bool:
        return True

# --- Statements ---

@dataclass
class AnnotatedStmt(Stmt):
    """持有意图注释的包装语句节点"""
    intent: IntentInfo
    stmt: Stmt

@dataclass
class AnnotatedExpr(Expr):
    """持有意图注释的包装表达式节点"""
    intent: IntentInfo
    expr: Expr

@dataclass
class FunctionDef(Stmt):
    name: str
    args: List['arg']
    body: List[Stmt]
    returns: Optional[Expr] = None
    
    @property
    def creates_scope(self) -> bool:
        return True

@dataclass
class ClassDef(Stmt):
    name: str
    body: List[Stmt] # Includes methods and class variables
    parent: Optional[str] = None # Parent class name
    methods: List[Union['FunctionDef', 'LLMFunctionDef']] = field(default_factory=list)
    fields: List['Assign'] = field(default_factory=list)
    
    @property
    def creates_scope(self) -> bool:
        return True

@dataclass
class LLMFunctionDef(Stmt):
    name: str
    args: List['arg']
    sys_prompt: Optional[List[Union[str, Expr]]]
    user_prompt: Optional[List[Union[str, Expr]]]
    returns: Optional[Expr] = None
    
    @property
    def creates_scope(self) -> bool:
        return True

@dataclass
class GlobalStmt(Stmt):
    names: List[str]

@dataclass
class Return(Stmt):
    value: Optional[Expr] = None

@dataclass
class Assign(Stmt):
    targets: List[Expr]
    value: Optional[Expr]

@dataclass
class AugAssign(Stmt):
    target: Expr
    op: str
    value: Expr

@dataclass
class For(Stmt):
    target: Optional[Expr]
    iter: Expr
    body: List[Stmt]
    orelse: List[Stmt] = field(default_factory=list)

@dataclass
class While(Stmt):
    test: Expr
    body: List[Stmt]
    orelse: List[Stmt] = field(default_factory=list)

@dataclass
class If(Stmt):
    test: Expr
    body: List[Stmt]
    orelse: List[Stmt] = field(default_factory=list)

@dataclass
class Try(Stmt):
    body: List[Stmt]
    handlers: List['ExceptHandler']
    orelse: List[Stmt] = field(default_factory=list)
    finalbody: List[Stmt] = field(default_factory=list)

@dataclass
class ExceptHandler(ASTNode):
    type: Optional[Expr]
    name: Optional[str]
    body: List[Stmt]

@dataclass
class Raise(Stmt):
    exc: Optional[Expr]
    cause: Optional[Expr] = None

@dataclass
class Import(Stmt):
    names: List['alias']

@dataclass
class ImportFrom(Stmt):
    module: Optional[str]
    names: List['alias']
    level: int = 0

@dataclass
class ExprStmt(Stmt):
    value: Expr

@dataclass
class Pass(Stmt):
    pass

@dataclass
class Break(Stmt):
    pass

@dataclass
class Continue(Stmt):
    pass

@dataclass
class Retry(Stmt):
    hint: Optional[Expr] = None  # retry "hint"

@dataclass
class LLMExceptionalStmt(Stmt):
    primary: Stmt
    fallback: List[Stmt]

# --- Expressions ---

@dataclass
class BoolOp(Expr):
    op: str
    values: List[Expr]

@dataclass
class BinOp(Expr):
    left: Expr
    op: str
    right: Expr

@dataclass
class UnaryOp(Expr):
    op: str
    operand: Expr

@dataclass
class IfExp(Expr):
    test: Expr
    body: Expr
    orelse: Expr

@dataclass
class Dict(Expr):
    keys: List[Optional[Expr]]
    values: List[Expr]

@dataclass
class Compare(Expr):
    left: Expr
    ops: List[str]
    comparators: List[Expr]

@dataclass
class IntentStmt(Stmt):
    intent: IntentInfo
    body: List[Stmt]
    is_exclusive: bool = False # intent ! { ... }

@dataclass
class Call(Expr):
    func: Expr
    args: List[Expr]
    keywords: List['keyword']

@dataclass
class Constant(Expr):
    value: Any


@dataclass
class Attribute(Expr):
    value: Expr
    attr: str
    ctx: str

@dataclass
class Subscript(Expr):
    value: Expr
    slice: Expr
    ctx: str

@dataclass
class Name(Expr):
    id: str
    ctx: str

@dataclass
class ListExpr(Expr):
    elts: List[Expr]
    ctx: str

@dataclass
class TypeAnnotatedExpr(Expr):
    """持有类型标注的表达式包装节点"""
    target: ASTNode # 可以是 Name (变量赋值) 或 arg (函数参数)
    annotation: Expr

@dataclass
class FilteredExpr(Expr):
    """带过滤条件的表达式包装节点 (e.g., expr if filter)"""
    expr: Expr
    filter: Expr

@dataclass
class BehaviorExpr(Expr):
    segments: List[Union[str, Expr]]
    tag: str = ""

# --- Helpers ---

@dataclass
class arg(ASTNode):
    arg: str


@dataclass
class keyword(ASTNode):
    arg: Optional[str]
    value: Expr

@dataclass
class alias(ASTNode):
    name: str
    asname: Optional[str] = None
