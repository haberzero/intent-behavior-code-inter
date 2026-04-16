import os
from typing import Dict, List, Optional, Any, Set
from collections import OrderedDict
from core.compiler.dependencies import ModuleInfo, ImportInfo, CircularDependencyError, ModuleStatus, ImportType, DependencyGraph
from core.kernel.ast import IbModule
from core.compiler.lexer.lexer import Lexer
from core.compiler.common.tokens import Token
from core.compiler.parser.parser import Parser
from core.compiler.semantic.passes.semantic_analyzer import SemanticAnalyzer
from core.compiler.common.diagnostics import DiagnosticReporter
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.base.source.source_manager import SourceManager
from core.compiler.parser.resolver.resolver import ModuleResolver
from core.kernel.issue import Severity, CompilerError
from core.base.source_atomic import Location
from core.runtime.host.host_interface import HostInterface
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger
from core.base.diagnostics.codes import (
    DEP_GRAPH_ERROR, DEP_FAILED_DEPENDENCY, DEP_SECURITY_ERROR, DEP_FILE_NOT_FOUND, INTERNAL_ERROR,
    DEP_MODULE_NOT_FOUND
)
from core.kernel.blueprint import CompilationArtifact, CompilationResult

from core.base.interfaces import (
    ISourceProvider, ICompilerService
)
from core.kernel.symbols import (
    Symbol, VariableSymbol, SymbolKind, SymbolTable, FunctionSymbol, TypeSymbol
)
from core.kernel.spec import ModuleSpec as ModuleMetadata, IbSpec, LazySpec
# from core.compiler.semantic.bridge import TypeBridge # REMOVED: File does not exist

