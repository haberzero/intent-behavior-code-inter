import os
from typing import Dict, List, Optional
from typedef.dependency_types import (
    ImportInfo, ModuleInfo, ImportType, ModuleNotFoundError
)
from utils.diagnostics.issue_tracker import IssueTracker
from typedef.diagnostic_types import Severity, Location
from utils.diagnostics.codes import DEP_FILE_NOT_FOUND, DEP_MODULE_NOT_FOUND, DEP_INVALID_IMPORT_POSITION
from utils.lexer.lexer import Lexer
from typedef.lexer_types import TokenType, Token
from utils.parser.base_parser import BaseParser, ParseControlFlowError
from utils.dependency.resolver import ModuleResolver, ModuleResolveError

class ImportScanner(BaseParser):
    """
    Helper class to scan tokens for import statements using shared parsing logic.
    """
    def scan(self, file_path: str) -> List[ImportInfo]:
        imports = []
        imports_allowed = True
        
        while not self.is_at_end():
            token = self.peek()
            
            # Skip whitespace/structure tokens
            if token.type in (TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT):
                self.advance()
                continue
                
            if token.type == TokenType.EOF:
                break
                
            # Check for Import
            if self.match(TokenType.IMPORT):
                if not imports_allowed:
                    self._report_invalid_pos(file_path, self.previous())
                    self._skip_to_next_statement()
                    continue
                    
                try:
                    # BaseParser.parse_import assumes 'import' was consumed (previous token)
                    # We consumed it with match(IMPORT)
                    node = self.parse_import()
                    
                    for alias in node.names:
                        info = ImportInfo(
                            module_name=alias.name,
                            lineno=node.lineno,
                            import_type=ImportType.IMPORT
                        )
                        imports.append(info)
                except ParseControlFlowError:
                    self._skip_to_next_statement()
                    
            elif self.match(TokenType.FROM):
                if not imports_allowed:
                    self._report_invalid_pos(file_path, self.previous())
                    self._skip_to_next_statement()
                    continue
                    
                try:
                    node = self.parse_from_import()
                    
                    # Reconstruct module name representation
                    mod_name = node.module or ""
                    if node.level > 0:
                        mod_name = "." * node.level + mod_name
                        
                    info = ImportInfo(
                        module_name=mod_name,
                        lineno=node.lineno,
                        import_type=ImportType.FROM_IMPORT
                    )
                    imports.append(info)
                except ParseControlFlowError:
                    self._skip_to_next_statement()
                    
            else:
                # Non-import token found (and not newline/indent)
                # This marks the end of the allowed import section
                imports_allowed = False
                self.advance()
                
        return imports

    def _skip_to_next_statement(self):
        while not self.is_at_end() and self.peek().type != TokenType.NEWLINE:
            self.advance()
        if self.match(TokenType.NEWLINE):
            pass

    def _report_invalid_pos(self, file_path: str, token: Token):
        loc = Location(file_path=file_path, line=token.line, column=token.column)
        self.issue_tracker.report(
            Severity.ERROR, 
            DEP_INVALID_IMPORT_POSITION, 
            "Import statements must be at the top of the file", 
            loc
        )

class DependencyScanner:
    """
    Scans source files for import statements and resolves file paths.
    """
    
    def __init__(self, root_dir: str, issue_tracker: Optional[IssueTracker] = None):
        self.root_dir = os.path.abspath(root_dir)
        self.issue_tracker = issue_tracker or IssueTracker()
        self.modules: Dict[str, ModuleInfo] = {} # Key: Absolute file path
        self.resolver = ModuleResolver(self.root_dir)
        
    def scan_file(self, file_path: str) -> Optional[ModuleInfo]:
        """
        Scans a single file for imports using ImportScanner.
        """
        abs_path = os.path.abspath(file_path)
        
        # Security Check: Ensure file is within root_dir
        try:
            abs_root = os.path.abspath(self.root_dir)
            if os.path.commonpath([abs_root, abs_path]) != abs_root:
                self.issue_tracker.report(Severity.ERROR, DEP_FILE_NOT_FOUND, f"Security Error: Access denied for file outside root: {file_path}")
                return None
        except ValueError:
             self.issue_tracker.report(Severity.ERROR, DEP_FILE_NOT_FOUND, f"Security Error: Access denied for file on different drive: {file_path}")
             return None

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
            
        # Lexing
        # We use a temporary IssueTracker for Lexing to avoid polluting the global one with syntax errors
        # unless we want to report them? 
        # Usually Dependency Scan should be tolerant or report errors.
        # But here we pass self.issue_tracker to ImportScanner, so syntax errors in imports are reported.
        # For Lexer, if it fails, it might be better to report.
        
        lexer_tracker = self.issue_tracker # Use same tracker? Or a temp one?
        # If we use global tracker, lexer errors (like unterminated string) will block compilation.
        # This is correct.
        
        lexer = Lexer(content, lexer_tracker)
        try:
            tokens = lexer.tokenize()
        except Exception:
            # Lexer might raise CompilerError if issue_tracker has errors
            # Or we can catch it.
            return None
        
        # Scanning
        scanner = ImportScanner(tokens, self.issue_tracker)
        imports = scanner.scan(abs_path)
        
        mod_info = ModuleInfo(file_path=abs_path, imports=imports, content=content, mtime=mtime)
        self.modules[abs_path] = mod_info
        return mod_info

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
            
            visited.add(current_path)
            
            mod_info = self.scan_file(current_path)
            if mod_info is None:
                continue
                
            for imp in mod_info.imports:
                try:
                    resolved_path = self.resolver.resolve(imp.module_name, current_path)
                    imp.file_path = resolved_path
                    if resolved_path not in visited and resolved_path not in queue:
                        queue.append(resolved_path)
                except ModuleResolveError:
                    # Map ResolveError to existing ModuleNotFoundError
                    # Or report directly
                    loc = Location(file_path=current_path, line=imp.lineno, column=0)
                    self.issue_tracker.report(Severity.ERROR, DEP_MODULE_NOT_FOUND, f"Module '{imp.module_name}' not found", loc)
                    
        return self.modules
