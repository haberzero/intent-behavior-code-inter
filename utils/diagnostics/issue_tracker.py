from typing import List, Optional, Union, Any
from typedef.diagnostic_types import Diagnostic, Severity, Location, CompilerError, FatalCompilerError, Locatable

class IssueTracker:
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
                location: Optional[Union[Locatable, Location]] = None, 
                hint: Optional[str] = None):
        """
        Report a diagnostic.
        Location can be a Token, a Scanner, a Location object, or None.
        It must satisfy Locatable protocol (have line/column or line/col).
        """
        loc = self._resolve_location(location)
        diag = Diagnostic(severity, code, message, loc, hint)
        self.diagnostics.append(diag)
        
        if severity.value >= Severity.ERROR.value:
            self._error_count += 1
            
        if severity == Severity.FATAL:
            raise FatalCompilerError(diag)

    def panic(self, code: str, message: str, location: Optional[Union[Locatable, Location]] = None):
        """Report a FATAL error and stop immediately."""
        self.report(Severity.FATAL, code, message, location)

    def has_errors(self) -> bool:
        return self._error_count > 0

    def check_errors(self):
        """Raise CompilerError if any errors have been reported."""
        if self.has_errors():
            raise CompilerError(self.diagnostics)

    def _resolve_location(self, loc: Optional[Union[Locatable, Location]]) -> Optional[Location]:
        if loc is None:
            return None
        
        if isinstance(loc, Location):
            return loc
            
        # Try to extract line and column
        line = getattr(loc, 'line', None)
        if line is None:
            return None # Can't locate
            
        column = getattr(loc, 'column', None)
        if column is None:
            column = getattr(loc, 'col', None) # Support Scanner
        
        if column is None:
            column = 0 # Default if only line known?
            
        length = 1
        value = getattr(loc, 'value', None)
        if isinstance(value, str):
            length = len(value)
        else:
            length = getattr(loc, 'length', 1)
        
        # Extract context line
        context = None
        if 0 <= line - 1 < len(self._lines):
            context = self._lines[line - 1]
            
        return Location(
            file_path=self.file_path,
            line=line,
            column=column,
            length=length,
            context_line=context
        )
