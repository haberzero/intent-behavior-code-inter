
from typing import Dict, Optional, List, Any
import re
from core.types import parser_types as ast
from core.types.symbol_types import Symbol, SymbolType
from core.types.exception_types import SemanticError
from core.types.diagnostic_types import Diagnostic, Severity, CompilerError, Location
from core.types.scope_types import ScopeType, ScopeNode
from core.compiler.parser.symbol_table import ScopeManager
from core.support.diagnostics.issue_tracker import IssueTracker
from core.support.diagnostics.codes import (
    SEM_UNDEFINED_SYMBOL, SEM_REDEFINITION, SEM_TYPE_MISMATCH
)
from core.support.diagnostics.core_debugger import CoreModule, DebugLevel, core_debugger

from core.compiler.semantic.types import (
    Type, PrimitiveType, AnyType, ListType, DictType, FunctionType, ModuleType,
    UserDefinedType, CallableType,
    INT_TYPE, FLOAT_TYPE, STR_TYPE, BOOL_TYPE, VOID_TYPE, ANY_TYPE,
    get_builtin_type
)

from core.compiler.semantic.prelude import Prelude
from core.support.host_interface import HostInterface

class SemanticAnalyzer:
    """
    Performs semantic analysis and type checking on the AST.
    """
    def _init_builtins(self):
        """Register builtin functions and modules."""
        prelude = Prelude(self.host_interface)
        
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

    def __init__(self, issue_tracker: Optional[IssueTracker] = None, host_interface: Optional[HostInterface] = None, debugger: Optional[Any] = None):
        self.scope_manager = ScopeManager() 
        self.issue_tracker = issue_tracker or IssueTracker()
        self.host_interface = host_interface
        self.debugger = debugger or core_debugger
        
    def analyze(self, node: ast.ASTNode):
        self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.BASIC, "Starting semantic analysis...")
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
        
        self.debugger.trace(CoreModule.SEMANTIC, DebugLevel.BASIC, "Semantic analysis complete.")
        
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

    def error(self, message: str, node: ast.ASTNode, code: str = "SEMANTIC_ERROR"):
        self.issue_tracker.report(Severity.ERROR, code, message, location=node)


    # --- Scope Management ---
    
    def visit_Module(self, node: ast.Module):
        # Initialize current_return_type
        self.current_return_type = None
        # Global scope is already active in init
        for stmt in node.body:
            self.visit(stmt)

    def visit_ClassDef(self, node: ast.ClassDef):
        # 1. Register class in current scope
        class_symbol = self.scope_manager.resolve(node.name)
        if not class_symbol:
            class_symbol = self.scope_manager.define(node.name, SymbolType.USER_TYPE)
        
        # Attach type info to the symbol
        from core.compiler.semantic.types import UserDefinedType
        class_symbol.type_info = UserDefinedType(node.name, node.scope)
        
        # 2. Enter Class Scope
        if node.scope:
            self.scope_manager.current_scope = node.scope
        else:
            self.scope_manager.enter_scope(ScopeType.CLASS)
            
        # 3. Visit class body
        for stmt in node.body:
            self.visit(stmt)
            
        # 4. Exit Class Scope
        if node.scope and node.scope.parent:
            self.scope_manager.current_scope = node.scope.parent
        else:
            self.scope_manager.exit_scope()

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
        
        # Check expressions in sys_prompt and user_prompt
        for prompt_segments in [node.sys_prompt, node.user_prompt]:
            if prompt_segments:
                for segment in prompt_segments:
                    if isinstance(segment, ast.Expr):
                        # Special check for Name to provide better error message for tests
                        if isinstance(segment, ast.Name):
                             symbol = self.scope_manager.resolve(segment.id)
                             if not symbol:
                                 self.error(f"Parameter '{segment.id}' used in LLM prompt is not defined", node)
                                 continue
                        self.visit(segment)
        
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
                        # [SPECIAL CASE] Allow BehaviorExpr to be assigned to 'callable'
                        if isinstance(declared_type, CallableType) and isinstance(node.value, ast.BehaviorExpr):
                            # This will be handled as a Lambda in the Interpreter
                            pass
                        # [FIX]: Type Inference for 'var' (AnyType)
                        elif isinstance(declared_type, AnyType) and val_type != VOID_TYPE:
                            symbol.type_info = val_type
                        elif not val_type.is_assignable_to(declared_type):
                            self.error(f"Type mismatch: Cannot assign '{val_type}' to '{declared_type}'", node, code=SEM_TYPE_MISMATCH)
            else:
                self.error("Invalid assignment target for declaration", node)
        else:
            # Reassignment: x = val
            if isinstance(target, ast.Name):
                var_name = target.id
                symbol = self.scope_manager.resolve(var_name)
                if not symbol:
                    self.error(f"Variable '{var_name}' is not defined", node, code=SEM_UNDEFINED_SYMBOL)
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
                            self.error(f"Type mismatch: Cannot assign '{val_type}' to '{symbol.type_info}'", node, code=SEM_TYPE_MISMATCH)
            elif isinstance(target, ast.Attribute):
                # Attribute assignment: obj.attr = val
                attr_type = self.visit(target)
                if node.value:
                    val_type = self.visit(node.value)
                    if attr_type and val_type and not val_type.is_assignable_to(attr_type):
                        self.error(f"Type mismatch: Cannot assign '{val_type}' to attribute of type '{attr_type}'", node, code=SEM_TYPE_MISMATCH)
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

    def visit_If(self, node: ast.If):
        self.visit(node.test)
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)
        if node.llm_fallback:
            for stmt in node.llm_fallback:
                self.visit(stmt)

    def visit_While(self, node: ast.While):
        self.visit(node.test)
        for stmt in node.body:
            self.visit(stmt)
        if node.llm_fallback:
            for stmt in node.llm_fallback:
                self.visit(stmt)

    def visit_For(self, node: ast.For):
        # Visit iterator
        self.visit(node.iter)
        
        # Enter loop scope
        self.scope_manager.enter_scope(ScopeType.BLOCK)
        
        if node.target:
            if isinstance(node.target, ast.Name):
                # Define loop variable
                if not self.scope_manager.current_scope.resolve(node.target.id):
                    sym = self.scope_manager.define(node.target.id, SymbolType.VARIABLE)
                    sym.type_info = ANY_TYPE
            else:
                self.visit(node.target)
                
        for stmt in node.body:
            self.visit(stmt)
            
        if node.llm_fallback:
            for stmt in node.llm_fallback:
                self.visit(stmt)
                
        self.scope_manager.exit_scope()

    def visit_Try(self, node: ast.Try):
        for stmt in node.body:
            self.visit(stmt)
        for handler in node.handlers:
            self.visit(handler)
        for stmt in node.orelse:
            self.visit(stmt)
        for stmt in node.finalbody:
            self.visit(stmt)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if node.type:
            self.visit(node.type)
        
        if node.name:
            self.scope_manager.enter_scope(ScopeType.BLOCK)
            self.scope_manager.define(node.name, SymbolType.VARIABLE)
            for stmt in node.body:
                self.visit(stmt)
            self.scope_manager.exit_scope()
        else:
            for stmt in node.body:
                self.visit(stmt)

    def visit_Raise(self, node: ast.Raise):
        if node.exc:
            self.visit(node.exc)

    def visit_Call(self, node: ast.Call) -> Type:
        func_type = self.visit(node.func)
        
        if isinstance(func_type, AnyType):
            return ANY_TYPE
            
        from core.compiler.semantic.types import UserDefinedType
        if isinstance(func_type, UserDefinedType):
            # Class instantiation: e.g. Person("Alice")
            # Returns an instance of that class
            return func_type
            
        # Determine if it's a normal function or a generic callable
        if not isinstance(func_type, (FunctionType, CallableType)):
            self.error(f"Expression of type '{func_type}' is not callable", node)
            return ANY_TYPE # Fallback
            
        if isinstance(func_type, CallableType):
            # Generic callable, we don't know the exact signature or return type at compile time.
            # Assume it's Any for now.
            for arg in node.args:
                self.visit(arg)
            return ANY_TYPE

        # Check arguments
        param_types = func_type.param_types
        
        # [NEW]: If it's a method call, skip the 'self' parameter check
        if isinstance(node.func, ast.Attribute):
            obj_type = self.visit(node.func.value)
            if isinstance(obj_type, UserDefinedType):
                # It is a method call on a class instance
                if len(param_types) > 0:
                    param_types = param_types[1:]
        
        if len(node.args) != len(param_types):
            self.error(f"Argument count mismatch: expected {len(param_types)}, got {len(node.args)}", node)
            return ANY_TYPE # Stop checking args
            
        for i, arg in enumerate(node.args):
            arg_type = self.visit(arg)
            expected_type = param_types[i]
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
                self.error(f"Variable '{node.id}' is not defined", node, code=SEM_UNDEFINED_SYMBOL)
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
        
        if isinstance(value_type, UserDefinedType):
            # It is a class instance access
            if value_type.scope:
                attr_sym = value_type.scope.resolve(node.attr)
                if attr_sym:
                    # Found in class scope
                    if attr_sym.type_info is None and attr_sym.declared_type_node:
                         # Handle both node and token list for lazy resolution
                         if isinstance(attr_sym.declared_type_node, list):
                             attr_sym.type_info = self._resolve_type_from_tokens(attr_sym.declared_type_node)
                         else:
                             attr_sym.type_info = self._resolve_type(attr_sym.declared_type_node)
                    return attr_sym.type_info or ANY_TYPE
            
            # If not found in scope, it might be a dynamic property or error
            if value_type.scope:
                self.error(f"Class '{value_type.class_name}' has no attribute '{node.attr}'", node)
            return ANY_TYPE

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
        
        from core.compiler.semantic.types import get_promoted_type
        result_type = get_promoted_type(node.op, left_type, right_type)
        
        if result_type is None:
            self.error(f"Binary operator '{node.op}' not supported for types '{left_type}' and '{right_type}'", node)
            return ANY_TYPE
            
        return result_type

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Type:
        operand_type = self.visit(node.operand)
        
        if isinstance(operand_type, AnyType):
            return ANY_TYPE
            
        if node.op == 'not':
            return BOOL_TYPE
        
        if node.op == '~':
            if operand_type == INT_TYPE:
                return INT_TYPE
            self.error(f"Unary operator '~' not supported for type '{operand_type}'", node)
            return ANY_TYPE
            
        if node.op in ('+', '-'):
            if operand_type in (INT_TYPE, FLOAT_TYPE):
                return operand_type
            self.error(f"Unary operator '{node.op}' not supported for type '{operand_type}'", node)
            return ANY_TYPE
            
        return ANY_TYPE

    def visit_Compare(self, node: ast.Compare) -> Type:
        left_type = self.visit(node.left)
        from core.compiler.semantic.types import get_promoted_type
        
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
        for segment in node.segments:
            if isinstance(segment, ast.Expr):
                # 为了保持测试兼容性，对未定义变量提供特定的错误信息
                if isinstance(segment, ast.Name):
                    symbol = self.scope_manager.resolve(segment.id)
                    if not symbol:
                        self.error(f"Variable '{segment.id}' used in behavior expression is not defined", segment)
                        continue
                self.visit(segment)
        
        # 行为描述行本质上是动态 LLM 调用，其返回类型在运行时确定。
        # 为了支持 int x = @~...~ 这种语法，我们在语义分析阶段将其视为 ANY_TYPE。
        return ANY_TYPE

    # --- Helpers ---

    def _resolve_type_from_tokens(self, tokens: List[Any]) -> Type:
        if not tokens:
            return ANY_TYPE
            
        from core.compiler.parser.core.token_stream import TokenStream
        from core.compiler.parser.core.context import ParserContext
        from core.compiler.parser.components.type_def import TypeComponent
        
        # Create a temporary parser context to parse the type annotation
        temp_stream = TokenStream(tokens, self.issue_tracker)
        # Pass the current scope_manager to ensure user-defined types are resolvable
        temp_context = ParserContext(temp_stream, self.issue_tracker, scope_manager=self.scope_manager)
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
            
            # [NEW]: Check for user-defined types in symbol table
            symbol = self.scope_manager.resolve(node.id)
            if symbol and symbol.type == SymbolType.USER_TYPE:
                return UserDefinedType(node.id, symbol.exported_scope)
            
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
