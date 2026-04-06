from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from core.compiler.parser.core.token_stream import TokenStream
from core.compiler.common.diagnostics import DiagnosticReporter
from core.compiler.parser.resolver.resolver import ModuleResolver
from core.runtime.host.host_interface import HostInterface

from core.kernel import ast as ast

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
    metadata: Optional[Any] = None # MetadataRegistry
    package_name: str = ""
    pending_intents: List[ast.IbIntentInfo] = field(default_factory=list)
    
    # Component references (injected after initialization)
    expression_parser: Optional['ExpressionComponent'] = None
    statement_parser: Optional['StatementComponent'] = None
    declaration_parser: Optional['DeclarationComponent'] = None
    type_parser: Optional['TypeComponent'] = None
    import_parser: Optional['ImportComponent'] = None
    
    def push_intent(self, intent: ast.IbIntentInfo):
        """Add a pending intent comment for the next statement."""
        self.pending_intents.append(intent)
        
    def consume_intents(self) -> List[ast.IbIntentInfo]:
        """Consume all pending intents and clear the list."""
        intents = self.pending_intents
        self.pending_intents = []
        return intents

    def __post_init__(self):
        if self.module_cache is None:
            self.module_cache = {}
        if self.host_interface is None:
            self.host_interface = HostInterface()
            
        # 自动从宿主接口提取元数据注册表
        if self.metadata is None and self.host_interface:
            self.metadata = self.host_interface.metadata
