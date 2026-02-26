from typing import List, Optional, Union, Any
from core.types.diagnostic_types import Diagnostic, Severity, Location, CompilerError, FatalCompilerError, Locatable

class IssueTracker:
    """
    Centralized manager for collecting and reporting compiler diagnostics.
    """
    def __init__(self, file_path: str = "<unknown>"):
        self.file_path = file_path
        self.diagnostics: List[Diagnostic] = []
        self._error_count = 0

    def report(self, severity: Severity, code: str, message: str, 
                location: Optional[Union[Locatable, Location]] = None, 
                hint: Optional[str] = None):
        """
        Report a diagnostic.
        Location can be a Token, a Scanner, a Location object, or None.
        It must satisfy Locatable protocol (have line/column or line/col).
        """
        diag = Diagnostic(severity, code, message, self._resolve_location(location), hint)
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

    def clear(self):
        """Clear all diagnostics."""
        self.diagnostics = []
        self._error_count = 0

    def check_errors(self):
        """Raise CompilerError if any errors have been reported."""
        if self.has_errors():
            # If we raise here, we should pass diagnostics?
            # CompilerError usually takes message or list of diagnostics.
            # In other parts of code: raise CompilerError(self.diagnostics)
            # Or raise CompilerError("Compilation failed")
            # Let's check typedef/diagnostic_types.py
            # But here we just raise.
            raise CompilerError(self.diagnostics)

    def merge(self, other: 'IssueTracker'):
        """Merge diagnostics from another tracker."""
        self.diagnostics.extend(other.diagnostics)
        self._error_count += other._error_count

    def _resolve_location(self, loc: Optional[Union[Locatable, Location]]) -> Optional[Location]:
        if loc is None:
            return None
        
        if isinstance(loc, Location):
            # If the location already has a file path, keep it.
            # If it doesn't (or is unknown), use ours?
            # Usually Lexer produces tokens with line/col but no file path.
            # Parser produces AST nodes with line/col but no file path.
            # So when we report using a Token/ASTNode, we need to inject self.file_path.
            # But if loc is already a Location object (e.g. from DependencyScanner), it has file_path.
            if not loc.file_path or loc.file_path == "<unknown>":
                # Create copy with our file path
                return Location(
                    file_path=self.file_path,
                    line=loc.line,
                    column=loc.column,
                    length=loc.length,
                    context_line=loc.context_line
                )
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
            
        return Location(
            file_path=self.file_path,
            line=line,
            column=column,
            length=length,
            context_line=context
        )
