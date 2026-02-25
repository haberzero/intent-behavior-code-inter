import os
from typing import Dict, List, Optional, Any, Set
from typedef.dependency_types import ModuleInfo, ImportInfo, CircularDependencyError
from typedef.parser_types import Module
from typedef.scope_types import ScopeNode
from utils.parser.scanners.import_scanner import ImportScanner
from utils.lexer.lexer import Lexer
from typedef.lexer_types import Token
from utils.parser.parser import Parser
from utils.semantic.semantic_analyzer import SemanticAnalyzer
from utils.diagnostics.issue_tracker import IssueTracker
from utils.source.source_manager import SourceManager
from utils.parser.resolver.resolver import ModuleResolver
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
        # DependencyScanner is now instantiated per file
        
        # Caches
        self.modules: Dict[str, ModuleInfo] = {} # Path -> Info
        self.ast_cache: Dict[str, Module] = {}   # Path -> AST
        self.scope_cache: Dict[str, ScopeNode] = {} # Path AND Name -> Scope (for Parser)
        self.token_cache: Dict[str, List[Token]] = {} # Path -> Tokens (Cached from initial scan)
        self.module_name_to_path: Dict[str, str] = {} # Name -> Path (Fast lookup)
        
        # Build Cache
        # Map: file_path -> mtime
        self.build_cache: Dict[str, float] = {}

    def get_module_ast(self, module_name: str) -> Optional[Module]:
        """
        通过模块名获取已编译的 AST。
        """
        # 1. 尝试通过快速索引查找文件路径
        path = self.module_name_to_path.get(module_name)
        if path:
            return self.ast_cache.get(path)
            
        # 2. 回退：尝试直接在缓存中查找 (兼容逻辑)
        if module_name in self.scope_cache:
            for path, scope in self.scope_cache.items():
                if scope == self.scope_cache[module_name] and path != module_name:
                    return self.ast_cache.get(path)
        return None

    def compile_project(self, entry_file: str) -> Dict[str, Module]:
        """
        Compiles the project starting from entry_file.
        Returns a map of file_path -> AST.
        """
        # 1. Scan Dependencies (Recursive)
        # We manually drive the scanning process here to control token caching
        entry_file = os.path.abspath(entry_file)
        self._scan_and_cache(entry_file)
            
        if self.issue_tracker.has_errors():
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
                        pass
                    self.build_cache[file_path] = mod_info.mtime
                else:
                    pass
            
        if self.issue_tracker.has_errors():
            raise CompilerError("Compilation failed.")
            
        return self.ast_cache

    def _scan_and_cache(self, entry_file: str):
        """
        Recursively scan files, Lex them, cache tokens, and resolving imports.
        Manages the dependency graph creation and prevents cycles during scanning.
        """
        visited = set()
        queue = [entry_file]
        
        # We also need to track what we've processed in this session to avoid infinite loops if cycle exists
        # Although DependencyGraph will catch cycles later, we don't want infinite recursion here.
        processed_in_this_scan = set()

        while queue:
            current_path = queue.pop(0)
            if current_path in visited:
                continue
            
            visited.add(current_path)
            processed_in_this_scan.add(current_path)
            
            # Security Check: Ensure file is within root_dir
            try:
                abs_root = self.root_dir
                abs_path = os.path.realpath(current_path)
                if os.path.commonpath([abs_root, abs_path]) != abs_root:
                    self.issue_tracker.report(Severity.ERROR, "DEP_FILE_NOT_FOUND", f"Security Error: Access denied for file outside root: {current_path}")
                    continue
            except ValueError:
                 self.issue_tracker.report(Severity.ERROR, "DEP_FILE_NOT_FOUND", f"Security Error: Access denied (drive mismatch): {current_path}")
                 continue

            # 1. Read Content & Lex (if not cached or outdated)
            # Check build_cache or just always read? 
            # For now, we assume we need to scan to find dependencies.
            
            try:
                with open(current_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    mtime = os.path.getmtime(current_path)
            except (FileNotFoundError, OSError):
                self.issue_tracker.report(Severity.ERROR, "DEP_FILE_NOT_FOUND", f"File not found: {current_path}")
                continue
            
            # Lexing
            lexer = Lexer(content, self.issue_tracker)
            try:
                tokens = lexer.tokenize()
                self.token_cache[current_path] = tokens
            except Exception:
                # Lexer error reported to issue_tracker
                continue
                
            # 2. Scan Imports using ImportScanner (Token based)
            scanner = ImportScanner(tokens, self.issue_tracker)
            imports = scanner.scan(current_path)
            
            # Create ModuleInfo
            mod_info = ModuleInfo(
                file_path=current_path,
                imports=imports,
                content=content,
                mtime=mtime
            )
            self.modules[current_path] = mod_info

            # 3. Resolve and Enqueue Imports
            for imp in imports:
                try:
                    resolved_path = self.resolver.resolve(imp.module_name, current_path)
                    imp.file_path = resolved_path
                    
                    # Cycle Prevention: Only add to queue if not visited
                    if resolved_path not in visited and resolved_path not in queue:
                        queue.append(resolved_path)
                        
                except Exception:
                     # Resolver errors are already reported by resolver or we should ensure they are.
                     # The resolver raises ModuleResolveError, let's catch it to report if not reported.
                     # Actually ModuleResolveError carries info.
                     pass
                         
    def _compile_file(self, file_path: str):
        """
        Compiles a single file: Lex (reuse) -> Parse -> Semantic.
        Populates caches.
        """
        module_info = self.modules.get(file_path)
        if not module_info:
            return 

        # Determine module name
        rel_path = os.path.relpath(file_path, self.root_dir)
        base_name = os.path.splitext(rel_path)[0]
        module_name = base_name.replace(os.sep, '.')
        self.module_name_to_path[module_name] = file_path
        
        # Get content
        source = module_info.content
        self.source_manager.add_source(file_path, source)
        
        # Create per-file tracker
        file_tracker = IssueTracker(file_path)
        
        try:
            # 1. Reuse Tokens
            tokens = self.token_cache.get(file_path)
            if not tokens:
                # Should not happen if _scan_and_cache ran successfully
                # But if it failed, we might be here?
                # Re-lex
                lexer = Lexer(source, file_tracker)
                tokens = lexer.tokenize()
            
            # 2. Parse
            parser = Parser(tokens, file_tracker, self.scope_cache, package_name=module_name, module_resolver=self.resolver)
            ast_node = parser.parse()
            
            self.ast_cache[file_path] = ast_node
            
            # 3. Semantic Analysis
            analyzer = SemanticAnalyzer(file_tracker)
            analyzer.analyze(ast_node)
            
            # Register Scope
            if ast_node.scope:
                self.scope_cache[file_path] = ast_node.scope
                self.scope_cache[module_name] = ast_node.scope
                
        except CompilerError:
            pass
        except Exception as e:
            import traceback
            traceback.print_exc()
            file_tracker.report(Severity.FATAL, "INTERNAL_ERROR", str(e))
            
        finally:
            self.issue_tracker.merge(file_tracker)
            
        if file_tracker.has_errors():
            raise CompilerError("File compilation failed.")

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
