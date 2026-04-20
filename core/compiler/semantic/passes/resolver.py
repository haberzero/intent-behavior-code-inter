from typing import List, Optional, Any, TYPE_CHECKING
from core.kernel import ast as ast
from core.kernel import symbols
from core.kernel.symbols import SymbolTable, TypeSymbol, FunctionSymbol
from core.kernel.spec import IbSpec, ClassSpec, FuncSpec, ModuleSpec
from core.kernel.spec.member import MemberSpec, MethodMemberSpec

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
        self.current_class_descriptor: Optional[ClassSpec] = None

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
            # 使用 is_class_spec() 代替 isinstance 检查
            if parent_sym and parent_sym.spec and self.analyzer.registry.is_class_spec(parent_sym.spec):
                parent_desc = parent_sym.spec
            else:
                # [Enum Hook] 尝试从注册表查找父类（如 Enum）
                meta_reg = self.analyzer.registry
                
                if meta_reg:
                    parent_desc = meta_reg.resolve(node.parent)
                    if parent_desc and not self.analyzer.registry.is_class_spec(parent_desc):
                        parent_desc = None
                
                if not parent_desc:
                    self.analyzer.error(f"Base class '{node.parent}' is not defined or not a class", node, code="SEM_001")
        
        # 2. 创建 ClassSpec 并绑定到符号
        # 使用工厂创建以确保驻留
        descriptor = self.analyzer.registry.factory.create_class(
            name=node.name, 
            parent_name=node.parent
        )
        if parent_desc:
             descriptor.parent_name = parent_desc.name
        
        # 注册到注册表，以便后续继承解析能找到它
        # 必须使用返回的已注册克隆，否则成员信息只写入本地对象，
        # 注册表中存放的是另一个独立副本，导致 resolve_member 在继承场景下看到空类型。
        registered = self.analyzer.registry.register(descriptor)
             
        sym.spec = registered
        
        # 3. 解析成员
        old_class = self.current_class_descriptor
        self.current_class_descriptor = registered
        try:
            for stmt in node.body:
                if isinstance(stmt, (ast.IbFunctionDef, ast.IbLLMFunctionDef, ast.IbAssign)):
                    self.visit(stmt)
        finally:
            self.current_class_descriptor = old_class

    def visit_IbFunctionDef(self, node: ast.IbFunctionDef):
        # 解析返回类型
        ret_type = self.analyzer._void_desc
        if node.returns:
            ret_type = self.analyzer._resolve_type(node.returns)
            
        # 解析参数类型
        param_types = []
            
        for arg_node in node.args:
            arg_type = self.analyzer._any_desc
            if isinstance(arg_node, ast.IbTypeAnnotatedExpr):
                arg_type = self.analyzer._resolve_type(arg_node.annotation)
            param_types.append(arg_type)
            
        # 使用工厂创建 FuncSpec 以确保驻留
        func_desc = self.analyzer.registry.factory.create_func(
            name=node.name,
            param_type_names=[p.name for p in param_types],
            return_type_name=ret_type.name
        )
        func_desc.is_user_defined = True
        
        if self.current_class_descriptor:
            # 同步到 spec 的成员表中，使用正规的 MethodMemberSpec
            self.current_class_descriptor.members[node.name] = MethodMemberSpec(
                name=node.name,
                kind="method",
                param_type_names=[p.name for p in param_types],
                param_type_modules=[p.module_path for p in param_types],
                return_type_name=ret_type.name,
            )
            
        # 绑定到符号
        sym = self.symbol_table.resolve(node.name)
        if sym and sym.is_function:
            sym.spec = func_desc

    def visit_IbLLMFunctionDef(self, node: ast.IbLLMFunctionDef):
        # LLM 函数默认返回 string
        ret_type = self.analyzer._str_desc
        if node.returns:
            ret_type = self.analyzer._resolve_type(node.returns)
            
        param_types = []
            
        for arg_node in node.args:
            arg_type = self.analyzer._any_desc
            if isinstance(arg_node, ast.IbTypeAnnotatedExpr):
                arg_type = self.analyzer._resolve_type(arg_node.annotation)
            param_types.append(arg_type)
            
        # 使用工厂创建 FuncSpec 以确保驻留
        func_desc = self.analyzer.registry.factory.create_func(
            name=node.name,
            param_type_names=[p.name for p in param_types],
            return_type_name=ret_type.name,
            is_llm=True
        )
        func_desc.is_user_defined = True
        
        if self.current_class_descriptor:
            # 同步到 spec 的成员表中，使用正规的 MethodMemberSpec
            self.current_class_descriptor.members[node.name] = MethodMemberSpec(
                name=node.name,
                kind="method",
                param_type_names=[p.name for p in param_types],
                param_type_modules=[p.module_path for p in param_types],
                return_type_name=ret_type.name,
                llm=True,
            )

        sym = self.symbol_table.resolve(node.name)
        if sym and sym.is_function:
            sym.spec = func_desc
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
                        # 同步到 spec 的成员表中，使用正规的 MemberSpec
                        self.current_class_descriptor.members[name] = MemberSpec(
                            name=name,
                            kind="field",
                            type_name=declared_type.name,
                        )

                    sym = self.symbol_table.resolve(name)
                    if sym and sym.is_variable:
                        sym.spec = declared_type

    def visit_IbBehaviorInstance(self, node: ast.IbBehaviorInstance):
        """
        解析带类型标注的行为实例表达式 (Type) @~...~ 的返回类型。
        类型信息用于 __outputhint_prompt__ 注入和类型检查。
        """
        target_type_name = getattr(node, 'target_type_name', None)
        if target_type_name:
            return self.analyzer._resolve_type(target_type_name)
        return self.analyzer._any_desc

    def visit_IbBehaviorExpr(self, node: ast.IbBehaviorExpr):
        """
        解析不带类型标注的行为描述表达式 @~...~ 的返回类型。
        默认返回字符串类型。
        """
        return self.analyzer._str_desc
