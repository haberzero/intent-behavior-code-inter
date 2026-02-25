from dataclasses import dataclass
from typing import Optional, Dict, Any
from utils.parser.core.token_stream import TokenStream
from utils.diagnostics.issue_tracker import IssueTracker
from utils.parser.symbol_table import ScopeManager
from utils.parser.resolver.resolver import ModuleResolver
from utils.host_interface import HostInterface

@dataclass
class ParserContext:
    """
    Holds shared state for the parser and its components.
    """
    stream: TokenStream
    issue_tracker: IssueTracker
    scope_manager: Optional[ScopeManager] = None
    module_resolver: Optional[ModuleResolver] = None
    module_cache: Optional[Dict[str, Any]] = None
    host_interface: Optional[HostInterface] = None
    package_name: str = ""
    pending_intent: Optional[str] = None
    
    def __post_init__(self):
        if self.scope_manager is None:
            self.scope_manager = ScopeManager()
        if self.module_cache is None:
            self.module_cache = {}
        if self.host_interface is None:
            self.host_interface = HostInterface()
