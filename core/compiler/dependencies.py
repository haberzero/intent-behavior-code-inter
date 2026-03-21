
from dataclasses import dataclass, field
from typing import List, Set, Optional, Dict, Any
from enum import Enum, auto
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger

class ImportType(Enum):
    IMPORT = auto()      # import module
    FROM_IMPORT = auto() # from module import name

class ModuleStatus(Enum):
    PENDING = auto()
    SUCCESS = auto()
    COMPILED = auto()
    FAILED = auto()

@dataclass
class ImportInfo:
    """Represents a single import statement."""
    module_name: str # The module being imported (e.g. "utils.math")
    file_path: Optional[str] = None # Resolved absolute file path
    lineno: int = 0
    import_type: ImportType = ImportType.IMPORT
    level: int = 0 # Level for relative imports (0 = absolute)
    names: List[Any] = field(default_factory=list) # List of IbAlias nodes

@dataclass
class ModuleInfo:
    """Represents a source file and its dependencies."""
    file_path: str
    imports: List[ImportInfo] = field(default_factory=list)
    content: Optional[str] = None # Source code content (cached)
    mtime: float = 0.0 # Modification time
    status: ModuleStatus = ModuleStatus.PENDING

class DependencyError(Exception):
    """Base class for dependency resolution errors."""
    pass

class CircularDependencyError(DependencyError):
    """Raised when circular import is detected."""
    def __init__(self, cycle: List[str]):
        self.cycle = cycle
        msg = "Circular dependency detected: " + " -> ".join(cycle)
        super().__init__(msg)

class ModuleNotFoundError(DependencyError):
    """Raised when an imported module cannot be found."""
    def __init__(self, module_name: str, importer: str):
        self.module_name = module_name
        self.importer = importer
        super().__init__(f"Module '{module_name}' not found (imported by {importer})")

class DependencyGraph:
    """
    Analyzes dependency graph for cycles and compilation order.
    """
    def __init__(self, modules: Dict[str, ModuleInfo], debugger: Optional[Any] = None):
        self.modules = modules
        self.adj_list: Dict[str, List[str]] = {}
        self.debugger = debugger or core_debugger
        self._build_graph()

        
    def _build_graph(self):
        for path, info in self.modules.items():
            self.adj_list[path] = []
            for imp in info.imports:
                if imp.file_path and imp.file_path in self.modules:
                    self.adj_list[path].append(imp.file_path)
                    
    def check_cycles(self):
        """
        Detects circular dependencies using DFS.
        Raises CircularDependencyError if cycle found.
        """
        visited = set()
        recursion_stack = set()
        
        # Track path for error reporting
        
        def dfs(node: str, current_path: List[str]):
            visited.add(node)
            recursion_stack.add(node)
            current_path.append(node)
            
            # Use self.modules to get imports
            
            if node in self.adj_list:
                for neighbor in self.adj_list[node]:
                    if neighbor not in visited:
                        dfs(neighbor, current_path)
                    elif neighbor in recursion_stack:
                        # Cycle detected!
                        # Extract the cycle part from current_path
                        # neighbor is the start of the cycle
                        try:
                            idx = current_path.index(neighbor)
                            cycle = current_path[idx:] + [neighbor]
                        except ValueError:
                            cycle = [neighbor, node, neighbor]
                            
                        raise CircularDependencyError(cycle)
                        
            recursion_stack.remove(node)
            current_path.pop()
            
        # We must iterate over all nodes because the graph might be disconnected
        for node in list(self.adj_list.keys()):
            if node not in visited:
                dfs(node, [])

    def get_compilation_order(self) -> List[str]:
        """
        Returns a list of file paths to compile.
        If there are no cycles, this is a topological sort (dependencies first).
        If there are cycles, it returns a best-effort order.
        """
        # [MOD] 允许循环引用，不再强制报错。
        # 运行时由 ModuleManager 的缓存机制处理循环加载。
        try:
            self.check_cycles()
        except CircularDependencyError as e:
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Note: Circular dependency detected (allowed): {e}")
        
        visited = set()
        order = []
        
        def dfs(node: str):
            visited.add(node)
            for neighbor in self.adj_list.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
            order.append(node)
        
        for node in self.adj_list:
            if node not in visited:
                dfs(node)
                
        return order
