from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum, auto

class Severity(Enum):
    ERROR = auto()
    WARNING = auto()
    INFO = auto()

@dataclass
class Location:
    line: int
    column: int
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    file_path: Optional[str] = None

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
    def __init__(self, message: str, token: Any = None):
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
