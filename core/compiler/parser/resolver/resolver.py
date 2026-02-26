import os
from typing import Optional

class ModuleResolveError(Exception):
    def __init__(self, module_name: str, importer_path: Optional[str] = None):
        msg = f"Cannot resolve module '{module_name}'"
        if importer_path:
            msg += f" from '{importer_path}'"
        super().__init__(msg)
        self.module_name = module_name
        self.importer_path = importer_path

class ModuleResolver:
    """
    Resolves module names (e.g., 'utils.math' or '..calc') to absolute file paths.
    Acts as the Single Source of Truth for path resolution.
    """
    def __init__(self, root_dir: str):
        self.root_dir = os.path.realpath(root_dir)
        # Extensions to probe, in order of preference
        self.extensions = ['.ibci', '.py', '']

    def _check_path_security(self, path: str):
        """
        Ensure the path is within the project root directory.
        Prevents Path Traversal attacks.
        """
        # Resolve symlinks to ensure we are checking the real location
        abs_path = os.path.realpath(path)
        abs_root = self.root_dir # Already realpath
        
        # Use commonpath to correctly handle path separators and subdirectories
        try:
            common = os.path.commonpath([abs_root, abs_path])
        except ValueError:
            # Can happen on Windows if paths are on different drives
            raise ModuleResolveError(f"Path '{path}' is on a different drive than root '{self.root_dir}'")
            
        if common != abs_root:
            raise ModuleResolveError(f"Security Error: Path '{path}' resolves to '{abs_path}' which is outside project root '{self.root_dir}'")

    def _get_candidate_path(self, module_name: str, context_file: Optional[str] = None) -> str:
        """Helper to calculate candidate path without probing."""
        is_relative = module_name.startswith('.')
        
        candidate_path: str
        
        if is_relative:
            if not context_file:
                raise ModuleResolveError(module_name, None)
                
            # Count leading dots
            level = 0
            for char in module_name:
                if char == '.':
                    level += 1
                else:
                    break
            
            # module_name: ..math -> level=2, suffix=math
            suffix = module_name[level:]
            
            # Start from the directory containing the importer file
            current_dir = os.path.dirname(os.path.abspath(context_file))
            
            # Go up (level - 1) times
            base_dir = current_dir
            for _ in range(level - 1):
                base_dir = os.path.dirname(base_dir)
                
            # Construct relative path
            if suffix:
                rel_path = suffix.replace('.', os.sep)
                candidate_path = os.path.join(base_dir, rel_path)
            else:
                # Import is just '..', e.g. from .. import X -> importing form __init__ of parent
                candidate_path = base_dir
                
        else:
            # Absolute import (from root)
            rel_path = module_name.replace('.', os.sep)
            candidate_path = os.path.join(self.root_dir, rel_path)
            
        # Security Check
        self._check_path_security(candidate_path)
            
        return candidate_path

    def resolve(self, module_name: str, context_file: Optional[str] = None) -> str:
        """
        Resolve a module name to an absolute file path.
        
        Args:
            module_name: The module name (e.g., 'pkg.mod' or '..mod').
            context_file: The absolute path of the file importing the module (required for relative imports).
            
        Returns:
            The absolute path to the resolved file.
            
        Raises:
            ModuleResolveError: If the module cannot be found.
        """
        candidate_path = self._get_candidate_path(module_name, context_file)
        
        # Check for file existence
        resolved = self._probe_file(candidate_path)
        if resolved:
            return resolved
            
        raise ModuleResolveError(module_name, context_file)

    def is_package_dir(self, module_name: str, context_file: Optional[str] = None) -> bool:
        """Check if the module name resolves to an existing directory (namespace package)."""
        try:
            candidate_path = self._get_candidate_path(module_name, context_file)
            return os.path.isdir(candidate_path)
        except Exception:
            return False

    def _probe_file(self, base_path: str) -> Optional[str]:
        """Check for file existence with various extensions and package inits."""
        # 1. Check direct file: path.ibci
        for ext in self.extensions:
            path = base_path + ext
            if os.path.isfile(path):
                return path
                
        # 2. Check package init: path/__init__.ibci
        for ext in self.extensions:
            init_path = os.path.join(base_path, '__init__' + ext)
            if os.path.isfile(init_path):
                return init_path
                
        return None
