import os
from typing import Dict, List, Optional, Any
from typedef.dependency_types import ModuleInfo, ImportInfo
from typedef.parser_types import Module
from typedef.scope_types import ScopeNode
from utils.dependency.dependency_scanner import DependencyScanner
from utils.dependency.graph import DependencyGraph
from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from utils.semantic.semantic_analyzer import SemanticAnalyzer
from utils.diagnostics.issue_tracker import IssueTracker
from utils.source.source_manager import SourceManager
from utils.dependency.resolver import ModuleResolver
from typedef.diagnostic_types import Severity, CompilerError

class Scheduler:
    """
    Top-level scheduler for multi-file compilation.
    Orchestrates DependencyScanner, Parser, and SemanticAnalyzer.
    """
    def __init__(self, root_dir: str):
        self.root_dir = os.path.realpath(root_dir)
        self.issue_tracker = IssueTracker()
        self.source_manager = SourceManager()
        self.resolver = ModuleResolver(self.root_dir)
        self.dependency_scanner = DependencyScanner(self.root_dir, self.issue_tracker)
        
        # Caches
        self.modules: Dict[str, ModuleInfo] = {} # Path -> Info
        self.ast_cache: Dict[str, Module] = {}   # Path -> AST
        self.scope_cache: Dict[str, ScopeNode] = {} # Path AND Name -> Scope (for Parser)
        
        # Build Cache
        # Map: file_path -> mtime
        self.build_cache: Dict[str, float] = {}

    def compile_project(self, entry_file: str) -> Dict[str, Module]:
        """
        Compiles the project starting from entry_file.
        Returns a map of file_path -> AST.
        """
        # 1. Scan Dependencies
        try:
            self.modules = self.dependency_scanner.scan_dependencies(entry_file)
        except Exception as e:
            # Propagate fatal dependency errors
            raise e
            
        if self.issue_tracker.has_errors():
            # We don't have source code for dependency errors yet (unless scanned)
            # But dependency scanner reports location.
            # We might want to register content for files that had dependency errors if possible.
            raise CompilerError("Dependency scanning failed.")

        # 2. Build Dependency Graph and Get Order
        graph = DependencyGraph(self.modules)
        try:
            compilation_order = graph.get_compilation_order()
        except Exception as e:
            self.issue_tracker.report(Severity.ERROR, "DEP_CYCLE", str(e))
            raise e

        # 3. Compile in Topological Order
        for file_path in compilation_order:
            # Check mtime
            mod_info = self.modules.get(file_path)
            if mod_info:
                last_mtime = self.build_cache.get(file_path, 0.0)
                if mod_info.mtime > last_mtime or file_path not in self.ast_cache:
                    # Recompile
                    try:
                        self._compile_file(file_path)
                    except CompilerError:
                        # Continue to see if we can compile others? 
                        # Usually not safe if dependent.
                        # But we collect errors.
                        pass
                    self.build_cache[file_path] = mod_info.mtime
                else:
                    pass
            
        if self.issue_tracker.has_errors():
            raise CompilerError("Compilation failed.")
            
        return self.ast_cache

    def _compile_file(self, file_path: str):
        """
        Compiles a single file: Lex -> Parse -> Semantic.
        Populates caches.
        """
        module_info = self.modules.get(file_path)
        if not module_info:
            return # Should not happen

        # Determine module name from path relative to root
        rel_path = os.path.relpath(file_path, self.root_dir)
        # Remove extension and replace separators
        base_name = os.path.splitext(rel_path)[0]
        module_name = base_name.replace(os.sep, '.')
        
        # Read source
        source = module_info.content
        self.source_manager.add_source(file_path, source)
        
        # Create per-file tracker
        file_tracker = IssueTracker(file_path)
        
        try:
            # Lexing
            lexer = Lexer(source, file_tracker)
            tokens = lexer.tokenize()
            
            # Parsing
            parser = Parser(tokens, file_tracker, self.scope_cache, package_name=module_name, module_resolver=self.resolver)
            ast_node = parser.parse()
            
            self.ast_cache[file_path] = ast_node
            
            # Semantic Analysis
            analyzer = SemanticAnalyzer(file_tracker)
            analyzer.analyze(ast_node)
            
            # Register the module's scope for other modules to use
            if ast_node.scope:
                self.scope_cache[file_path] = ast_node.scope
                self.scope_cache[module_name] = ast_node.scope
                
        except CompilerError:
            # Errors already in file_tracker
            pass
        except Exception as e:
            # Unexpected error
            import traceback
            traceback.print_exc()
            file_tracker.report(Severity.FATAL, "INTERNAL_ERROR", str(e))
            
        finally:
            # Merge diagnostics to global tracker
            self.issue_tracker.merge(file_tracker)
            
        if file_tracker.has_errors():
            raise CompilerError("File compilation failed.")
