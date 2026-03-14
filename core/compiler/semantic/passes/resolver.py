from typing import List, Optional, Any, TYPE_CHECKING
from core.domain import ast as ast
from core.domain import symbols
from core.domain.symbols import SymbolTable, TypeSymbol, FunctionSymbol
from core.domain.types.descriptors import (
    TypeDescriptor, ClassMetadata, FunctionMetadata,
    VOID_DESCRIPTOR, STR_DESCRIPTOR, ANY_DESCRIPTOR
)
from core.domain import types as uts

if TYPE_CHECKING:
    from .semantic_analyzer import SemanticAnalyzer

class TypeResolver:
    """
    第二阶段：类型决议 (Pass 2)
    解析继承关系、函数签名以及成员类型。
    填充 Pass 1 中收集的静态符号的类型信息。
    """
    def __init__(self, symbol_table: SymbolTable, semantic_analyzer: 'SemanticAnalyzer'):
        self.symbol_table = symbol_table
        self.analyzer = semantic_analyzer
        self.current_class_descriptor: Optional[ClassMetadata] = None

    def resolve(self, node: ast.IbASTNode):
        self.visit(node)

    def visit(self, node: ast.IbASTNode):
        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        res_type = visitor(node)
        
        # [NEW Phase 5] 记录类型推导侧表
        if isinstance(node, ast.IbExpr) and res_type:
            self.analyzer.node_to_type[node] = res_type
        elif isinstance(node, ast.IbClassDef) and hasattr(self, "current_class_descriptor") and self.current_class_descriptor:
             # 对于类定义，我们记录它定义的类型
             self.analyzer.node_to_type[node] = self.current_class_descriptor
             
        return res_type

    def generic_visit(self, node: ast.IbASTNode):
        # 仅访问声明类节点和赋值节点（以推导全局变量类型）
        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, (ast.IbClassDef, ast.IbFunctionDef, ast.IbLLMFunctionDef, ast.IbAssign)):
                        self.visit(item)
            elif isinstance(child, (ast.IbClassDef, ast.IbFunctionDef, ast.IbLLMFunctionDef, ast.IbAssign)):
                self.visit(child)

    def visit_IbModule(self, node: ast.IbModule):
        for stmt in node.body:
            if isinstance(stmt, (ast.IbClassDef, ast.IbFunctionDef, ast.IbLLMFunctionDef, ast.IbAssign)):
                self.visit(stmt)

    def visit_IbClassDef(self, node: ast.IbClassDef):
        sym = self.symbol_table.resolve(node.name)
        if not isinstance(sym, symbols.TypeSymbol):
            return

        # 1. 解析继承
        parent_desc = None
        if node.parent:
            parent_sym = self.symbol_table.resolve(node.parent)
            if parent_sym and isinstance(parent_sym.type_info, ClassMetadata):
                parent_desc = parent_sym.type_info
            else:
                self.analyzer.error(f"Base class '{node.parent}' is not defined or not a class", node, code="SEM_001")
        
        # 2. 创建 ClassMetadata 并绑定到符号
        descriptor = uts.ClassMetadata(
            name=node.name, 
            parent_name=node.parent,
            parent_module=None # 暂时不支持跨模块
        )
        if parent_desc:
             descriptor.parent_name = parent_desc.name
        
        # [NEW Phase 5] 注册到元数据注册表，以便后续继承解析能找到它
        if self.analyzer.registry and hasattr(self.analyzer.registry, "_metadata_registry"):
            self.analyzer.registry._metadata_registry.register(descriptor)
             
        sym.descriptor = descriptor
        
        # 3. 解析成员
        old_class = self.current_class_descriptor
        self.current_class_descriptor = descriptor
        try:
            for stmt in node.body:
                if isinstance(stmt, (ast.IbFunctionDef, ast.IbLLMFunctionDef, ast.IbAssign)):
                    self.visit(stmt)
        finally:
            self.current_class_descriptor = old_class

    def visit_IbFunctionDef(self, node: ast.IbFunctionDef):
        # 解析返回类型
        ret_type = VOID_DESCRIPTOR
        if node.returns:
            ret_type = self.analyzer._resolve_type(node.returns)
            
        # 解析参数类型
        param_types = []
        # if self.current_class_descriptor:
        #     param_types.append(self.current_class_descriptor) # self param handling logic moved to BoundMethodMetadata
            
        for arg_node in node.args:
            arg_type = ANY_DESCRIPTOR
            if isinstance(arg_node, ast.IbTypeAnnotatedExpr):
                arg_type = self.analyzer._resolve_type(arg_node.annotation)
            param_types.append(arg_type)
            
        # 创建 FunctionMetadata 并注入到当前类的描述符中
        func_desc = uts.FunctionMetadata(
            name=node.name,
            param_types=param_types,
            return_type=ret_type
        )
        
        if self.current_class_descriptor:
            # [Axiom Hook] 同步到描述符的成员表中 (保持物理隔离下的元数据完备性)
            # 包装为符号对象，以满足语义分析器的接口需求
            self.current_class_descriptor.members[node.name] = symbols.FunctionSymbol(
                name=node.name,
                kind=symbols.SymbolKind.FUNCTION,
                descriptor=func_desc,
                def_node=node
            )
            
        # 绑定到符号
        sym = self.symbol_table.resolve(node.name)
        if isinstance(sym, symbols.FunctionSymbol):
            sym.descriptor = func_desc

    def visit_IbLLMFunctionDef(self, node: ast.IbLLMFunctionDef):
        # LLM 函数默认返回 string
        ret_type = STR_DESCRIPTOR
        if node.returns:
            ret_type = self.analyzer._resolve_type(node.returns)
            
        param_types = []
        # if self.current_class_descriptor:
        #     param_types.append(self.current_class_descriptor)
            
        for arg_node in node.args:
            arg_type = ANY_DESCRIPTOR
            if isinstance(arg_node, ast.IbTypeAnnotatedExpr):
                arg_type = self.analyzer._resolve_type(arg_node.annotation)
            param_types.append(arg_type)
            
        # 创建 FunctionMetadata
        func_desc = uts.FunctionMetadata(
            name=node.name,
            param_types=param_types,
            return_type=ret_type
        )
        
        if self.current_class_descriptor:
            # 包装为符号对象
            self.current_class_descriptor.members[node.name] = symbols.FunctionSymbol(
                name=node.name,
                kind=symbols.SymbolKind.LLM_FUNCTION,
                descriptor=func_desc,
                def_node=node,
                metadata={"is_llm": True}
            )

        sym = self.symbol_table.resolve(node.name)
        if isinstance(sym, symbols.FunctionSymbol):
            sym.descriptor = func_desc
            sym.metadata["is_llm"] = True

    def visit_IbAssign(self, node: ast.IbAssign):
        # 处理类字段声明
        for target in node.targets:
            if isinstance(target, ast.IbTypeAnnotatedExpr):
                declared_type = self.analyzer._resolve_type(target.annotation)
                if isinstance(target.target, ast.IbName):
                    name = target.target.id
                    # 注入到描述符
                    if self.current_class_descriptor:
                        # [Fix] 统一使用 Symbol 包装成员，以满足语义分析器的接口需求
                        self.current_class_descriptor.members[name] = symbols.VariableSymbol(
                            name=name,
                            kind=symbols.SymbolKind.VARIABLE,
                            descriptor=declared_type,
                            def_node=target
                        )
                    
                    sym = self.symbol_table.resolve(name)
                    if isinstance(sym, symbols.VariableSymbol):
                        sym.descriptor = declared_type
