from dataclasses import dataclass, field
from typing import List, Optional, Union, Any
from enum import IntEnum, auto
from core.base.source_atomic import Location
from .intent_logic import IntentMode


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
    pass

@dataclass(kw_only=True, eq=False)
class IbExpr(IbASTNode):
    """表达式节点基类"""
    pass

# --- Intent Info ---

@dataclass(kw_only=True, eq=False)
class IbIntentInfo(IbASTNode):
    """意图元数据信息"""
    mode: IntentMode # 切换为枚举
    tag: Optional[str] = None # Optional tag for precise removal/masking
    content: str # Raw content or constant string
    segments: Optional[List[Union[str, 'IbExpr']]] = None # Interpolated segments for comments like @ "..."
    expr: Optional['IbExpr'] = None # Dynamic expression for 'intent expr:'
    pop_top: bool = False # 特殊标记：@- 无参数时为 True，表示移除栈顶意图

    @property
    def is_override(self) -> bool:
        return self.mode == IntentMode.OVERRIDE

    @property
    def is_remove(self) -> bool:
        return self.mode == IntentMode.REMOVE

    @property
    def is_pop_top(self) -> bool:
        """判断是否为无参数的 @-（移除栈顶意图）"""
        return self.mode == IntentMode.REMOVE and self.pop_top

    def resolve_content(self, context: Any, evaluator: Any = None) -> str:
        """
        编译器阶段的意图解析：尽可能返回静态内容。
        """
        return str(self.content).strip()

@dataclass(kw_only=True, eq=False)
class IbIntentAnnotation(IbStmt):
    """
    意图注释节点 - @ 和 @! 专用
    替代涂抹式关联，实现意图注释的 AST 级别独立表示。
    
    设计说明：
    - @ (APPEND): 单行意图，必须后续紧跟 LLM 调用
    - @! (OVERRIDE): 排他意图，必须后续紧跟 LLM 调用
    """
    intent: IbIntentInfo

@dataclass(kw_only=True, eq=False)
class IbIntentStackOperation(IbStmt):
    """
    意图栈操作节点 - @+ 和 @- 专用
    允许独立存在，作为全局意图栈操作。
    
    设计说明：
    - @+ (APPEND): 叠加意图到栈，允许独立存在
    - @- (REMOVE): 从栈中移除意图，允许独立存在
    """
    intent: IbIntentInfo

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
    retry_hint: Optional[List[Union[str, IbExpr]]] = None
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
class IbSwitch(IbStmt):
    """Switch-Case 语句"""
    test: IbExpr  # 要匹配的表达式
    cases: List['IbCase']  # case 列表

@dataclass(kw_only=True, eq=False)
class IbCase(IbASTNode):
    """Switch Case"""
    pattern: Optional[IbExpr]  # 匹配的值，None 表示 default
    body: List[IbStmt]  # case 匹配的语句体

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

@dataclass(kw_only=True, eq=False)
class IbImport(IbStmt):
    names: List['IbAlias']

@dataclass(kw_only=True, eq=False)
class IbImportFrom(IbStmt):
    module: Optional[str]
    names: List['IbAlias']
    level: int = 0

@dataclass(kw_only=True, eq=False)
class IbExprStmt(IbStmt):
    value: IbExpr

@dataclass(kw_only=True, eq=False)
class IbPass(IbStmt):
    pass

@dataclass(kw_only=True, eq=False)
class IbBreak(IbStmt):
    pass

@dataclass(kw_only=True, eq=False)
class IbContinue(IbStmt):
    pass

@dataclass(kw_only=True, eq=False)
class IbRetry(IbStmt):
    hint: Optional[IbExpr] = None

@dataclass(kw_only=True, eq=False)
class IbLLMExceptionalStmt(IbStmt):
    """
    llmexcept 语句结构。
    包含触发语句和对应的异常处理块。
    
    语法：
    statement
    llmexcept:
        statements...
    
    或者：
    statement
    llmexcept retry "hint"
    """
    target: IbStmt
    body: List[IbStmt] = field(default_factory=list)

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
class IbSlice(IbExpr):
    lower: Optional[IbExpr] = None
    upper: Optional[IbExpr] = None
    step: Optional[IbExpr] = None

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
