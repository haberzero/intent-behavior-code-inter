from typing import List, Optional, Union
from typedef.diagnostic_types import Diagnostic, Severity, Location, CompilerError, FatalCompilerError
from typedef.lexer_types import Token

class DiagnosticManager:
    """
    Centralized manager for collecting and reporting compiler diagnostics.
    """
    def __init__(self, source_code: str = "", file_path: str = "<unknown>"):
        self.source_code = source_code
        self.file_path = file_path
        self.diagnostics: List[Diagnostic] = []
        self._error_count = 0
        self._lines = source_code.splitlines()

    def report(self, severity: Severity, code: str, message: str, 
               location: Optional[Union[Token, Location]] = None, 
               hint: Optional[str] = None):
        """
        Report a diagnostic.
        Location can be a Token, a Location object, or None.
        """
        loc = self._resolve_location(location)
        diag = Diagnostic(severity, code, message, loc, hint)
        self.diagnostics.append(diag)
        
        if severity.value >= Severity.ERROR.value:
            self._error_count += 1
            
        if severity == Severity.FATAL:
            raise FatalCompilerError(diag)

    def panic(self, code: str, message: str, location: Optional[Union[Token, Location]] = None):
        """Report a FATAL error and stop immediately."""
        self.report(Severity.FATAL, code, message, location)

    def has_errors(self) -> bool:
        return self._error_count > 0

    def check_errors(self):
        """Raise CompilerError if any errors have been reported."""
        if self.has_errors():
            raise CompilerError(self.diagnostics)

    def _resolve_location(self, loc: Optional[Union[Token, Location]]) -> Optional[Location]:
        if loc is None:
            return None
        
        if isinstance(loc, Location):
            return loc
            
        # Assume it's a Token-like object (has line, column, value/length)
        if hasattr(loc, 'line') and hasattr(loc, 'column'):
            length = 1
            if hasattr(loc, 'value') and isinstance(loc.value, str):
                length = len(loc.value)
            elif hasattr(loc, 'length'):
                length = loc.length
            
            # Extract context line
            context = None
            if 0 <= loc.line - 1 < len(self._lines):
                context = self._lines[loc.line - 1]
                
            return Location(
                file_path=self.file_path,
                line=loc.line,
                column=loc.column,
                length=length,
                context_line=context
            )
        
        return None
