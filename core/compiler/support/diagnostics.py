from typing import Protocol, Optional, Any, runtime_checkable, List
from core.domain.issue_atomic import Severity

@runtime_checkable
class DiagnosticReporter(Protocol):
    """
    Compiler-specific diagnostic reporting interface.
    Abstracts away the foundation's IssueTracker.
    Now directly uses Domain Severity and supports Error Codes.
    """
    def report(self, severity: Severity, code: str, message: str, node: Optional[Any] = None, hint: Optional[str] = None):
        ...
    
    def error(self, message: str, node: Optional[Any] = None, code: str = "COMPILER_ERROR", hint: Optional[str] = None):
        ...
    
    def warning(self, message: str, node: Optional[Any] = None, code: str = "COMPILER_WARNING", hint: Optional[str] = None):
        ...

    def hint(self, message: str, node: Optional[Any] = None, code: str = "COMPILER_HINT"):
        ...

    def panic(self, message: str, node: Optional[Any] = None, code: str = "FATAL_ERROR"):
        ...
    
    def check_errors(self):
        """Should raise an exception if fatal errors were reported."""
        ...

    def clear(self):
        """Clears all reported issues."""
        ...

    def has_errors(self) -> bool:
        """Returns True if any errors were reported."""
        ...

    def merge(self, other: 'DiagnosticReporter'):
        """Merges another reporter's diagnostics into this one."""
        ...

    @property
    def diagnostics(self) -> List[Any]:
        """Returns the list of all reported diagnostics."""
        ...
