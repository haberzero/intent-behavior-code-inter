
import os
from typing import Dict, List, Optional
from typedef.dependency_types import (
    ImportInfo, ModuleInfo, ImportType
)
from utils.diagnostics.issue_tracker import IssueTracker
from typedef.diagnostic_types import Severity, Location
from utils.diagnostics.codes import DEP_FILE_NOT_FOUND, DEP_MODULE_NOT_FOUND, DEP_INVALID_IMPORT_POSITION
from utils.lexer.lexer import Lexer
from typedef.lexer_types import TokenType, Token

class DependencyScanner:
    """
    Scans source files for import statements and resolves file paths.
    """
    
    def __init__(self, root_dir: str, issue_tracker: Optional[IssueTracker] = None):
        self.root_dir = os.path.abspath(root_dir)
        self.issue_tracker = issue_tracker or IssueTracker()
        self.modules: Dict[str, ModuleInfo] = {} # Key: Absolute file path
        
    def scan_file(self, file_path: str) -> Optional[ModuleInfo]:
        """
        Scans a single file for imports using Lexer logic (but simplified).
        """
        abs_path = os.path.abspath(file_path)
        if abs_path in self.modules:
            return self.modules[abs_path]
            
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            self.issue_tracker.report(Severity.ERROR, DEP_FILE_NOT_FOUND, f"File not found: {file_path}")
            return None
            
        # Get mtime
        try:
            mtime = os.path.getmtime(abs_path)
        except OSError:
            mtime = 0.0
            
        imports = []
        
        # Use Lexer to tokenize
        # We need a fresh issue tracker for lexer to avoid polluting global tracker with lex errors
        # (We only care about imports here)
        lexer_tracker = IssueTracker()
        lexer = Lexer(content, lexer_tracker)
        tokens = lexer.tokenize()
        
        # Scan tokens for import statements
        i = 0
        n = len(tokens)
        imports_allowed = True
        
        while i < n:
            token = tokens[i]
            
            # Skip newlines at start
            if token.type == TokenType.NEWLINE:
                i += 1
                continue
                
            if token.type == TokenType.EOF:
                break
            
            # Skip Dedent/Indent if they appear (shouldn't at top level before imports)
            if token.type in (TokenType.INDENT, TokenType.DEDENT):
                i += 1
                continue
                
            is_import = False
            
            if token.type == TokenType.IMPORT:
                # import X
                # import X as Y
                # import X.Y
                if not imports_allowed:
                    self._report_invalid_pos(file_path, token)
                    # Skip to next newline
                    while i < n and tokens[i].type != TokenType.NEWLINE:
                        i += 1
                    continue
                    
                is_import = True
                i += 1 # consume import
                
                # Parse module names (comma separated)
                while i < n:
                    if tokens[i].type == TokenType.NEWLINE:
                        break
                        
                    if tokens[i].type == TokenType.IDENTIFIER:
                        module_name, consumed = self._consume_dotted_name(tokens, i)
                        i += consumed
                        
                        info = ImportInfo(
                            module_name=module_name,
                            lineno=token.line,
                            import_type=ImportType.IMPORT
                        )
                        imports.append(info)
                        
                        # Check for 'as'
                        if i < n and tokens[i].type == TokenType.AS:
                            i += 2 # Skip 'as' and alias name (simplification)
                            
                        # Check for comma
                        if i < n and tokens[i].type == TokenType.COMMA:
                            i += 1
                            continue
                        else:
                            break
                    else:
                        break

            elif token.type == TokenType.FROM:
                # from X import Y
                # from . import Y
                # from ..X import Y
                if not imports_allowed:
                    self._report_invalid_pos(file_path, token)
                    while i < n and tokens[i].type != TokenType.NEWLINE:
                        i += 1
                    continue
                    
                is_import = True
                i += 1 # consume from
                
                # Handle dots for relative import
                dots = 0
                while i < n and tokens[i].type == TokenType.DOT:
                    dots += 1
                    i += 1
                    
                module_name = ""
                if dots > 0:
                    module_name = "." * dots
                    
                if i < n and tokens[i].type == TokenType.IDENTIFIER:
                    suffix, consumed = self._consume_dotted_name(tokens, i)
                    module_name += suffix
                    i += consumed
                
                # Expect 'import'
                if i < n and tokens[i].type == TokenType.IMPORT:
                    i += 1 # consume import
                    # We don't really care what is imported, just that it IS an import from module_name
                    # But wait, 'from . import x', module_name is '.'
                    
                    if module_name:
                        info = ImportInfo(
                            module_name=module_name,
                            lineno=token.line,
                            import_type=ImportType.FROM_IMPORT
                        )
                        imports.append(info)
                
                # Skip rest of line
                while i < n and tokens[i].type != TokenType.NEWLINE:
                    i += 1
                    
            else:
                # Non-import token found
                # Ignore comments (Lexer usually skips them or produces COMMENT tokens if configured, 
                # but our Lexer skips comments by default)
                # If Lexer produces COMMENT tokens, we should skip them.
                # Assuming current Lexer implementation:
                # Lexer.skip_whitespace_and_comments() is called internally.
                # So we only see significant tokens.
                imports_allowed = False
                # Skip to next token
                i += 1
                
        mod_info = ModuleInfo(file_path=abs_path, imports=imports, content=content, mtime=mtime)
        self.modules[abs_path] = mod_info
        return mod_info

    def _consume_dotted_name(self, tokens: List[Token], start_index: int) -> tuple[str, int]:
        """
        Consumes tokens forming a dotted name (a.b.c).
        Returns (name, consumed_count).
        """
        name = ""
        consumed = 0
        i = start_index
        n = len(tokens)
        
        if i < n and tokens[i].type == TokenType.IDENTIFIER:
            name += tokens[i].value
            consumed += 1
            i += 1
            
            while i < n and tokens[i].type == TokenType.DOT:
                # Check if next is identifier
                if i + 1 < n and tokens[i+1].type == TokenType.IDENTIFIER:
                    name += "." + tokens[i+1].value
                    consumed += 2 # dot + identifier
                    i += 2
                else:
                    break
        return name, consumed

    def _report_invalid_pos(self, file_path: str, token: Token):
        loc = Location(file_path=file_path, line=token.line, column=token.column)
        self.issue_tracker.report(
            Severity.ERROR, 
            DEP_INVALID_IMPORT_POSITION, 
            "Import statements must be at the top of the file", 
            loc
        )

    def resolve_path(self, module_name: str, importer_path: str) -> str:
        """
        Resolves a module name (e.g., 'utils.math' or '..math') to an absolute file path.
        Rules:
        1. If starts with '.', resolve relative to importer_path.
        2. Else, resolve relative to root_dir.
        """
        is_relative = module_name.startswith('.')
        
        if is_relative:
            # Count leading dots
            level = 0
            for char in module_name:
                if char == '.':
                    level += 1
                else:
                    break
            
            # module_name: ..math -> level=2, suffix=math
            suffix = module_name[level:]
            
            # Determine base directory
            # importer_path is a file path.
            # We start from the directory containing the importer file
            current_dir = os.path.dirname(importer_path)
            
            # If importer is pkg/subpkg/calc.ibci
            # from ..math import add
            # level=2.
            # We want to go up (level - 1) times from current_dir
            
            base_dir = current_dir
            for _ in range(level - 1):
                base_dir = os.path.dirname(base_dir)
            
            # Construct relative path
            # suffix is 'math'
            if suffix:
                rel_path = suffix.replace('.', os.sep)
                candidate = os.path.join(base_dir, rel_path)
            else:
                # Import is just '..', e.g. from .. import X
                candidate = base_dir
                
        else:
            # Absolute import (from root)
            rel_path = module_name.replace('.', os.sep)
            candidate = os.path.join(self.root_dir, rel_path)
        
        # Check for file (e.g. utils/math.ibci)
        # Extensions to try
        extensions = ['.ibci', '.py', '']
        
        for ext in extensions:
            path = candidate + ext
            # Check if it's a file first
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
            
            mod_info = self.scan_file(current_path)
            if mod_info is None:
                continue
                
            for imp in mod_info.imports:
                try:
                    resolved_path = self.resolve_path(imp.module_name, current_path)
                    imp.file_path = resolved_path
                    if resolved_path not in visited and resolved_path not in queue:
                        queue.append(resolved_path)
                except ModuleNotFoundError:
                    loc = Location(file_path=current_path, line=imp.lineno, column=0)
                    self.issue_tracker.report(Severity.ERROR, DEP_MODULE_NOT_FOUND, f"Module '{imp.module_name}' not found", loc)
                    
        return self.modules
