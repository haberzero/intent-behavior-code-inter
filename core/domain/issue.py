from typing import Optional, List, Any, Protocol, runtime_checkable
from dataclasses import dataclass
from .issue_atomic import Severity, Location

# --- 诊断协议 (Protocols) ---

@runtime_checkable
class Locatable(Protocol):
    """具有位置信息的对象协议（如 Token, ASTNode）"""
    @property
    def line(self) -> int: ...
    @property
    def column(self) -> int: ...
    @property
    def length(self) -> int: ...
    @property
    def end_line(self) -> Optional[int]: ...
    @property
    def end_column(self) -> Optional[int]: ...

# --- 诊断实体 (Entities) ---

@dataclass
class Diagnostic:
    """编译器收集的单个诊断信息"""
    severity: Severity
    code: str
    message: str
    location: Optional[Location]
    hint: Optional[str] = None

# --- 基础异常 (Domain Logic) ---

class IBCBaseException(Exception):
    """所有 IBC-Inter 相关异常的基类"""
    def __init__(self, message: str, location: Optional[Location] = None, severity: Severity = Severity.ERROR, error_code: Optional[str] = None, context_info: Optional[dict] = None):
        self.message = message
        self.location = location
        self.severity = severity
        self.error_code = error_code
        self.context_info = context_info or {}
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        prefix = f"[{self.severity.name}]"
        if self.error_code:
            prefix += f"[{self.error_code}]"
        
        loc_str = ""
        if self.location:
            loc_str = f" at {self.location}"
        
        return f"{prefix}{loc_str}: {self.message}"

class LexerError(IBCBaseException):
    def __init__(self, message: str, location: Optional[Location] = None):
        super().__init__(message, location, severity=Severity.ERROR, error_code="LEXER_ERROR")

class ParserError(IBCBaseException):
    def __init__(self, message: str, location: Optional[Location] = None):
        super().__init__(message, location, severity=Severity.ERROR, error_code="PARSER_ERROR")

class InterpreterError(IBCBaseException):
    def __init__(self, message: str, location: Optional[Location] = None, error_code: Optional[str] = None):
        super().__init__(message, location, severity=Severity.ERROR, error_code=error_code or "RUNTIME_ERROR")

class SemanticError(IBCBaseException):
    def __init__(self, message: str, location: Optional[Location] = None):
        super().__init__(message, location, severity=Severity.ERROR, error_code="SEMANTIC_ERROR")

class CompilerError(Exception):
    """
    编译器收集的一组诊断错误。
    当编译因为多个错误必须中止时抛出。
    """
    def __init__(self, diagnostics: List[Diagnostic]):
        self.diagnostics = diagnostics
        super().__init__(f"Compilation failed with {len(diagnostics)} errors.")

class FatalCompilerError(CompilerError):
    """遇到致命错误立即抛出"""
    def __init__(self, diagnostic: Diagnostic):
        super().__init__([diagnostic])

class LLMUncertaintyError(InterpreterError):
    """LLM 在严格模式下返回了无法解析的值"""
    def __init__(self, message: str, location: Optional[Location] = None, raw_response: str = ""):
        super().__init__(message, location, error_code="RUN_009")
        self.raw_response = raw_response

# --- 运行时流控异常 (已迁移) ---
# 已迁移至 core/runtime/exceptions.py，请勿在此处添加
