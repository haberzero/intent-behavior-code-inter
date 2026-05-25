"""
Diagnostic and Result Types

Implements the "errors as data" pattern where diagnostics are first-class
values that flow through the pipeline rather than being thrown as exceptions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Any, Dict, Set


class DiagnosticLevel(Enum):
    """Diagnostic severity levels"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


@dataclass
class Diagnostic:
    """A single diagnostic message."""
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
        return cls(level=DiagnosticLevel.ERROR, message=message, code=code, **kwargs)

    @classmethod
    def warning(cls, message: str, code: str = "SEM_000", **kwargs) -> 'Diagnostic':
        return cls(level=DiagnosticLevel.WARNING, message=message, code=code, **kwargs)

    @classmethod
    def info(cls, message: str, code: str = "SEM_000", **kwargs) -> 'Diagnostic':
        return cls(level=DiagnosticLevel.INFO, message=message, code=code, **kwargs)

    @classmethod
    def from_exception(cls, exc: Exception, node_uid: Optional[str] = None) -> 'Diagnostic':
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


@dataclass(frozen=True)
class PassOutput:
    """Immutable output produced by a single Phase.

    Each Phase collects its bindings into a PassOutput. The Pipeline
    merges all PassOutputs into the final MetadataStore without ever
    mutating shared state during analysis.
    """
    symbol_bindings: Dict[Any, Any] = field(default_factory=dict)
    type_bindings: Dict[Any, Any] = field(default_factory=dict)
    location_bindings: Dict[Any, Any] = field(default_factory=dict)
    cell_captured_symbols: Set[str] = field(default_factory=set)
    diagnostics: List[Diagnostic] = field(default_factory=list)
    success: bool = True

    def has_errors(self) -> bool:
        return any(d.is_error() for d in self.diagnostics)


@dataclass
class PassResult:
    """Result of executing a semantic analysis pass.

    Carries the (possibly updated) context and a PassOutput with
    the bindings produced by that pass.
    """
    context: 'SemanticContext'
    output: PassOutput
    pass_name: str = "unknown"

    # Legacy fields kept for internal Phase sub-step coordination
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def diagnostics(self) -> List[Diagnostic]:
        return self.output.diagnostics

    @property
    def success(self) -> bool:
        return self.output.success

    @classmethod
    def ok(cls, context: 'SemanticContext',
           output: Optional[PassOutput] = None,
           diagnostics: Optional[List[Diagnostic]] = None,
           metadata: Optional[Dict[str, Any]] = None,
           pass_name: str = "unknown") -> 'PassResult':
        """Create a successful result."""
        if output is None:
            output = PassOutput(diagnostics=diagnostics or [], success=True)
        return cls(
            context=context,
            output=output,
            metadata=metadata or {},
            pass_name=pass_name
        )

    @classmethod
    def fail(cls, context: 'SemanticContext', diagnostic: Diagnostic,
             metadata: Optional[Dict[str, Any]] = None,
             pass_name: str = "unknown") -> 'PassResult':
        """Create a failed result."""
        output = PassOutput(diagnostics=[diagnostic], success=False)
        return cls(
            context=context,
            output=output,
            metadata=metadata or {},
            pass_name=pass_name
        )

    def has_errors(self) -> bool:
        return self.output.has_errors()

    def has_warnings(self) -> bool:
        return any(d.is_warning() for d in self.output.diagnostics)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'pass_name': self.pass_name,
            'success': self.success,
            'diagnostics': [d.to_dict() for d in self.diagnostics],
        }
