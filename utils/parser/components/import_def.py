from typing import List, Optional
from typedef.lexer_types import TokenType
from typedef import parser_types as ast
from typedef.symbol_types import SymbolType
from typedef.scope_types import ScopeNode, ScopeType
from typedef.diagnostic_types import Severity
from utils.parser.core.component import BaseComponent
from utils.diagnostics.codes import DEP_INVALID_IMPORT_POSITION, DEP_MODULE_NOT_FOUND

class ImportComponent(BaseComponent):
    """
    Component for parsing import statements and registering them in the scope.
    """

    def parse_import(self) -> ast.Import:
        """Parses 'import a.b, c as d'."""
        start_token = self.stream.previous() 
        
        names = self.parse_aliases()
        self.stream.consume_end_of_statement("Expect newline after import.")
        
        node = self._loc(ast.Import(names=names), start_token)
        
        # Registration Logic
        for alias_node in node.names:
            module_name = alias_node.name
            asname = alias_node.asname
            
            # Resolve final scope for the full module name
            final_scope = self._resolve_module_scope(module_name, node)
            
            if asname:
                # import a.b.c as d
                # Define 'd' pointing to the final module scope
                sym = self.scope_manager.define(asname, SymbolType.MODULE)
                sym.exported_scope = final_scope
            else:
                # import a.b.c
                # Define 'a', ensuring a->b->c chain exists
                parts = module_name.split('.')
                
                # Define top level name
                top_name = parts[0]
                # Check if already defined to avoid overwriting existing symbol
                curr_sym = self.scope_manager.resolve(top_name)
                if not curr_sym:
                    curr_sym = self.scope_manager.define(top_name, SymbolType.MODULE)
                
                # We need to ensure current_sym has a scope (to hold 'b')
                if not curr_sym.exported_scope:
                    # Try to resolve 'a' scope directly
                    curr_sym.exported_scope = self._resolve_module_scope(top_name, node)
                    if not curr_sym.exported_scope:
                            # Create dummy scope if not found
                            curr_sym.exported_scope = ScopeNode(ScopeType.GLOBAL)
                            
                curr_scope = curr_sym.exported_scope
                
                # Path so far
                path_prefix = top_name
                
                # Traverse/Create the rest: b, c
                for part in parts[1:]:
                    path_prefix += "." + part
                    
                    # Look for 'part' in curr_scope
                    sub_sym = curr_scope.resolve(part)
                    if not sub_sym:
                        sub_sym = curr_scope.define(part, SymbolType.MODULE)
                        
                    # Ensure sub_sym has scope
                    if not sub_sym.exported_scope:
                        sub_sym.exported_scope = self._resolve_module_scope(path_prefix, node)
                        if not sub_sym.exported_scope:
                            sub_sym.exported_scope = ScopeNode(ScopeType.GLOBAL)
                            
                    curr_scope = sub_sym.exported_scope
                    
        return node

    def parse_from_import(self) -> ast.ImportFrom:
        """Parses 'from .a import b'."""
        start_token = self.stream.previous() # 'from' already consumed
        
        # Handle relative imports: from . import x, from ..foo import x
        level = 0
        while self.stream.match(TokenType.DOT):
            level += 1
            
        module_name = None
        if self.stream.check(TokenType.IDENTIFIER):
            module_name = self.parse_dotted_name()
            
        self.stream.consume(TokenType.IMPORT, "Expect 'import'.")
        names = self.parse_aliases()
        
        self.stream.consume_end_of_statement("Expect newline after import.")
        node = self._loc(ast.ImportFrom(module=module_name, names=names, level=level), start_token)
        
        # Registration Logic
        full_module_name = self._resolve_relative_module_name(node.module, node.level, node)
        module_scope = self._resolve_module_scope(full_module_name, node)
        
        for alias_node in node.names:
            name = alias_node.name
            asname = alias_node.asname or name
            
            # Define in current scope
            sym_type = SymbolType.VARIABLE
            exported_scope = None
            origin_sym = None
            
            if module_scope:
                # Look up in module scope
                origin_sym = module_scope.resolve(name)
                if origin_sym:
                    sym_type = origin_sym.type
                    exported_scope = origin_sym.exported_scope
                else:
                    # Symbol not found in module
                    # self.issue_tracker.report(Severity.ERROR, "DEP_IMPORT_ERROR", f"Cannot import name '{name}' from '{full_module_name}'", start_token)
                    # For now, allow it (maybe dynamic?), but warning or error depending on strictness.
                    # Original code had error.
                    pass
                    
            sym = self.scope_manager.define(asname, sym_type)
            sym.exported_scope = exported_scope
            
            # Store reference to origin for lazy type resolution in semantic analysis
            sym.origin_symbol = origin_sym 
            
            if origin_sym:
                sym.type_info = origin_sym.type_info
                
        return node

    def parse_aliases(self) -> List[ast.alias]:
        aliases = []
        while True:
            start = self.stream.peek()
            
            if self.stream.match(TokenType.STAR):
                aliases.append(self._loc(ast.alias(name='*', asname=None), start))
            else:
                name = self.parse_dotted_name()
                asname = None
                
                # Check for 'as' keyword
                if self.stream.match(TokenType.AS):
                    asname = self.stream.consume(TokenType.IDENTIFIER, "Expect alias name.").value
                
                aliases.append(self._loc(ast.alias(name=name, asname=asname), start))
            
            if not self.stream.match(TokenType.COMMA):
                break
        return aliases

    def parse_dotted_name(self) -> str:
        name = self.stream.consume(TokenType.IDENTIFIER, "Expect identifier.").value
        while self.stream.match(TokenType.DOT):
            name += "." + self.stream.consume(TokenType.IDENTIFIER, "Expect identifier after '.'.").value
        return name

    def _resolve_relative_module_name(self, module_name: Optional[str], level: int, context_node: Optional[ast.ASTNode] = None) -> str:
        """Resolve relative module name (e.g. .math) to absolute module name."""
        if level == 0:
            return module_name or ""
            
        if not self.context.package_name:
            # Fallback for root package
            return module_name or ""
            
        parts = self.context.package_name.split('.')
        if level > len(parts) + 1:
             # Error: Attempted relative import beyond top-level package
             self.issue_tracker.report(
                 Severity.ERROR, 
                 DEP_INVALID_IMPORT_POSITION, 
                 f"Relative import level ({level}) exceeds package depth", 
                 context_node
             )
             return ""
        
        parent_parts = parts[:len(parts) - level]
        parent_package = ".".join(parent_parts)
        
        if module_name:
            return f"{parent_package}.{module_name}" if parent_package else module_name
        else:
            return parent_package

    def _resolve_module_scope(self, module_name: str, context_node: Optional[ast.ASTNode] = None) -> Optional[ScopeNode]:
        """Resolve module name to ScopeNode using Resolver and Cache."""
        # 1. Try to resolve to path if resolver exists
        resolved_path = None
        if self.context.module_resolver:
             try:
                 resolved_path = self.context.module_resolver.resolve(module_name)
             except Exception as e:
                 # Check if it is a namespace package (directory without init file)
                 if self.context.module_resolver.is_package_dir(module_name):
                     # It's a valid directory, so we treat it as a namespace package.
                     # We return None here, and the caller will create a dummy scope.
                     return None

                 # Report error if module resolution fails
                 self.issue_tracker.report(
                     Severity.ERROR,
                     DEP_MODULE_NOT_FOUND,
                     f"Failed to resolve module '{module_name}': {str(e)}",
                     context_node
                 )
                 return None
        
        # 2. Look up in cache
        # Cache might be keyed by path or name.
        if resolved_path and resolved_path in self.context.module_cache:
            return self.context.module_cache[resolved_path]
            
        if module_name in self.context.module_cache:
            return self.context.module_cache[module_name]
            
        return None
