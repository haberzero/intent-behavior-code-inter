from typing import Protocol, Optional, Any, runtime_checkable, List
from enum import Enum, auto

class DiagnosticSeverity(Enum):
    ERROR = auto()
    WARNING = auto()
    INFO = auto()

@runtime_checkable
class DiagnosticReporter(Protocol):
    """
    Compiler-specific diagnostic reporting interface.
    Abstracts away the foundation's IssueTracker.
    """
    def report(self, message: str, node: Optional[Any] = None, severity: DiagnosticSeverity = DiagnosticSeverity.ERROR):
        ...
    
    def error(self, message: str, node: Optional[Any] = None):
        ...
    
    def warning(self, message: str, node: Optional[Any] = None):
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
