from dataclasses import dataclass, field
from typing import Optional, Any, TYPE_CHECKING
from typedef.diagnostic_types import Severity, Location

if TYPE_CHECKING:
    from typedef.lexer_types import Token
    from typedef.parser_types import ASTNode

class IBCBaseException(Exception):
    """Base exception for all IBC-Inter related exceptions."""
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
            loc_str = f" at line {self.location.line}, column {self.location.column}"
            if self.location.file_path:
                loc_str = f" in {self.location.file_path}{loc_str}"
        
        return f"{prefix}{loc_str}: {self.message}"

class LexerError(IBCBaseException):
    def __init__(self, message: str, line: int, column: int, end_line: Optional[int] = None, end_column: Optional[int] = None):
        super().__init__(
            message, 
            Location(line=line, column=column, end_line=end_line, end_column=end_column), 
            severity=Severity.ERROR, 
            error_code="LEXER_ERROR"
        )

class ParserError(IBCBaseException):
    def __init__(self, message: str, token: Optional['Token'] = None):
        loc = None
        if token:
            # Assuming token has line, column, end_line, end_column attributes
            loc = Location(
                line=getattr(token, 'line', 0), 
                column=getattr(token, 'column', 0),
                end_line=getattr(token, 'end_line', None),
                end_column=getattr(token, 'end_column', None)
            )
        super().__init__(
            message, 
            loc, 
            severity=Severity.ERROR, 
            error_code="PARSER_ERROR",
            context_info={'token': token} if token else None
        )
        self.token = token

class InterpreterError(IBCBaseException):
    def __init__(self, message: str, node: Optional['ASTNode'] = None, error_code: Optional[str] = None):
        loc = None
        if node:
            loc = Location(
                file_path=getattr(node, 'file_path', None),
                line=getattr(node, 'lineno', 0),
                column=getattr(node, 'col_offset', 0),
                end_line=getattr(node, 'end_lineno', None),
                end_column=getattr(node, 'end_col_offset', None)
            )
        super().__init__(
            message,
            loc,
            severity=Severity.ERROR,
            error_code=error_code or "RUNTIME_ERROR",
            context_info={'node': node} if node else None
        )
        self.node = node

class SemanticError(IBCBaseException):
    def __init__(self, message: str, node: Optional['ASTNode'] = None):
        loc = None
        if node:
            loc = Location(
                line=getattr(node, 'lineno', 0),
                column=getattr(node, 'col_offset', 0),
                end_line=getattr(node, 'end_lineno', None),
                end_column=getattr(node, 'end_col_offset', None)
            )
        super().__init__(
            message,
            loc,
            severity=Severity.ERROR,
            error_code="SEMANTIC_ERROR",
            context_info={'node': node} if node else None
        )
        self.node = node

class LLMUncertaintyError(InterpreterError):
    """Raised when LLM returns an unparsable or ambiguous value in strict scenes."""
    def __init__(self, message: str, node: Optional['ASTNode'] = None, raw_response: str = ""):
        super().__init__(message, node, error_code="RUN_009") # RUN_LLM_ERROR
        self.raw_response = raw_response
