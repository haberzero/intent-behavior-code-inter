
from typing import Dict, List, Set, Optional
from typedef.dependency_types import ModuleInfo, CircularDependencyError

class DependencyGraph:
    """
    Analyzes dependency graph for cycles and compilation order.
    """
    def __init__(self, modules: Dict[str, ModuleInfo]):
        self.modules = modules
        self.adj_list: Dict[str, List[str]] = {}
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
        Returns a topologically sorted list of file paths.
        Dependency-free modules come first.
        """
        self.check_cycles() # Ensure no cycles first
        
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
                
        # The dfs order adds a node AFTER its children are visited.
        # This results in a topological sort where dependencies come first.
        return order
