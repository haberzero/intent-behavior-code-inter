from typing import List, Optional, Union, Any
from core.domain.issue import Diagnostic, Severity, CompilerError, FatalCompilerError, Locatable
from core.domain.issue_atomic import Location
from core.foundation.interfaces import ISourceProvider

class IssueTracker:
    """
    Centralized manager for collecting and reporting compiler diagnostics.
    """
    def __init__(self, file_path: str = "<unknown>", source_provider: Optional[ISourceProvider] = None):
        self.file_path = file_path
        self.source_provider = source_provider
        self._diagnostics: List[Diagnostic] = []
        self._error_count = 0

    @property
    def diagnostics(self) -> List[Diagnostic]:
        return self._diagnostics

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self._diagnostics if d.severity == Severity.WARNING)

    @property
    def total_count(self) -> int:
        return len(self._diagnostics)

    def report(self, severity: Severity, code: str, message: str, 
                location: Optional[Union[Locatable, Location]] = None, 
                hint: Optional[str] = None):
        """
        Report a diagnostic.
        Location can be a Token, a Scanner, a Location object, or None.
        It must satisfy Locatable protocol (have line/column).
        """
        diag = Diagnostic(severity, code, message, self._resolve_location(location), hint)
        self._diagnostics.append(diag)
        
        if severity.value >= Severity.ERROR.value:
            self._error_count += 1
            
        if severity == Severity.FATAL:
            raise FatalCompilerError(diag)

    def error(self, message: str, location: Optional[Any] = None, code: str = "COMPILER_ERROR", hint: Optional[str] = None):
        self.report(Severity.ERROR, code, message, location, hint)

    def warning(self, message: str, location: Optional[Any] = None, code: str = "COMPILER_WARNING", hint: Optional[str] = None):
        self.report(Severity.WARNING, code, message, location, hint)

    def hint(self, message: str, location: Optional[Any] = None, code: str = "COMPILER_HINT"):
        self.report(Severity.HINT, code, message, location)

    def panic(self, message: str, location: Optional[Any] = None, code: str = "FATAL_ERROR"):
        self.report(Severity.FATAL, code, message, location)

    def has_errors(self) -> bool:
        return self._error_count > 0

    def clear(self):
        """Clear all diagnostics."""
        self._diagnostics = []
        self._error_count = 0

    def check_errors(self):
        """Raise CompilerError if any errors have been reported."""
        if self.has_errors():
            raise CompilerError(self._diagnostics)

    def merge(self, other: 'IssueTracker'):
        """Merge diagnostics from another tracker."""
        self._diagnostics.extend(other.diagnostics)
        self._error_count += other._error_count

    def _resolve_location(self, loc: Optional[Union[Locatable, Location]]) -> Optional[Location]:
        if loc is None:
            return None
        
        resolved_loc = None
        if isinstance(loc, Location):
            if not loc.file_path or loc.file_path == "<unknown>":
                # Create copy with our file path
                resolved_loc = Location(
                    file_path=self.file_path,
                    line=loc.line,
                    column=loc.column,
                    length=loc.length,
                    end_line=loc.end_line,
                    end_column=loc.end_column,
                    context_line=loc.context_line
                )
            else:
                resolved_loc = loc
            
        elif isinstance(loc, Locatable):
            # Use standard Locatable protocol
            resolved_loc = Location(
                file_path=self.file_path,
                line=loc.line,
                column=loc.column,
                length=loc.length,
                end_line=loc.end_line,
                end_column=loc.end_column
            )
        
        # [Active Defense] 自动注入源码片段实现“无盘化”诊断
        if resolved_loc and not resolved_loc.context_line and self.source_provider:
            resolved_loc.context_line = self.source_provider.get_line(resolved_loc.file_path, resolved_loc.line)
            
        return resolved_loc
