from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, List, Any, Protocol, runtime_checkable

class Severity(Enum):
    HINT = auto()    # 优化建议，如 "Unused variable"
    INFO = auto()    # 编译过程信息
    WARNING = auto() # 可能的问题，但不影响 AST 生成
    ERROR = auto()   # 语法/语义错误，导致编译失败，但可尝试恢复
    FATAL = auto()   # 内部错误或资源耗尽，必须立即停止

@dataclass
class Location:
    file_path: str
    line: int
    column: int
    length: int = 1
    context_line: Optional[str] = None # 缓存出错行的源码

@runtime_checkable
class Locatable(Protocol):
    """Protocol for objects that have location information."""
    @property
    def line(self) -> int: ...
    # Support both column (Token) and col (Scanner)
    # We can't define OR in Protocol properties easily, 
    # so we just define a marker protocol that we check dynamically or use Union.
    
@dataclass
class Diagnostic:
    severity: Severity
    code: str
    message: str
    location: Optional[Location]
    hint: Optional[str] = None

class CompilerError(Exception):
    """
    Base class for compiler errors.
    Thrown when compilation must be aborted due to errors.
    """
    def __init__(self, diagnostics: List[Diagnostic]):
        self.diagnostics = diagnostics
        super().__init__(f"Compilation failed with {len(diagnostics)} errors.")

class FatalCompilerError(CompilerError):
    """
    Thrown immediately when a FATAL error occurs.
    """
    def __init__(self, diagnostic: Diagnostic):
        super().__init__([diagnostic])
