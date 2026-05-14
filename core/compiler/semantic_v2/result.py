"""
Diagnostic and Result Types

Implements the "errors as data" pattern where diagnostics are first-class
values that flow through the pipeline rather than being thrown as exceptions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Any, Dict
from core.kernel import ast as ibci_ast


class DiagnosticLevel(Enum):
    """Diagnostic severity levels"""
    ERROR = "error"       # Prevents code generation
    WARNING = "warning"   # Code may run but has issues
    INFO = "info"         # Informational message
    HINT = "hint"         # Suggestion for improvement


@dataclass
class Diagnostic:
    """
    A single diagnostic message (error, warning, etc.).

    Design decisions:
    - Immutable (frozen=True)
    - Contains all information needed for display
    - Can be serialized for IDE integration
    """
    level: DiagnosticLevel
    message: str
    code: str  # e.g., "SEM_003"
    node_uid: Optional[str] = None
    file_path: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    hint: Optional[str] = None
    related: List['Diagnostic'] = field(default_factory=list)

    @classmethod
    def error(cls, message: str, code: str = "SEM_000", **kwargs) -> 'Diagnostic':
        """Create an error diagnostic"""
        return cls(level=DiagnosticLevel.ERROR, message=message, code=code, **kwargs)

    @classmethod
    def warning(cls, message: str, code: str = "SEM_000", **kwargs) -> 'Diagnostic':
        """Create a warning diagnostic"""
        return cls(level=DiagnosticLevel.WARNING, message=message, code=code, **kwargs)

    @classmethod
    def info(cls, message: str, code: str = "SEM_000", **kwargs) -> 'Diagnostic':
        """Create an info diagnostic"""
        return cls(level=DiagnosticLevel.INFO, message=message, code=code, **kwargs)

    @classmethod
    def from_exception(cls, exc: Exception, node_uid: Optional[str] = None) -> 'Diagnostic':
        """Create an error diagnostic from an exception"""
        return cls(
            level=DiagnosticLevel.ERROR,
            message=str(exc),
            code="SEM_999",
            node_uid=node_uid,
            hint=f"Exception: {exc.__class__.__name__}"
        )

    def is_error(self) -> bool:
        return self.level == DiagnosticLevel.ERROR

    def is_warning(self) -> bool:
        return self.level == DiagnosticLevel.WARNING

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'level': self.level.value,
            'message': self.message,
            'code': self.code,
            'node_uid': self.node_uid,
            'file_path': self.file_path,
            'line': self.line,
            'column': self.column,
            'hint': self.hint,
        }


@dataclass
class PassResult:
    """
    Result of executing a semantic analysis pass.

    Design: Functional programming pattern - passes don't mutate state,
    they return new contexts and accumulated diagnostics.

    Key insight from V1 limitations:
    - V1 throws exceptions on errors, losing subsequent analysis
    - V2 collects all diagnostics, enables reporting all issues at once
    """
    context: 'SemanticContext'  # Updated context (may be the same if pass failed)
    metadata: Dict[str, Any]    # Pass-specific metadata (e.g., collected symbols)
    diagnostics: List[Diagnostic]
    success: bool
    pass_name: str = "unknown"

    @classmethod
    def ok(cls, context: 'SemanticContext', metadata: Optional[Dict[str, Any]] = None,
           diagnostics: Optional[List[Diagnostic]] = None, pass_name: str = "unknown") -> 'PassResult':
        """Create a successful result"""
        return cls(
            context=context,
            metadata=metadata or {},
            diagnostics=diagnostics or [],
            success=True,
            pass_name=pass_name
        )

    @classmethod
    def fail(cls, context: 'SemanticContext', diagnostic: Diagnostic,
             metadata: Optional[Dict[str, Any]] = None, pass_name: str = "unknown") -> 'PassResult':
        """Create a failed result"""
        return cls(
            context=context,
            metadata=metadata or {},
            diagnostics=[diagnostic],
            success=False,
            pass_name=pass_name
        )

    def has_errors(self) -> bool:
        """Check if result contains any errors"""
        return any(d.is_error() for d in self.diagnostics)

    def has_warnings(self) -> bool:
        """Check if result contains any warnings"""
        return any(d.is_warning() for d in self.diagnostics)

    def add_diagnostic(self, diagnostic: Diagnostic) -> 'PassResult':
        """Add a diagnostic to this result (returns new result)"""
        from dataclasses import replace
        new_diagnostics = self.diagnostics + [diagnostic]
        return replace(
            self,
            diagnostics=new_diagnostics,
            success=self.success and not diagnostic.is_error()
        )

    def merge(self, other: 'PassResult') -> 'PassResult':
        """Merge two results (for combining parallel analyses)"""
        from dataclasses import replace
        return replace(
            self,
            metadata={**self.metadata, **other.metadata},
            diagnostics=self.diagnostics + other.diagnostics,
            success=self.success and other.success
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'pass_name': self.pass_name,
            'success': self.success,
            'diagnostics': [d.to_dict() for d in self.diagnostics],
            'metadata_keys': list(self.metadata.keys()),
        }
