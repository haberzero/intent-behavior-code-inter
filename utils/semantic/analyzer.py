from typing import Dict, Any, Optional, List
from typedef import parser_types as ast
from typedef.exception_types import SemanticError
from .types import Type, AnyType, VoidType, PrimitiveType, ListType, DictType, FunctionType
from .symbol_table import SymbolTable, Symbol, SymbolKind

class SemanticAnalyzer:
    def __init__(self):
        self.symbol_table = SymbolTable()

    def analyze(self, node: ast.ASTNode):
        method_name = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ast.ASTNode):
        if hasattr(node, '__dict__'):
            for key, value in node.__dict__.items():
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, ast.ASTNode):
                            self.analyze(item)
                elif isinstance(value, ast.ASTNode):
                    self.analyze(value)

    def visit_Module(self, node: ast.Module):
        for stmt in node.body:
            self.analyze(stmt)

    def visit_Assign(self, node: ast.Assign):
        # 1. Analyze value expression to infer its type
        value_type = self.analyze(node.value) if node.value else None
        
        for target in node.targets:
            if isinstance(target, ast.Name):
                name = target.id
                
                if node.type_annotation:
                    # Declaration: int x = 10
                    # 1. Resolve declared type
                    declared_type = self._resolve_type_node(node.type_annotation)
                    
                    # 2. Check for builtin protection / redeclaration
                    # We check if 'name' is already a builtin symbol
                    existing = self.symbol_table.current_scope.resolve(name)
                    if existing and existing.is_builtin:
                        raise SemanticError(f"Cannot reassign built-in symbol '{name}'", node)

                    # 3. Type Compatibility Check
                    if value_type and not isinstance(declared_type, AnyType):
                         if not self._is_type_compatible(declared_type, value_type):
                             raise SemanticError(f"Type mismatch: Variable '{name}' declared as {declared_type} but assigned {value_type}", node)
                    
                    # 4. Define in scope
                    symbol = Symbol(name, SymbolKind.VARIABLE, declared_type)
                    self.symbol_table.current_scope.define(symbol)
                    
                else:
                    # Reassignment: x = 10
                    symbol = self.symbol_table.current_scope.resolve(name)
                    if not symbol:
                        # Check if it's a new variable declaration using type inference (implicit var)
                        # IBC design might require 'var' keyword.
                        # If user writes 'x = 10', is it allowed if x is new?
                        # Based on test_undefined_variable, it seems NO.
                        raise SemanticError(f"Variable '{name}' is not defined", node)
                    
                    if symbol.is_builtin:
                        raise SemanticError(f"Cannot reassign built-in symbol '{name}'", node)
                        
                    if symbol.kind != SymbolKind.VARIABLE:
                         raise SemanticError(f"Cannot assign to {symbol.kind.name.lower()} '{name}'", node)
                    
                    # Type Check
                    if value_type and not isinstance(symbol.type_info, AnyType):
                         if not self._is_type_compatible(symbol.type_info, value_type):
                             raise SemanticError(f"Type mismatch: Variable '{name}' is {symbol.type_info} but assigned {value_type}", node)

            elif isinstance(target, ast.Subscript):
                self.analyze(target) # Check if container exists etc.
                # TODO: Check if value matches container element type
            elif isinstance(target, ast.Attribute):
                self.analyze(target)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        name = node.name
        
        # Check builtin protection
        existing = self.symbol_table.current_scope.resolve(name)
        if existing and existing.is_builtin:
             raise SemanticError(f"Cannot redefine built-in function '{name}'", node)

        # Resolve return type
        return_type = VoidType()
        if node.returns:
            return_type = self._resolve_type_node(node.returns)
            
        # Resolve param types to build FunctionType
        # We need to temporarily enter a scope to resolve param types? 
        # No, param types should be resolved in the outer scope (e.g. List[int])
        # But parameter NAMES are defined in the inner scope.
        
        param_types = []
        for arg in node.args:
            if arg.annotation:
                param_types.append(self._resolve_type_node(arg.annotation))
            else:
                param_types.append(AnyType())
                
        func_type = FunctionType(param_types, return_type)
        func_symbol = Symbol(name, SymbolKind.FUNCTION, func_type)
        self.symbol_table.current_scope.define(func_symbol)
        
        # Enter Function Scope
        self.symbol_table.enter_scope(name=f"func_{name}")
        
        # Define parameters in local scope
        for i, arg in enumerate(node.args):
            p_type = param_types[i]
            self.symbol_table.current_scope.define(Symbol(arg.arg, SymbolKind.VARIABLE, p_type))
            
        # Analyze body
        for stmt in node.body:
            self.analyze(stmt)
            
        self.symbol_table.exit_scope()

    def visit_Name(self, node: ast.Name):
        if node.ctx == 'Load':
            symbol = self.symbol_table.current_scope.resolve(node.id)
            if not symbol:
                raise SemanticError(f"Name '{node.id}' is not defined", node)
            
            # If it's a variable, return its type
            if symbol.kind == SymbolKind.VARIABLE:
                return symbol.type_info
            # If it's a function, return the FunctionType
            if symbol.kind == SymbolKind.FUNCTION:
                return symbol.type_info
            # If it's a type (e.g. 'int'), return the Type object itself?
            # Or a TypeType? For now, return the Type object.
            if symbol.kind == SymbolKind.TYPE:
                return symbol.type_info # This is a Type object (e.g. PrimitiveType('int'))
                
        return AnyType()

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, bool): return PrimitiveType('bool')
        if isinstance(node.value, int): return PrimitiveType('int')
        if isinstance(node.value, float): return PrimitiveType('float')
        if isinstance(node.value, str): return PrimitiveType('str')
        if node.value is None: return VoidType()
        return AnyType()

    def visit_BinOp(self, node: ast.BinOp):
        left_type = self.analyze(node.left)
        right_type = self.analyze(node.right)
        
        # Helper to check primitive types
        def is_prim(t, name): return isinstance(t, PrimitiveType) and t.name == name
        
        # String concatenation
        if node.op == '+':
             if is_prim(left_type, 'str') and is_prim(right_type, 'str'): return PrimitiveType('str')
        
        if is_prim(left_type, 'int') and is_prim(right_type, 'int'): return PrimitiveType('int')
        
        if (is_prim(left_type, 'float') or is_prim(right_type, 'float')) and \
           (isinstance(left_type, PrimitiveType) and left_type.name in ('int', 'float')) and \
           (isinstance(right_type, PrimitiveType) and right_type.name in ('int', 'float')):
            return PrimitiveType('float')
        
        if isinstance(left_type, AnyType) or isinstance(right_type, AnyType):
            return AnyType()
            
        raise SemanticError(f"Binary operator '{node.op}' not supported for types {left_type} and {right_type}", node)

    def visit_Call(self, node: ast.Call):
        callee_type = self.analyze(node.func)
        
        # Case 1: Calling a Type (Constructor/Cast)
        if isinstance(callee_type, Type) and not isinstance(callee_type, FunctionType):
            # E.g. int("123") -> callee_type is PrimitiveType('int')
            # The result of calling a Type is an instance of that Type.
            return callee_type
            
        # Case 2: Calling a Function
        if isinstance(callee_type, FunctionType):
            # TODO: Check argument count and types against callee_type.param_types
            return callee_type.return_type
            
        if isinstance(callee_type, AnyType):
            return AnyType()
            
        raise SemanticError(f"Expression of type {callee_type} is not callable", node)

    def _resolve_type_node(self, node: ast.ASTNode) -> Type:
        """
        Converts an AST node (Name, Subscript) into a Type object.
        Resolves type names using the symbol table.
        """
        if isinstance(node, ast.Name):
            # Simple type: int, str, var
            if node.id == 'var':
                return AnyType()
            
            symbol = self.symbol_table.current_scope.resolve(node.id)
            if not symbol:
                raise SemanticError(f"Unknown type '{node.id}'", node)
            if symbol.kind != SymbolKind.TYPE:
                raise SemanticError(f"'{node.id}' is not a type", node)
            
            return symbol.type_info # Should be a Type instance
            
        if isinstance(node, ast.Subscript):
            # Generic type: List[int]
            # node.value is the container type name (e.g. List)
            # node.slice is the element type (e.g. int)
            
            container_type = self._resolve_type_node(node.value)
            
            # Since we don't have a full GenericType definition in symbol table yet,
            # we check names manually or assume standard generics.
            # In a full system, 'List' symbol would store info that it takes 1 type param.
            
            if isinstance(container_type, PrimitiveType) and container_type.name == 'list':
                # It's a list
                element_type = self._resolve_type_node(node.slice)
                return ListType(element_type)
                
            if isinstance(container_type, PrimitiveType) and container_type.name == 'dict':
                # It's a dict. slice might be a Tuple/ListExpr if multiple args?
                # parser_types says slice is Expr. 
                # If Dict[str, int], parser might produce Tuple/ListExpr for slice?
                # For now assuming slice is one type.
                # Actually, standard python parser produces Tuple for multi-arg subscript.
                # My parser produces ListExpr if multiple args in brackets.
                
                key_type = AnyType()
                val_type = AnyType()
                
                if isinstance(node.slice, ast.ListExpr):
                    if len(node.slice.elts) >= 2:
                        key_type = self._resolve_type_node(node.slice.elts[0])
                        val_type = self._resolve_type_node(node.slice.elts[1])
                else:
                    # Maybe just one arg provided?
                    pass
                    
                return DictType(key_type, val_type)

            return container_type

        return AnyType()

    def _is_type_compatible(self, target: Type, value: Type) -> bool:
        if isinstance(target, AnyType) or isinstance(value, AnyType):
            return True
        if isinstance(target, VoidType) or isinstance(value, VoidType):
            return False
            
        if isinstance(target, PrimitiveType) and isinstance(value, PrimitiveType):
            if target.name == value.name: return True
            if target.name == 'float' and value.name == 'int': return True
            return False
            
        # Check List compatibility
        if isinstance(target, ListType) and isinstance(value, ListType):
             return self._is_type_compatible(target.element_type, value.element_type)
        
        # Check Dict compatibility
        if isinstance(target, DictType) and isinstance(value, DictType):
             return self._is_type_compatible(target.key_type, value.key_type) and \
                    self._is_type_compatible(target.value_type, value.value_type)

        return str(target) == str(value)
