from typing import Optional, Any, Union, List
from .diagnostics import DiagnosticReporter, DiagnosticSeverity
from core.support.diagnostics.issue_tracker import IssueTracker
from core.domain.diagnostics import Severity

class IssueTrackerAdapter(DiagnosticReporter):
    """
    Adapts the foundation's IssueTracker to the compiler's DiagnosticReporter interface.
    """
    def __init__(self, tracker: IssueTracker):
        self.tracker = tracker

    def _map_severity(self, severity: DiagnosticSeverity) -> Severity:
        if severity == DiagnosticSeverity.ERROR:
            return Severity.ERROR
        if severity == DiagnosticSeverity.WARNING:
            return Severity.WARNING
        if severity == DiagnosticSeverity.INFO:
            return Severity.INFO
        return Severity.ERROR

    def report(self, message: str, node: Optional[Any] = None, severity: DiagnosticSeverity = DiagnosticSeverity.ERROR):
        self.tracker.report(
            severity=self._map_severity(severity),
            code="COMPILER_ISSUE", # Default code for adapted reports
            message=message,
            location=node
        )

    def error(self, message: str, node: Optional[Any] = None):
        self.report(message, node, DiagnosticSeverity.ERROR)

    def warning(self, message: str, node: Optional[Any] = None):
        self.report(message, node, DiagnosticSeverity.WARNING)

    def check_errors(self):
        self.tracker.check_errors()

    def clear(self):
        self.tracker.clear()

    def has_errors(self) -> bool:
        return self.tracker.has_errors()

    def merge(self, other: 'DiagnosticReporter'):
        if isinstance(other, IssueTrackerAdapter):
            self.tracker.merge(other.tracker)
        else:
            # Fallback for generic reporters: manually copy diagnostics
            for diag in other.diagnostics:
                self.tracker.diagnostics.append(diag)

    @property
    def diagnostics(self) -> List[Any]:
        return self.tracker.diagnostics

def wrap_tracker(tracker: Optional[Union[IssueTracker, DiagnosticReporter]]) -> DiagnosticReporter:
    """Ensures we have a DiagnosticReporter."""
    if tracker is None:
        return IssueTrackerAdapter(IssueTracker())
    if isinstance(tracker, DiagnosticReporter):
        return tracker
    return IssueTrackerAdapter(tracker)
