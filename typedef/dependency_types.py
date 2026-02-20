
from dataclasses import dataclass, field
from typing import List, Set, Optional, Dict
from enum import Enum, auto

class ImportType(Enum):
    IMPORT = auto()      # import module
    FROM_IMPORT = auto() # from module import name

@dataclass
class ImportInfo:
    """Represents a single import statement."""
    module_name: str # The module being imported (e.g. "utils.math")
    file_path: Optional[str] = None # Resolved absolute file path
    lineno: int = 0
    import_type: ImportType = ImportType.IMPORT

@dataclass
class ModuleInfo:
    """Represents a source file and its dependencies."""
    file_path: str
    imports: List[ImportInfo] = field(default_factory=list)
    content: Optional[str] = None # Source code content (cached)

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
