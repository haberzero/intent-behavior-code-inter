from typing import List, Optional, Any, TYPE_CHECKING
from core.kernel import ast as ast
from core.kernel import symbols
from core.kernel.symbols import SymbolTable, TypeSymbol, FunctionSymbol
from core.kernel.types.descriptors import (
    TypeDescriptor, ClassMetadata, FunctionMetadata,
    VOID_DESCRIPTOR, STR_DESCRIPTOR, ANY_DESCRIPTOR
)
from core.kernel import types as uts

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
        
        # 记录类型推导侧表
        if isinstance(node, ast.IbExpr) and res_type:
            self.analyzer.node_to_type[node] = res_type
        elif isinstance(node, ast.IbClassDef) and hasattr(self, "current_class_descriptor") and self.current_class_descriptor:
             # 对于类定义，我们记录它定义的类型
             self.analyzer.node_to_type[node] = self.current_class_descriptor
             
        return res_type

    def generic_visit(self, node: ast.IbASTNode):
        result_type = None

        # 遍历节点属性，访问子节点
        for attr in vars(node):
            child = getattr(node, attr)

            # 处理列表类型的子节点
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, (ast.IbClassDef, ast.IbFunctionDef, ast.IbLLMFunctionDef, ast.IbAssign)):
                        self.visit(item)
                    elif isinstance(item, ast.IbExpr):
                        item_type = self.visit(item)
                        if item_type:
                            result_type = item_type

            # 处理语句类型的子节点
            elif isinstance(child, (ast.IbClassDef, ast.IbFunctionDef, ast.IbLLMFunctionDef, ast.IbAssign)):
                self.visit(child)

            # 处理表达式类型的子节点（用于类型推导）
            elif isinstance(child, ast.IbExpr):
                item_type = self.visit(child)
                if item_type:
                    result_type = item_type

        return result_type

    def visit_IbModule(self, node: ast.IbModule):
        for stmt in node.body:
            if isinstance(stmt, (ast.IbClassDef, ast.IbFunctionDef, ast.IbLLMFunctionDef, ast.IbAssign)):
                self.visit(stmt)

    def visit_IbClassDef(self, node: ast.IbClassDef):
        sym = self.symbol_table.resolve(node.name)
        if not sym or not sym.is_type:
            return

        # 1. 解析继承
        parent_desc = None
        if node.parent:
            parent_sym = self.symbol_table.resolve(node.parent)
            # 使用 is_class() 代替 isinstance 检查
            if parent_sym and parent_sym.descriptor and parent_sym.descriptor.is_class():
                parent_desc = parent_sym.descriptor
            else:
                # [Enum Hook] 尝试从 meta_registry 查找父类（如 Enum）
                # self.analyzer.registry 就是 MetadataRegistry
                meta_reg = self.analyzer.registry
                
                if meta_reg:
                    parent_desc = meta_reg.resolve(node.parent)
                    if parent_desc and not parent_desc.is_class():
                        parent_desc = None
                
                if not parent_desc:
                    self.analyzer.error(f"Base class '{node.parent}' is not defined or not a class", node, code="SEM_001")
        
        # 2. 创建 ClassMetadata 并绑定到符号
        # 使用工厂创建以确保驻留
        descriptor = self.analyzer.registry.factory.create_class(
            name=node.name, 
            parent=node.parent
        )
        if parent_desc:
             descriptor.parent_name = parent_desc.name
        
        # 注册到元数据注册表，以便后续继承解析能找到它
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
        # param_types.append(self.current_class_descriptor) # self param handling logic moved to BoundMethodMetadata
            
        for arg_node in node.args:
            arg_type = ANY_DESCRIPTOR
            if isinstance(arg_node, ast.IbTypeAnnotatedExpr):
                arg_type = self.analyzer._resolve_type(arg_node.annotation)
            param_types.append(arg_type)
            
        # 使用工厂创建 FunctionMetadata 以确保驻留
        func_desc = self.analyzer.registry.factory.create_function(
            params=param_types,
            ret=ret_type
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
        if sym and sym.is_function:
            sym.descriptor = func_desc

    def visit_IbLLMFunctionDef(self, node: ast.IbLLMFunctionDef):
        # LLM 函数默认返回 string
        ret_type = STR_DESCRIPTOR
        if node.returns:
            ret_type = self.analyzer._resolve_type(node.returns)
            
        param_types = []
        # if self.current_class_descriptor:
        # param_types.append(self.current_class_descriptor)
            
        for arg_node in node.args:
            arg_type = ANY_DESCRIPTOR
            if isinstance(arg_node, ast.IbTypeAnnotatedExpr):
                arg_type = self.analyzer._resolve_type(arg_node.annotation)
            param_types.append(arg_type)
            
        # 使用工厂创建 FunctionMetadata 以确保驻留
        func_desc = self.analyzer.registry.factory.create_function(
            params=param_types,
            ret=ret_type
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
        if sym and sym.is_function:
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
                        # 统一使用 Symbol 包装成员，以满足语义分析器的接口需求
                        self.current_class_descriptor.members[name] = symbols.VariableSymbol(
                            name=name,
                            kind=symbols.SymbolKind.VARIABLE,
                            descriptor=declared_type,
                            def_node=target
                        )

                    sym = self.symbol_table.resolve(name)
                    if sym and sym.is_variable:
                        sym.descriptor = declared_type

    def visit_IbBehaviorInstance(self, node: ast.IbBehaviorInstance):
        """
        解析带类型标注的行为实例表达式 (Type) @~...~ 的返回类型。
        类型信息用于 __llmoutput_hint__ 注入和类型检查。
        """
        target_type_name = getattr(node, 'target_type_name', None)
        if target_type_name:
            return self.analyzer._resolve_type(target_type_name)
        return ANY_DESCRIPTOR

    def visit_IbBehaviorExpr(self, node: ast.IbBehaviorExpr):
        """
        解析不带类型标注的行为描述表达式 @~...~ 的返回类型。
        默认返回字符串类型。
        """
        return STR_DESCRIPTOR
