from typing import Protocol, Optional, Any, runtime_checkable, List
from core.base.source_atomic import Location, Severity

@runtime_checkable
class DiagnosticReporter(Protocol):
    def report(self, severity: Severity, code: str, message: str, location: Optional[Any] = None, hint: Optional[str] = None):
        ...

    def error(self, message: str, location: Optional[Any] = None, code: str = "COMPILER_ERROR", hint: Optional[str] = None):
        ...

    def warning(self, message: str, location: Optional[Any] = None, code: str = "COMPILER_WARNING", hint: Optional[str] = None):
        ...

    def hint(self, message: str, location: Optional[Any] = None, code: str = "COMPILER_HINT"):
        ...

    def panic(self, message: str, location: Optional[Any] = None, code: str = "FATAL_ERROR"):
        ...

    def check_errors(self):
        ...

    def clear(self):
        ...

    def has_errors(self) -> bool:
        ...

    def merge(self, other: 'DiagnosticReporter'):
        ...

    @property
    def diagnostics(self) -> List[Any]:
        ...