class Scheduler(ICompilerService):
    """
    Top-level scheduler for multi-file compilation.
    Orchestrates Lexer, Parser, and SemanticAnalyzer.
    """
    MAX_CACHE_SIZE = 100 # Maximum modules to keep in memory

    def __init__(self, root_dir: str, host_interface: Optional[HostInterface] = None, debugger: Optional[Any] = None, issue_tracker: Optional[DiagnosticReporter] = None, registry: Optional[Any] = None):
        self.root_dir = os.path.realpath(root_dir)
        self.source_manager = SourceManager()
        self.issue_tracker = issue_tracker or IssueTracker(source_provider=self.source_manager)
        self.resolver = ModuleResolver(self.root_dir)
        self.host_interface = host_interface or HostInterface()
        self.debugger = debugger or core_debugger
        self.registry = registry # 注册表实例，用于类型同步
        
        # Initial symbols to pre-populate in every module's global scope
        self.predefined_symbols: Dict[str, Any] = {}
        
        # Caches (Using OrderedDict for LRU behavior)
        self.modules: Dict[str, ModuleInfo] = {} # Path -> Info
        self.ast_cache: OrderedDict[str, IbModule] = OrderedDict()   # Path -> AST
        self.symbol_table_cache: OrderedDict[str, Any] = OrderedDict() # Path -> SymbolTable
        self.token_cache: OrderedDict[str, List[Token]] = OrderedDict() # Path -> Tokens
        self.module_name_to_path: Dict[str, str] = {} # Name -> Path (Fast lookup)
        
        # 插件类型缓存：用于存储已转换的外部插件模块类型，支持跨插件继承
        self.plugin_type_cache: Dict[str, Any] = {}
        
        # Build Cache
        # Map: file_path -> mtime
        self.build_cache: Dict[str, float] = {}
        
        # Explicitly allowed files outside root (e.g. for run_string)
        self.allowed_files: Set[str] = set()

    def allow_file(self, file_path: str):
        """Explicitly allow a file outside root_dir."""
        abs_path = os.path.realpath(file_path)
        self.allowed_files.add(abs_path)
        self.resolver.allow_file(abs_path)

    # --- ICompilerService Implementation ---

    def compile_file(self, file_path: str) -> CompilationArtifact:
        """ICompilerService: Compiles a file and its dependencies."""
        return self.compile_project(file_path)

    # TODO: 怀疑是智能体引入的妥协性操作。后续需要单独严格审核。目前MVP Demo暂时不深究
    def compile_to_artifact_dict(self, file_path: str) -> Dict[str, Any]:
        """ICompilerService: 编译文件并返回平铺化的字典产物，供解释器直接加载。"""
        artifact = self.compile_file(file_path)
        from core.compiler.serialization.serializer import FlatSerializer
        return FlatSerializer().serialize_artifact(artifact)

    def resolve_module_path(self, module_name: str) -> Optional[str]:
        """ICompilerService: Resolves a module name to its absolute file path."""
        # Check cache first
        if module_name in self.module_name_to_path:
            return self.module_name_to_path[module_name]
        
        # Try resolving relative to root_dir
        try:
            return self.resolver.resolve(module_name, os.path.join(self.root_dir, "__init__.ibci"))
        except:
            return None

    def get_module_source(self, module_name: str) -> Optional[str]:
        """ICompilerService: Returns the source content of a module."""
        path = self.resolve_module_path(module_name)
        if not path:
            return None
        return self.source_manager.get_full_source(path)

    # ---------------------------------------

    def compile_project(self, entry_file: str) -> CompilationArtifact:
        """
        Compiles the project starting from entry_file.
        Returns a CompilationArtifact (Blueprint) for the interpreter.
        """
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Starting project compilation: {entry_file}")
        # 0. Clear previous state
        self.issue_tracker.clear()
        self.modules.clear()
        self.module_name_to_path.clear()
        
        artifact = CompilationArtifact()
        
        # 1. Scan Dependencies (Recursive)
        # We manually drive the scanning process here to control token caching
        entry_file = os.path.abspath(entry_file)
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Phase 1: Scanning dependencies starting from {entry_file}")
        self._scan_and_cache(entry_file)
            
        if self.issue_tracker.has_errors():
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, "Dependency scanning failed with errors.")
            raise CompilerError(self.issue_tracker.diagnostics)

        # 2. Build Dependency Graph and Get Order
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, "Phase 2: Building dependency graph and determining compilation order.")
        graph = DependencyGraph(self.modules, debugger=self.debugger)
        try:
            compilation_order = graph.get_compilation_order()
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DATA, f"Compilation order determined:", data=compilation_order)
        except Exception as e:
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Circular dependency or graph error: {str(e)}")
            self.issue_tracker.error(str(e), code=DEP_GRAPH_ERROR)
            raise e

        # 3. Compile in Topological Order
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Phase 3: Compiling {len(compilation_order)} files in topological order.")
        for file_path in compilation_order:
            mod_info = self.modules.get(file_path)
            if not mod_info:
                continue

            # Check if dependencies failed
            failed_deps = []
            for imp in mod_info.imports:
                if imp.file_path:
                    dep_info = self.modules.get(imp.file_path)
                    if dep_info and dep_info.status == ModuleStatus.FAILED:
                        failed_deps.append(imp.module_name)
            
            if failed_deps:
                self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Skipping {file_path} because dependencies failed: {failed_deps}")
                self.issue_tracker.error(f"IbModule '{file_path}' cannot be compiled because its dependencies failed: {', '.join(failed_deps)}", code=DEP_FAILED_DEPENDENCY)
                mod_info.status = ModuleStatus.FAILED
                continue

            # Determine module name
            rel_path = os.path.relpath(file_path, self.root_dir)
            base_name = os.path.splitext(rel_path)[0]
            module_name = base_name.replace(os.sep, '.')
            self.module_name_to_path[module_name] = file_path

            # Check mtime or cache
            last_mtime = self.build_cache.get(file_path, 0.0)
            if mod_info.mtime > last_mtime or file_path not in self.ast_cache:
                # Recompile
                self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Compiling file: {file_path} (Cache miss/Outdated)")
                try:
                    res = self._compile_file(file_path, artifact)
                    artifact.add_module(module_name, res)
                    mod_info.status = ModuleStatus.SUCCESS
                except CompilerError:
                    self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Failed to compile: {file_path}")
                    mod_info.status = ModuleStatus.FAILED
                self.build_cache[file_path] = mod_info.mtime
            else:
                self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Using cached AST for: {file_path}")
                # Reconstruct result from cache
                res = CompilationResult(
                    module_ast=self.ast_cache[file_path], 
                    symbol_table=self.symbol_table_cache.get(file_path)
                )
                artifact.add_module(module_name, res)
                mod_info.status = ModuleStatus.SUCCESS
            
        if self.issue_tracker.has_errors():
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, "Project compilation failed with errors.")
            raise CompilerError(self.issue_tracker.diagnostics)
            
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, "Project compilation successful.")
        
        # Set entry point
        entry_rel = os.path.relpath(entry_file, self.root_dir)
        artifact.entry_module = os.path.splitext(entry_rel)[0].replace(os.sep, '.')
        artifact.global_symbols = self.predefined_symbols

        return artifact

    def _prune_cache(self):
        """
        Maintains the LRU cache by removing oldest items if capacity exceeded.
        """
        while len(self.ast_cache) > self.MAX_CACHE_SIZE:
            oldest_path, _ = self.ast_cache.popitem(last=False)
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Pruning cache for {oldest_path}")
            # Optionally remove from other caches if they are tightly coupled
            if oldest_path in self.token_cache:
                self.token_cache.pop(oldest_path)
            # Note: scope_cache is harder to prune because it's used for cross-file analysis.
            # For now, we keep scopes as they are relatively small.

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
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Scanning: {current_path}")
            
            # Security Check: Ensure file is within root_dir or explicitly allowed
            try:
                abs_root = self.root_dir
                abs_path = os.path.realpath(current_path)
                if abs_path not in self.allowed_files and os.path.commonpath([abs_root, abs_path]) != abs_root:
                    self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Security violation: Access denied for {current_path}")
                    self.issue_tracker.error(f"Security Error: Access denied for file outside root: {current_path}", code=DEP_SECURITY_ERROR)
                    continue
            except ValueError:
                 self.issue_tracker.error(f"Security Error: Access denied (drive mismatch): {current_path}", code=DEP_SECURITY_ERROR)
                 continue

            # 1. Read Content & Lex (if not cached or outdated)
            try:
                with open(current_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    mtime = os.path.getmtime(current_path)
            except (FileNotFoundError, OSError):
                self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"File not found: {current_path}")
                self.issue_tracker.error(f"File not found: {current_path}", code=DEP_FILE_NOT_FOUND)
                continue
            
            # Register source before lexing to enable context in errors
            self.source_manager.add_source(current_path, content)
            
            # Lexing
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Lexing for dependencies: {current_path}")
            lexer = Lexer(content, self.issue_tracker, debugger=self.debugger)
            try:
                tokens = lexer.tokenize()
                self.token_cache[current_path] = tokens
            except Exception:
                # Lexer error reported to issue_tracker
                continue
                
            # 2. Scan Imports using Main Parser (parse_imports_only)
            # Replaced ImportScanner with Parser.parse_imports_only
            parser = Parser(
                tokens, 
                self.issue_tracker, 
                debugger=self.debugger
            )
            imports = parser.parse_imports_only()
            
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DATA, f"Found imports in {current_path}:", data=[i.module_name for i in imports])
            
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
                # Skip external modules - they don't have source files
                # 直接通过元数据注册表查询外部模块，消除 HostInterface 兼容性依赖
                module_name = imp.module_name
                if self.host_interface.metadata.resolve(module_name) is not None:
                    self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Found external module: {module_name}")
                    continue
                if module_name in self.host_interface._module_metadata_map:
                    self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Found external module via alias: {module_name}")
                    continue

                try:
                    resolved_path = self.resolver.resolve(imp.module_name, current_path)
                    imp.file_path = resolved_path
                    self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Resolved import '{imp.module_name}' to {resolved_path}")
                    
                    # Cycle Prevention: Only add to queue if not visited
                    if resolved_path not in visited and resolved_path not in queue:
                        queue.append(resolved_path)
                        
                except Exception as e:
                     self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Failed to resolve '{imp.module_name}': {str(e)}")
                     # Use appropriate error code based on message
                     code = DEP_MODULE_NOT_FOUND
                     if "Security Error" in str(e):
                         code = DEP_SECURITY_ERROR
                     
                     self.issue_tracker.report(
                         Severity.ERROR, 
                         code=code, 
                         message=str(e),
                         location=Location(file_path=current_path, line=imp.lineno, column=1)
                     )
                         
    def _compile_file(self, file_path: str, artifact: CompilationArtifact):
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
        file_tracker = IssueTracker(file_path, source_provider=self.source_manager)
        
        try:
            # 1. Reuse Tokens
            tokens = self.token_cache.get(file_path)
            if not tokens:
                # re-lex 纯粹的防御机制，常规情况下，理论上来讲不应该出现
                self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Token cache miss for {file_path}, re-lexing.")
                lexer = Lexer(source, file_tracker, debugger=self.debugger)
                tokens = lexer.tokenize()
            
            # 2. Parse
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Parsing: {file_path} (IbModule: {module_name})")
            parser = Parser(
                tokens, 
                file_tracker, 
                package_name=module_name, 
                module_resolver=self.resolver,
                host_interface=self.host_interface,
                debugger=self.debugger
            )
            ast_node = parser.parse()
            
            # 3. Semantic Analysis
            self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Semantic Analysis: {file_path}")
            
            # 在分析前预注册空的 ModuleMetadata 到注册表
            # 这样 LazySpec 才能在解析时找到目标，即使当前模块还未分析完
            pre_mod_meta = self.registry.factory.create_module(module_name) if self.registry else ModuleMetadata(name=module_name)
            self.registry.register(pre_mod_meta)
            
            analyzer = SemanticAnalyzer(file_tracker, host_interface=self.host_interface, debugger=self.debugger, registry=self.registry, module_name=module_name)
            
            # Inject predefined symbols
            for name, val in self.predefined_symbols.items():
                if isinstance(val, Symbol):
                    analyzer.symbol_table.define(val)
                else:
                    # Log a warning for non-Symbol predefined symbols (should not happen now)
                    self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Warning: Predefined symbol '{name}' is not a Symbol object, skipping.")
            
            # Inject imported modules
            # [CLEANUP] Local imports removed and consolidated at top
            # TypeBridge import removed as file does not exist
            
            for imp in module_info.imports:
                # 查找已编译的结果或外部元数据
                s_mod_type = None
                imp_res = None
                
                if imp.file_path:
                    rel_imp_path = os.path.relpath(imp.file_path, self.root_dir)
                    imp_mod_name = os.path.splitext(rel_imp_path)[0].replace(os.sep, '.')
                    
                    # 统一使用 LazySpec 解决循环依赖问题
                    # 无论该模块是否已编译，都先注入 Lazy 描述符，
                    # 真正的成员解析将推迟到语义分析阶段通过 MetadataRegistry 自动解包。
                    s_mod_type = LazySpec(name=imp_mod_name)
                    # 必须绑定注册表以便后续解包
                elif imp.module_name in self.host_interface._module_metadata_map:
                    s_mod_type = self.host_interface._module_metadata_map[imp.module_name]
                elif self.host_interface.metadata.resolve(imp.module_name) is not None:
                    if imp.module_name in self.plugin_type_cache:
                        s_mod_type = self.plugin_type_cache[imp.module_name]
                    else:
                        # 直接从宿主接口的元数据注册表解析描述符
                        s_mod_type = self.host_interface.metadata.resolve(imp.module_name)
                        if s_mod_type:
                            # [UTS 2.0 Hydration] 确保从 Host 加载的元数据被正确水合到当前编译注册表
                            self.registry.register(s_mod_type)
                            self.plugin_type_cache[imp.module_name] = s_mod_type
                
                if not s_mod_type:
                    continue
                    
                # 根据 import_type 进行符号注入
                if imp.import_type == ImportType.IMPORT:
                    # 1. 处理 import a.b as c
                    # 目前 parse_imports_only 为每个 alias 创建一个 ImportInfo
                    alias = imp.names[0] if imp.names else None
                    local_name = alias.asname if alias and alias.asname else imp.module_name
                    
                    # 如果是多段导入 (import a.b) 且没有 asname，则注入 a
                    parts = imp.module_name.split('.')
                    if not (alias and alias.asname) and len(parts) > 1:
                        root_name = parts[0]
                        # 构造嵌套模块结构
                        root_sym = analyzer.symbol_table.resolve(root_name)
                        # 使用 is_module() 代替 isinstance
                        if not root_sym or not root_sym.spec or not isinstance(root_sym.spec, ModuleSpec):
                            # 使用工厂创建
                            root_mod_type = self.registry.factory.create_primitive("module")
                            root_mod_type.name = root_name
                            root_sym = VariableSymbol(name=root_name, kind=SymbolKind.MODULE, spec=root_mod_type)
                            analyzer.symbol_table.define(root_sym)
                        
                        curr_mod = root_sym.spec
                        for i in range(1, len(parts)):
                            part_name = parts[i]
                            is_last = (i == len(parts) - 1)
                            if is_last:
                                target_sym = VariableSymbol(name=part_name, kind=SymbolKind.MODULE, spec=s_mod_type)
                                curr_mod.exported_scope.define(target_sym)
                            else:
                                next_mod_sym = curr_mod.exported_scope.resolve(part_name)
                                # 使用 is_module() 代替 isinstance
                                if not next_mod_sym or not next_mod_sym.spec or not isinstance(next_mod_sym.spec, ModuleSpec):
                                    next_mod_type = self.registry.factory.create_primitive("module")
                                    next_mod_type.name = part_name
                                    next_mod_sym = VariableSymbol(name=part_name, kind=SymbolKind.MODULE, spec=next_mod_type)
                                    curr_mod.exported_scope.define(next_mod_sym)
                                curr_mod = next_mod_sym.spec
                    else:
                        # 普通导入或带别名导入
                        # [临时方案] 检查是否已存在同名符号
                        # [Future] 严格遵循显式引入原则：外部模块符号不预注入
                        existing = analyzer.symbol_table.resolve(local_name)
                        if existing:
                            # 情况1：已存在 MODULE 符号（可能是 Prelude 预注入的外部模块）
                            if existing.kind == SymbolKind.MODULE:
                                # 跳过重复注入
                                # 这符合"显式引入"原则的临时妥协：允许未 import 时使用 ai.xxx
                                pass
                            else:
                                # 情况2：已存在用户定义的符号（CLASS, FUNCTION 等）
                                # 外部模块的 import 应该被忽略或给出警告
                                # 因为用户可能意图使用自己定义的符号
                                pass
                        else:
                            mod_sym = VariableSymbol(name=local_name, kind=SymbolKind.MODULE, spec=s_mod_type, metadata={"is_external_module": True})
                            analyzer.symbol_table.define(mod_sym)
                        
                elif imp.import_type == ImportType.FROM_IMPORT:
                    # 2. 处理 from mod import a, b as c, *
                    for alias in imp.names:
                        if alias.name == '*':
                            # 注入所有导出的符号
                            # [临时方案] 检查是否已存在同名符号
                            for name, sym in s_mod_type.exported_scope.symbols.items():
                                existing = analyzer.symbol_table.resolve(name)
                                if existing:
                                    pass  # 跳过重复注入
                                else:
                                    new_sym = SymbolFactory.create_from_descriptor(name, sym.spec) if sym.spec else sym
                                    analyzer.symbol_table.define(new_sym)
                        else:
                            # 注入特定符号
                            target_sym = s_mod_type.exported_scope.resolve(alias.name)
                            if target_sym:
                                local_name = alias.asname if alias.asname else alias.name
                                # [临时方案] 检查是否已存在同名符号
                                existing = analyzer.symbol_table.resolve(local_name)
                                if existing:
                                    pass  # 跳过重复注入
                                else:
                                    # 创建一个指向原符号的克隆/别名符号
                                    # 使用 descriptor 参数，而不是 var_type/type_signature
                                    if target_sym.kind == SymbolKind.VARIABLE:
                                        new_sym = VariableSymbol(name=local_name, kind=SymbolKind.VARIABLE, spec=target_sym.spec, def_node=target_sym.def_node, metadata={"is_external_module": True})
                                    elif target_sym.kind == SymbolKind.FUNCTION:
                                        new_sym = FunctionSymbol(name=local_name, kind=SymbolKind.FUNCTION, spec=target_sym.spec, def_node=target_sym.def_node, metadata={"is_external_module": True})
                                    else:
                                        new_sym = TypeSymbol(name=local_name, kind=target_sym.kind, spec=target_sym.spec, def_node=target_sym.def_node, metadata={"is_external_module": True})

                                    analyzer.symbol_table.define(new_sym)
                            else:
                                # 符号未找到报错
                                analyzer.issue_tracker.report(
                                    Severity.ERROR, "SEM_001", 
                                    f"Symbol '{alias.name}' not found in module '{imp.module_name}'",
                                    location=Location(file_path=file_path, line=imp.lineno, column=1)
                                )
            
            result = analyzer.analyze(ast_node)
            
            # 语义分析完成后，更新注册表中的元数据成员
            # 这确保了 LazySpec 在解析时能看到完整的符号表
            final_mod_meta = self.registry.resolve(module_name)
            if final_mod_meta:
                # 过滤掉非导出的符号（如内部变量）可以在这里做，目前默认全量导出
                final_mod_meta.members = result.symbol_table.symbols
            
            # Cache AST, Tokens, and SymbolTable
            self.ast_cache[file_path] = ast_node
            self.symbol_table_cache[file_path] = result.symbol_table
            
            self.ast_cache.move_to_end(file_path)
            self.symbol_table_cache.move_to_end(file_path)
            if file_path in self.token_cache:
                self.token_cache.move_to_end(file_path)
            
            self._prune_cache()
            
            module_info.status = ModuleStatus.COMPILED
            return result
            
        except CompilerError:
            raise
        except Exception as e:
            file_tracker.error(f"Internal compiler error: {str(e)}", code=INTERNAL_ERROR)
            raise CompilerError(file_tracker.diagnostics) from e
        finally:
            self.issue_tracker.merge(file_tracker)
            
        if file_tracker.has_errors():
            raise CompilerError(file_tracker.diagnostics)

# DependencyGraph logic moved to core.compiler.dependencies
# This file imports DependencyGraph from there.
