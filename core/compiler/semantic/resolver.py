from typing import List, Optional, Any
from core.types import parser_types as ast
from . import symbols
from .symbols import (
    SymbolTable, TypeSymbol, FunctionSymbol, StaticType, ClassType, FunctionType,
    STATIC_VOID, STATIC_STR, STATIC_ANY
)
from .types import get_builtin_type

class TypeResolver:
    """
    第二阶段：类型决议 (Pass 2)
    解析继承关系、函数签名以及成员类型。
    填充 Pass 1 中收集的静态符号的类型信息。
    """
    def __init__(self, symbol_table: SymbolTable, semantic_analyzer: Any):
        self.symbol_table = symbol_table
        self.analyzer = semantic_analyzer
        self.current_class_type: Optional[ClassType] = None

    def resolve(self, node: ast.ASTNode):
        self.visit(node)

    def visit(self, node: ast.ASTNode):
        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ast.ASTNode):
        # 仅访问声明类节点和赋值节点（以推导全局变量类型）
        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.LLMFunctionDef, ast.Assign)):
                        self.visit(item)
            elif isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.LLMFunctionDef, ast.Assign)):
                self.visit(child)

    def visit_Module(self, node: ast.Module):
        for stmt in node.body:
            if isinstance(stmt, (ast.ClassDef, ast.FunctionDef, ast.LLMFunctionDef, ast.Assign)):
                self.visit(stmt)

    def visit_ClassDef(self, node: ast.ClassDef):
        sym = self.symbol_table.resolve(node.name)
        if not isinstance(sym, TypeSymbol):
            return

        # 1. 解析继承
        parent_type = None
        if node.parent:
            if node.parent == node.name:
                self.analyzer.error(f"Class '{node.name}' cannot inherit from itself", node)
            else:
                parent_sym = self.symbol_table.resolve(node.parent)
                if parent_sym and parent_sym.type_info.is_class:
                    # 检查循环继承
                    curr_parent = parent_sym.type_info
                    is_cycle = False
                    while curr_parent:
                        if curr_parent.name == node.name:
                            is_cycle = True
                            break
                        curr_parent = curr_parent.parent
                    
                    if is_cycle:
                        self.analyzer.error(f"Circular inheritance detected: '{node.name}' inherits from '{node.parent}'", node)
                    else:
                        parent_type = parent_sym.type_info
                else:
                    self.analyzer.error(f"Base class '{node.parent}' is not defined or not a class", node)
        
        # 2. 创建 ClassType 并绑定到符号
        class_scope = sym.owned_scope
        class_type = ClassType(name=node.name, parent=parent_type, scope=class_scope)
        sym.static_type = class_type
        node.inferred_type = class_type

        # 3. 解析成员（方法/字段）
        old_table = self.symbol_table
        if sym.owned_scope:
            self.symbol_table = sym.owned_scope
            
        old_class = self.current_class_type
        self.current_class_type = class_type
        try:
            for stmt in node.body:
                if isinstance(stmt, (ast.FunctionDef, ast.LLMFunctionDef, ast.Assign)):
                    self.visit(stmt)
        finally:
            self.current_class_type = old_class
            self.symbol_table = old_table

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # 解析返回类型
        ret_type = STATIC_VOID
        if node.returns:
            ret_type = self.analyzer._resolve_type(node.returns)
            
        # 解析参数类型
        param_types = []
        
        # [NEW] 隐式 self 注入：如果是类方法，在参数签名首位注入 self 类型
        if self.current_class_type:
            param_types.append(self.current_class_type)
            
        for arg in node.args:
            arg_type = STATIC_ANY
            if arg.annotation:
                arg_type = self.analyzer._resolve_type(arg.annotation)
            param_types.append(arg_type)
            
        # 绑定到符号
        sym = self.symbol_table.resolve(node.name)
        if isinstance(sym, FunctionSymbol):
            sym.type_signature = FunctionType(name=node.name, param_types=param_types, return_type=ret_type)

    def visit_LLMFunctionDef(self, node: ast.LLMFunctionDef):
        # LLM 函数默认返回 string
        ret_type = STATIC_STR
        if node.returns:
            ret_type = self.analyzer._resolve_type(node.returns)
            
        param_types = []
        
        # [NEW] 隐式 self 注入
        if self.current_class_type:
            param_types.append(self.current_class_type)
            
        for arg in node.args:
            arg_type = STATIC_ANY
            if arg.annotation:
                arg_type = self.analyzer._resolve_type(arg.annotation)
            param_types.append(arg_type)
            
        sym = self.symbol_table.resolve(node.name)
        if isinstance(sym, FunctionSymbol):
            sym.type_signature = FunctionType(name=node.name, param_types=param_types, return_type=ret_type)

    def visit_Assign(self, node: ast.Assign):
        # 处理类字段声明
        if node.type_annotation:
            declared_type = self.analyzer._resolve_type(node.type_annotation)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    sym = self.symbol_table.resolve(target.id)
                    if isinstance(sym, symbols.VariableSymbol):
                        sym.var_type = declared_type
