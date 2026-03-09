from dataclasses import dataclass
from typing import Optional, Dict, Any, TYPE_CHECKING
from core.compiler.parser.core.token_stream import TokenStream
from core.compiler.support.diagnostics import DiagnosticReporter
from core.compiler.parser.resolver.resolver import ModuleResolver
from core.foundation.host_interface import HostInterface

from core.domain import ast as ast

if TYPE_CHECKING:
    from core.compiler.parser.components.expression import ExpressionComponent
    from core.compiler.parser.components.statement import StatementComponent
    from core.compiler.parser.components.declaration import DeclarationComponent
    from core.compiler.parser.components.type_def import TypeComponent
    from core.compiler.parser.components.import_def import ImportComponent

@dataclass
class ParserContext:
    """
    Holds shared state for the parser and its components.
    Now acts as a Mediator for component communication to avoid circular dependencies.
    """
    stream: TokenStream
    issue_tracker: DiagnosticReporter
    module_resolver: Optional[ModuleResolver] = None
    module_cache: Optional[Dict[str, Any]] = None
    host_interface: Optional[HostInterface] = None
    package_name: str = ""
    pending_intent: Optional[ast.IbIntentInfo] = None
    
    # Component references (injected after initialization)
    expression_parser: Optional['ExpressionComponent'] = None
    statement_parser: Optional['StatementComponent'] = None
    declaration_parser: Optional['DeclarationComponent'] = None
    type_parser: Optional['TypeComponent'] = None
    import_parser: Optional['ImportComponent'] = None
    
    def push_intent(self, intent: ast.IbIntentInfo):
        """Set a pending intent comment for the next statement."""
        if self.pending_intent:
             # Already handled by reporting a warning in DeclarationComponent,
             # but we could also do it here if we want to be strict.
             pass
        self.pending_intent = intent
        
    def consume_intent(self) -> Optional[ast.IbIntentInfo]:
        """Consume the pending intent and clear it."""
        intent = self.pending_intent
        self.pending_intent = None
        return intent

    def __post_init__(self):
        if self.module_cache is None:
            self.module_cache = {}
        if self.host_interface is None:
            self.host_interface = HostInterface()
