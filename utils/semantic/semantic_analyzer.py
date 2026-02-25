
from typing import Dict, Optional, List, Any
import re
from typedef import parser_types as ast
from typedef.symbol_types import Symbol, SymbolType
from typedef.exception_types import SemanticError
from typedef.diagnostic_types import Diagnostic, Severity, CompilerError, Location
from typedef.scope_types import ScopeType, ScopeNode
from utils.parser.symbol_table import ScopeManager
from utils.diagnostics.issue_tracker import IssueTracker
from utils.semantic.types import (
    Type, PrimitiveType, AnyType, ListType, DictType, FunctionType, ModuleType,
    INT_TYPE, FLOAT_TYPE, STR_TYPE, BOOL_TYPE, VOID_TYPE, ANY_TYPE,
    get_builtin_type
)

from utils.semantic.prelude import Prelude

class SemanticAnalyzer:
    """
    Performs semantic analysis and type checking on the AST.
    """
    def _init_builtins(self):
        """Register builtin functions and modules."""
        prelude = Prelude()
        
        # 1. Functions
        for name, func_type in prelude.get_builtins().items():
            sym = self.scope_manager.global_scope.resolve(name)
            if not sym:
                sym = self.scope_manager.define(name, SymbolType.FUNCTION)
            sym.type_info = func_type

        # 2. Modules
        for name, mod_type in prelude.get_builtin_modules().items():
            sym = self.scope_manager.global_scope.resolve(name)
            if not sym:
                sym = self.scope_manager.define(name, SymbolType.MODULE)
            sym.type_info = mod_type
            sym.exported_scope = mod_type.scope

    def __init__(self, issue_tracker: Optional[IssueTracker] = None):
        self.scope_manager = ScopeManager() 
        self.issue_tracker = issue_tracker or IssueTracker()
        
    def analyze(self, node: ast.ASTNode):
        # Use the global scope attached to Module if available
        if isinstance(node, ast.Module) and node.scope:
            self.scope_manager.current_scope = node.scope
            self.scope_manager.global_scope = node.scope
            
            # Re-register builtins into this scope
            self._init_builtins()
        else:
            # Fallback: Use our own scope manager
            self._init_builtins()
            
        self.visit(node)
        
        self.issue_tracker.check_errors()

    def visit(self, node: ast.ASTNode):
        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ast.ASTNode):
        for child in node.__dict__.values():
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.ASTNode):
                        self.visit(item)
            elif isinstance(child, ast.ASTNode):
                self.visit(child)
        return ANY_TYPE

    def error(self, message: str, node: ast.ASTNode):
        self.issue_tracker.report(Severity.ERROR, "SEMANTIC_ERROR", message, location=node)


    # --- Scope Management ---
    
    def visit_Module(self, node: ast.Module):
        # Initialize current_return_type
        self.current_return_type = None
        # Global scope is already active in init
        for stmt in node.body:
            self.visit(stmt)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # 1. Register function in current scope (already handled by Parser/PreScanner, just fill types)
        
        # Resolve return type
        ret_type = VOID_TYPE
        if node.returns:
            ret_type = self._resolve_type(node.returns)
            
        param_types = []
        
        # We need to look up the function symbol in the current scope to update its type
        func_symbol = self.scope_manager.resolve(node.name)
        if not func_symbol:
            # Define it if missing (e.g. nested functions or global issues)
            func_symbol = self.scope_manager.define(node.name, SymbolType.FUNCTION)
            
        # 2. Enter function scope (Use the one attached to node)
        if node.scope:
            self.scope_manager.current_scope = node.scope
        else:
            # Fallback if scope missing (shouldn't happen)
            self.scope_manager.enter_scope(ScopeType.FUNCTION)
        
        # 3. Register parameters types
        for arg in node.args:
            arg_type = ANY_TYPE
            if arg.annotation:
                arg_type = self._resolve_type(arg.annotation)
            
            # Update symbol in current scope
            param_symbol = self.scope_manager.resolve(arg.arg)
            if not param_symbol:
                # Should exist, but define if not
                param_symbol = self.scope_manager.define(arg.arg, SymbolType.VARIABLE)
            
            param_symbol.type_info = arg_type
            param_types.append(arg_type)
            
        # Update function symbol with type info (FunctionType)
        if node.scope and node.scope.parent:
            outer_func_symbol = node.scope.parent.resolve(node.name)
            if outer_func_symbol:
                outer_func_symbol.type_info = FunctionType(param_types, ret_type)
        elif func_symbol: # Global or current scope fallback
            func_symbol.type_info = FunctionType(param_types, ret_type)
        
        # 4. Visit body
        # Track return type for return checking
        previous_ret_type = self.current_return_type
        self.current_return_type = ret_type
        
        for stmt in node.body:
            self.visit(stmt)
            
        self.current_return_type = previous_ret_type
            
        # Exit scope
        if node.scope and node.scope.parent:
            self.scope_manager.current_scope = node.scope.parent
        else:
            self.scope_manager.exit_scope()

    def visit_LLMFunctionDef(self, node: ast.LLMFunctionDef):
        ret_type = STR_TYPE
        if node.returns:
            ret_type = self._resolve_type(node.returns)
            
        param_types = []
        
        # Look up function symbol in current scope (before entering new scope)
        func_symbol = self.scope_manager.resolve(node.name)
        if not func_symbol:
            func_symbol = self.scope_manager.define(node.name, SymbolType.FUNCTION)
        
        # LLM functions also have a scope (for params)
        if node.scope:
            self.scope_manager.current_scope = node.scope
        else:
            self.scope_manager.enter_scope(ScopeType.FUNCTION)
        
        # Register parameters in the new scope
        for arg in node.args:
            arg_type = ANY_TYPE
            if arg.annotation:
                arg_type = self._resolve_type(arg.annotation)
            
            param_symbol = self.scope_manager.resolve(arg.arg)
            if not param_symbol:
                param_symbol = self.scope_manager.define(arg.arg, SymbolType.VARIABLE)
            
            param_symbol.type_info = arg_type
            param_types.append(arg_type)
            
        if node.scope and node.scope.parent:
            outer_func_symbol = node.scope.parent.resolve(node.name)
            if outer_func_symbol:
                outer_func_symbol.type_info = FunctionType(param_types, ret_type)
        elif func_symbol:
            func_symbol.type_info = FunctionType(param_types, ret_type)
        
        # LLM body is text, but we should check variable interpolations if possible.
        
        # Check placeholders in sys_prompt and user_prompt
        param_names = {arg.arg for arg in node.args}
        
        # Regex to find $__param__ pattern
        # Lexer already validated $__param__ format, so we can use simple regex
        # The value is $__name__
        placeholder_regex = re.compile(r'\$__(\w+)__')
        
        for prompt_node in [node.sys_prompt, node.user_prompt]:
            if prompt_node and isinstance(prompt_node.value, str):
                for match in placeholder_regex.finditer(prompt_node.value):
                    var_name = match.group(1)
                    if var_name not in param_names:
                        self.error(f"Parameter '{var_name}' used in LLM prompt is not defined in function arguments", node)
        
        if node.scope and node.scope.parent:
            self.scope_manager.current_scope = node.scope.parent
        else:
            self.scope_manager.exit_scope()

    # --- Statements ---
    
    def visit_Assign(self, node: ast.Assign):
        # Handle declarations vs assignments
        
        target = node.targets[0] # IBC-Inter only supports single target assignment
        
        if node.type_annotation:
            # Declaration: Type x = val
            declared_type = self._resolve_type(node.type_annotation)
            
            if isinstance(target, ast.Name):
                var_name = target.id
                # Symbol is ALREADY defined by Parser/PreScanner. We just need to FILL type info.
                symbol = self.scope_manager.resolve(var_name)
                
                # FALLBACK: If not found, and we are in global scope, define it.
                if not symbol and self.scope_manager.current_scope.depth == 0:
                    symbol = self.scope_manager.define(var_name, SymbolType.VARIABLE)
                
                if not symbol:
                    # Should not happen if Parser is correct and not global
                    self.error(f"Internal Error: Variable '{var_name}' not found in scope during declaration", node)
                    return

                symbol.type_info = declared_type
                
                # Check initial value
                if node.value:
                    val_type = self.visit(node.value)
                    if val_type is not None:
                        # [FIX]: Type Inference for 'var' (AnyType)
                        # If declared type is Any, try to infer from value.
                        if isinstance(declared_type, AnyType) and val_type != VOID_TYPE:
                            symbol.type_info = val_type
                        elif not val_type.is_assignable_to(declared_type):
                            self.error(f"Type mismatch: Cannot assign '{val_type}' to '{declared_type}'", node)
            else:
                self.error("Invalid assignment target for declaration", node)
        else:
            # Reassignment: x = val
            if isinstance(target, ast.Name):
                var_name = target.id
                symbol = self.scope_manager.resolve(var_name)
                if not symbol:
                    self.error(f"Variable '{var_name}' is not defined", node)
                    return
                
                # Check type compatibility
                if node.value:
                    val_type = self.visit(node.value)
                    
                    if symbol.type_info:
                        # If 'var' was previously inferred as Any (no init), now we can infer?
                        # Or if it was declared as 'var' and initialized, it has a type now.
                        # If it is STILL AnyType, we can update it?
                        if isinstance(symbol.type_info, AnyType) and val_type != VOID_TYPE:
                             symbol.type_info = val_type
                        elif val_type is not None and not val_type.is_assignable_to(symbol.type_info):
                            self.error(f"Type mismatch: Cannot assign '{val_type}' to '{symbol.type_info}'", node)
            else:
                # Subscript assignment etc.
                self.visit(target)
                if node.value:
                    self.visit(node.value)

    def visit_Return(self, node: ast.Return):
        # Explicit check if we are inside a function
        if self.current_return_type is None:
            self.error("Return statement outside of function", node)
            return

        expected = self.current_return_type
        
        if node.value:
            actual = self.visit(node.value)
            if actual is not None and not actual.is_assignable_to(expected):
                self.error(f"Invalid return type: expected '{expected}', got '{actual}'", node)
        else:
            if expected != VOID_TYPE and expected != ANY_TYPE:
                self.error(f"Missing return value: expected '{expected}'", node)

    def visit_ExprStmt(self, node: ast.ExprStmt):
        self.visit(node.value)

    def visit_Call(self, node: ast.Call) -> Type:
        # Resolve function type
        func_type = self.visit(node.func)
        
        if isinstance(func_type, AnyType):
            return ANY_TYPE
            
        if not isinstance(func_type, FunctionType):
            self.error(f"Expression of type '{func_type}' is not callable", node)
            return ANY_TYPE # Fallback
            
        # Check arguments
        if len(node.args) != len(func_type.param_types):
            self.error(f"Argument count mismatch: expected {len(func_type.param_types)}, got {len(node.args)}", node)
            return ANY_TYPE # Stop checking args
            
        for i, arg in enumerate(node.args):
            arg_type = self.visit(arg)
            expected_type = func_type.param_types[i]
            if arg_type is not None and not arg_type.is_assignable_to(expected_type):
                self.error(f"Argument {i+1} type mismatch: expected '{expected_type}', got '{arg_type}'", arg)
                
        return func_type.return_type

    def visit_Constant(self, node: ast.Constant) -> Type:
        val = node.value
        if isinstance(val, bool): return BOOL_TYPE
        if isinstance(val, int): return INT_TYPE
        if isinstance(val, float): return FLOAT_TYPE
        if isinstance(val, str): return STR_TYPE
        if val is None: return VOID_TYPE # Or NoneType
        return ANY_TYPE

    def visit_Name(self, node: ast.Name) -> Type:
        if node.ctx == 'Load':
            # Resolve starting from current scope
            symbol = self.scope_manager.resolve(node.id)
            if not symbol:
                self.error(f"Variable '{node.id}' is not defined", node)
                return ANY_TYPE
            
            if symbol.type == SymbolType.MODULE:
                 if symbol.exported_scope:
                     return ModuleType(symbol.exported_scope)
                 return ANY_TYPE # Module without scope?

            # [FIXED]: Lazy Type Resolution for Imported Symbols
            # If symbol.type_info is missing, but it's an imported symbol (has origin),
            # we should try to fetch the type from the origin scope NOW.
            
            if symbol.type_info is None:
                 if symbol.origin_symbol and symbol.origin_symbol.type_info:
                     symbol.type_info = symbol.origin_symbol.type_info
                 elif symbol.declared_type_node:
                     symbol.type_info = self._resolve_type(symbol.declared_type_node)
            
            return symbol.type_info or ANY_TYPE
        return ANY_TYPE

    def visit_Attribute(self, node: ast.Attribute) -> Type:
        # Check if value is a module or object
        # First visit the value (left side)
        
        value_type = self.visit(node.value)
        
        if isinstance(value_type, ModuleType):
             # It is a module/package
             module_scope = value_type.scope
             attr_sym = module_scope.resolve(node.attr)
             
             if not attr_sym:
                 # Try to resolve in exported scope for nested modules?
                 # If value_type.scope is a package scope, it might have exported modules.
                 pass
                 
             if not attr_sym:
                 self.error(f"Module/Package has no attribute '{node.attr}'", node)
                 return ANY_TYPE
                 
             if attr_sym.type == SymbolType.MODULE:
                 if attr_sym.exported_scope:
                     return ModuleType(attr_sym.exported_scope)
                 return ANY_TYPE
                 
             # [FIX]: Lazy resolution for attributes too!
             if attr_sym.type_info is None:
                  if attr_sym.origin_symbol and attr_sym.origin_symbol.type_info:
                      attr_sym.type_info = attr_sym.origin_symbol.type_info
                  elif attr_sym.declared_type_node:
                      attr_sym.type_info = self._resolve_type(attr_sym.declared_type_node)
                       
             return attr_sym.type_info or ANY_TYPE
        
        # Fallback for object attributes (not implemented fully)
        if isinstance(value_type, AnyType):
            return ANY_TYPE
            
        # TODO: Check class attributes when classes are implemented
        return ANY_TYPE

    def visit_BinOp(self, node: ast.BinOp) -> Type:
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)
        
        from utils.semantic.types import get_promoted_type
        result_type = get_promoted_type(node.op, left_type, right_type)
        
        if result_type is None:
            self.error(f"Binary operator '{node.op}' not supported for types '{left_type}' and '{right_type}'", node)
            return ANY_TYPE
            
        return result_type

    def visit_Compare(self, node: ast.Compare) -> Type:
        left_type = self.visit(node.left)
        from utils.semantic.types import get_promoted_type
        
        for op, comparator in zip(node.ops, node.comparators):
            right_type = self.visit(comparator)
            res = get_promoted_type(op, left_type, right_type)
            if res is None:
                 self.error(f"Comparison operator '{op}' not supported for types '{left_type}' and '{right_type}'", node)
            left_type = right_type
            
        return BOOL_TYPE

    def visit_ListExpr(self, node: ast.ListExpr) -> Type:
        # Infer element type
        if not node.elts:
            return ListType(ANY_TYPE)
            
        first_type = self.visit(node.elts[0])
        is_uniform = True
        for elt in node.elts[1:]:
            t = self.visit(elt)
            # Use stricter equality check for inference
            if t != first_type: 
                is_uniform = False
                break
        
        if is_uniform and first_type is not None:
            return ListType(first_type)
        return ListType(ANY_TYPE)

    def visit_BehaviorExpr(self, node: ast.BehaviorExpr) -> Type:
        # Check if variables referenced in the behavior expression exist in current scope
        for segment in node.segments:
            if isinstance(segment, ast.Name):
                symbol = self.scope_manager.resolve(segment.id)
                if not symbol:
                    self.error(f"Variable '{segment.id}' used in behavior expression is not defined", segment)
        
        return STR_TYPE # Behavior expressions return string content

    # --- Helpers ---

    def _resolve_type_from_tokens(self, tokens: List[Any]) -> Type:
        if not tokens:
            return ANY_TYPE
            
        from utils.parser.core.token_stream import TokenStream
        from utils.parser.core.context import ParserContext
        from utils.parser.components.type_def import TypeComponent
        
        # Create a temporary parser context to parse the type annotation
        temp_stream = TokenStream(tokens, self.issue_tracker)
        temp_context = ParserContext(temp_stream, self.issue_tracker)
        type_comp = TypeComponent(temp_context)
        
        try:
            type_node = type_comp.parse_type_annotation()
            return self._resolve_type(type_node)
        except Exception:
            return ANY_TYPE

    def _resolve_type(self, node: Any) -> Type:
        """
        Convert AST type annotation or Token list to Type object.
        """
        if isinstance(node, list):
            # It's a list of tokens from PreScanner
            return self._resolve_type_from_tokens(node)
            
        if isinstance(node, ast.Name):
            t = get_builtin_type(node.id)
            if t: return t
            
            # Check for prototype limitation: complex types
            # (Though Name is usually simple, we keep it for consistency)
            
            self.error(f"Unknown type '{node.id}'", node)
            
        elif isinstance(node, ast.Subscript):
            # Generic type: List[int]
            
            # PROTOTYPE HINT: Check for nested generics
            if isinstance(node.slice, ast.Subscript) or \
               (isinstance(node.slice, ast.ListExpr) and any(isinstance(e, ast.Subscript) for e in node.slice.elts)):
                self.issue_tracker.report(
                    Severity.HINT, "PROTO_LIMIT",
                    "IBC-Inter is in prototype stage. Nested generics (e.g., list[list[int]]) are not fully supported for type checking yet.",
                    node
                )
            
            base = self._resolve_type(node.value)
            
            # Extract args
            args = []
            if isinstance(node.slice, ast.ListExpr): # Multiple args
                for elt in node.slice.elts:
                    args.append(self._resolve_type(elt))
            else:
                args.append(self._resolve_type(node.slice))
                
            if isinstance(base, ListType): # Base is list[Any]
                return ListType(args[0])
            elif isinstance(base, DictType):
                if len(args) == 2:
                    return DictType(args[0], args[1])
                    
        return ANY_TYPE
