from dataclasses import dataclass, field
from typing import List, Optional, Union, Any
from enum import IntEnum, Enum, auto
from core.types.scope_types import ScopeNode

# --- Scene ---

class Scene(Enum):
    GENERAL = auto()
    BRANCH = auto()
    LOOP = auto()

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

@dataclass(kw_only=True)
class ASTNode:
    """AST 节点基类"""
    lineno: int = 0
    col_offset: int = 0
    end_lineno: int = 0
    end_col_offset: int = 0
    uid: str = field(default_factory=lambda: "")
    scope: Optional[ScopeNode] = None # Attached ScopeNode from symbol table

    @property
    def line(self) -> int:
        return self.lineno

    @property
    def column(self) -> int:
        return self.col_offset

@dataclass(kw_only=True)
class Stmt(ASTNode):
    """语句节点基类"""
    pass

@dataclass(kw_only=True)
class Expr(ASTNode):
    """表达式节点基类"""
    scene_tag: Scene = field(default=Scene.GENERAL)

# --- Module ---

@dataclass
class Module(ASTNode):
    body: List[Stmt] = field(default_factory=list)

# --- Statements ---

@dataclass
class FunctionDef(Stmt):
    name: str
    args: List['arg']
    body: List[Stmt]
    returns: Optional[Expr] = None

@dataclass
class ClassDef(Stmt):
    name: str
    body: List[Stmt] # Includes methods and class variables
    methods: List[Union['FunctionDef', 'LLMFunctionDef']] = field(default_factory=list)
    fields: List['Assign'] = field(default_factory=list)

@dataclass
class LLMFunctionDef(Stmt):
    name: str
    args: List['arg']
    sys_prompt: Optional[List[Union[str, Expr]]]
    user_prompt: Optional[List[Union[str, Expr]]]
    returns: Optional[Expr] = None

@dataclass
class Return(Stmt):
    value: Optional[Expr] = None

@dataclass
class Assign(Stmt):
    targets: List[Expr]
    value: Optional[Expr]
    type_annotation: Optional[Expr] = None

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
    llm_fallback: Optional[List[Stmt]] = None

@dataclass
class While(Stmt):
    test: Expr
    body: List[Stmt]
    orelse: List[Stmt] = field(default_factory=list)
    llm_fallback: Optional[List[Stmt]] = None

@dataclass
class If(Stmt):
    test: Expr
    body: List[Stmt]
    orelse: List[Stmt] = field(default_factory=list)
    llm_fallback: Optional[List[Stmt]] = None

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
    pass

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
class Call(Expr):
    func: Expr
    args: List[Expr]
    keywords: List['keyword']
    intent: Optional[str] = None

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
class BehaviorExpr(Expr):
    segments: List[Union[str, Expr]]
    tag: str = ""
    intent: Optional[str] = None

@dataclass
class CastExpr(Expr):
    type_name: str
    value: Expr

# --- Helpers ---

@dataclass
class arg(ASTNode):
    arg: str
    annotation: Optional[Expr] = None


@dataclass
class keyword(ASTNode):
    arg: Optional[str]
    value: Expr

@dataclass
class alias(ASTNode):
    name: str
    asname: Optional[str] = None
