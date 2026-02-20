
import os
import re
from typing import Dict, List, Optional, Set
from typedef.dependency_types import (
    ImportInfo, ModuleInfo, ImportType, 
    DependencyError, ModuleNotFoundError, CircularDependencyError
)

class DependencyScanner:
    """
    Scans source files for import statements and resolves file paths.
    """
    
    # Simple regex for finding imports (faster than full lexing)
    # Supports:
    #   import foo
    #   import foo.bar
    #   from foo import bar
    #   from .foo import bar
    #   from ..foo import bar
    IMPORT_REGEX = re.compile(r'^\s*(?:import\s+([\w.]+)|from\s+([\w.]+)\s+import\s+)', re.MULTILINE)
    
    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        self.modules: Dict[str, ModuleInfo] = {} # Key: Absolute file path
        
    def scan_file(self, file_path: str) -> ModuleInfo:
        """
        Scans a single file for imports. Does NOT recurse yet.
        """
        abs_path = os.path.abspath(file_path)
        if abs_path in self.modules:
            return self.modules[abs_path]
            
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            raise ModuleNotFoundError(file_path, "Root")
            
        imports = []
        for line_idx, line in enumerate(content.splitlines()):
            # Basic comment filtering
            if line.strip().startswith('#'):
                continue
                
            match = self.IMPORT_REGEX.match(line)
            if match:
                # Group 1: 'import X'
                # Group 2: 'from X import Y'
                module_name = match.group(1) or match.group(2)
                if module_name:
                    info = ImportInfo(
                        module_name=module_name,
                        lineno=line_idx + 1,
                        import_type=ImportType.IMPORT if match.group(1) else ImportType.FROM_IMPORT
                    )
                    imports.append(info)
                    
        mod_info = ModuleInfo(file_path=abs_path, imports=imports, content=content)
        self.modules[abs_path] = mod_info
        return mod_info

    def resolve_path(self, module_name: str, importer_path: str) -> str:
        """
        Resolves a module name (e.g., 'utils.math') to an absolute file path.
        Rules:
        1. Relative imports (future): currently assumes absolute from root.
        2. Tries appending '.ibc' (or whatever extension, let's assume no extension in import).
        3. Checks file existence.
        """
        # Convert dots to slashes
        rel_path = module_name.replace('.', os.sep)
        
        # Strategy 1: Look in project root
        candidate = os.path.join(self.root_dir, rel_path)
        
        # Check for file (e.g. utils/math.ibc or utils/math.py if we support that)
        # Assuming our source extension is .ibc (or empty for now, based on tests)
        # Let's assume .ibc for now, or check exact match if provided
        
        # Priority:
        # 1. exact match (if has extension)
        # 2. .ibci
        # 3. .py (for python interop?)
        
        extensions = ['.ibci', '.py', '']
        
        for ext in extensions:
            path = candidate + ext
            if os.path.isfile(path):
                return path
                
            # Check for package (init file)
            # path/result/__init__.ibci
            init_path = os.path.join(candidate, '__init__' + ext)
            if os.path.isfile(init_path):
                return init_path
                
        raise ModuleNotFoundError(module_name, importer_path)

    def scan_dependencies(self, entry_file: str) -> Dict[str, ModuleInfo]:
        """
        Recursively scans all dependencies starting from entry_file.
        Returns a map of all scanned modules.
        """
        entry_file = os.path.abspath(entry_file)
        visited = set()
        queue = [entry_file]
        
        while queue:
            current_path = queue.pop(0)
            if current_path in visited:
                continue
            
            # Note: We don't add to visited here because we want to allow re-visiting 
            # if we encounter it from another path? No, standard BFS/DFS is fine.
            # But we must ensure scan_file is called only once per file.
            # scan_file already checks self.modules cache.
            
            visited.add(current_path)
            
            try:
                mod_info = self.scan_file(current_path)
            except ModuleNotFoundError:
                if current_path == entry_file:
                    raise ModuleNotFoundError(current_path, "Root")
                else:
                    # This branch might be unreachable if resolution logic is correct
                    continue
                
            for imp in mod_info.imports:
                try:
                    resolved_path = self.resolve_path(imp.module_name, current_path)
                    imp.file_path = resolved_path
                    if resolved_path not in visited and resolved_path not in queue:
                        queue.append(resolved_path)
                except ModuleNotFoundError:
                    # Depending on strictness, we might raise or warn
                    # For now, raise strictly
                    raise ModuleNotFoundError(imp.module_name, current_path)
                    
        return self.modules
