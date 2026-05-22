"""
Pass 2.5: Type Resolution Pass

职责：解析类型标注，将 AST 中的类型名称字符串转换为 IbSpec 引用
输入：Context with resolved symbols
输出：Context with type annotations resolved

设计原则：
- 独立于 TypeCheckingPass（类型检查）——本 Pass 只做"名字→IbSpec"的解析
- 为后续 TypeCheckingPass 提供已解析的类型标注
- 处理 auto/any/fn 等动态类型标记
- 处理泛型类型标注 (list[int], dict[str, int] 等)
"""

from dataclasses import replace
from typing import Optional, List, Dict, Any

from core.kernel import ast
from core.kernel.symbols import Symbol, SymbolTable, SymbolKind
from core.kernel.spec import IbSpec

from ..result import PassResult, Diagnostic, DiagnosticLevel
from ..context import SemanticContext
from .base_pass import BasePass


class TypeResolutionPass(BasePass):
    """类型解析 Pass

    解析所有类型标注：
    - 函数参数类型标注
    - 函数返回类型标注
    - 变量声明类型标注
    - 泛型类型标注
    - 类型转换标注
    """

    def __init__(self):
        super().__init__("TypeResolutionPass")

    def run(self, context: SemanticContext) -> PassResult:
        """运行类型解析 Pass"""
        resolver = TypeAnnotationResolver(context)
        resolver.resolve(context.ast)

        # 更新 metadata 中的类型绑定（仅标注节点的解析结果）
        new_metadata = context.metadata
        for node_uid, type_spec in resolver.resolved_types.items():
            new_metadata.type_bindings[node_uid] = type_spec

        new_context = replace(context, metadata=new_metadata)
        return PassResult.ok(new_context, diagnostics=resolver.diagnostics)


class TypeAnnotationResolver:
    """类型标注解析器

    遍历 AST，解析所有类型标注节点（IbName/IbGenericType/IbSubscript in annotation position）
    """

    def __init__(self, context: SemanticContext):
        self.context = context
        self.registry = context.registry
        self.diagnostics: List[Diagnostic] = []
        self.resolved_types: Dict[str, IbSpec] = {}

        # 常用类型描述符缓存
        self._any_desc = self.registry.resolve("any")
        self._auto_desc = self.registry.resolve("auto")

    def error(self, message: str, node: ast.IbASTNode, code: str = "SEM_000"):
        """记录错误诊断"""
        node_uid = getattr(node, 'uid', None)
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.ERROR,
            message=message,
            code=code,
            node_uid=node_uid
        ))

    def resolve(self, node: ast.IbASTNode):
        """递归解析节点中的类型标注"""
        method_name = f'resolve_{node.__class__.__name__}'
        resolver = getattr(self, method_name, self._generic_resolve)
        return resolver(node)

    def _generic_resolve(self, node: ast.IbASTNode):
        """默认递归解析"""
        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        self.resolve(item)
            elif isinstance(child, ast.IbASTNode):
                self.resolve(child)

    def resolve_type_annotation(self, annotation: ast.IbASTNode) -> Optional[IbSpec]:
        """解析单个类型标注节点为 IbSpec"""
        if annotation is None:
            return None

        if isinstance(annotation, ast.IbName):
            spec = self.registry.resolve(annotation.id)
            if not spec:
                self.error(
                    f"Unknown type '{annotation.id}'",
                    annotation, code="SEM_004"
                )
                return self._any_desc
            return spec

        elif isinstance(annotation, ast.IbSubscript):
            # 泛型类型: list[int], dict[str, int], Optional[str]
            if isinstance(annotation.value, ast.IbName):
                base_spec = self.registry.resolve(annotation.value.id)
                if base_spec:
                    # 记录基础类型（泛型参数在当前 IBCI 中是 erasure）
                    return base_spec
            return self._any_desc

        elif hasattr(ast, 'IbGenericType') and isinstance(annotation, ast.IbGenericType):
            # 显式泛型标注节点
            base_name = annotation.base.id if isinstance(annotation.base, ast.IbName) else str(annotation.base)
            base_spec = self.registry.resolve(base_name)
            return base_spec if base_spec else self._any_desc

        elif hasattr(ast, 'IbCallableType') and isinstance(annotation, ast.IbCallableType):
            # fn[(param_types) -> return_type] 类型标注
            fn_callable_spec = self.registry.resolve("fn_callable")
            return fn_callable_spec if fn_callable_spec else self._any_desc

        return self._any_desc

    # ========== 节点解析方法 ==========

    def resolve_IbModule(self, node: ast.IbModule):
        """解析模块"""
        for stmt in node.body:
            self.resolve(stmt)

    def resolve_IbFunctionDef(self, node: ast.IbFunctionDef):
        """解析函数定义的类型标注"""
        # 解析参数类型
        for arg in node.args:
            self.resolve(arg)

        # 解析返回类型
        if node.returns:
            ret_spec = self.resolve_type_annotation(node.returns)
            node_uid = getattr(node.returns, 'uid', None)
            if node_uid and ret_spec:
                self.resolved_types[node_uid] = ret_spec

        # 递归处理函数体
        for stmt in node.body:
            self.resolve(stmt)

    def resolve_IbLLMFunctionDef(self, node: ast.IbLLMFunctionDef):
        """解析 LLM 函数定义的类型标注"""
        for arg in node.args:
            self.resolve(arg)
        if node.returns:
            ret_spec = self.resolve_type_annotation(node.returns)
            node_uid = getattr(node.returns, 'uid', None)
            if node_uid and ret_spec:
                self.resolved_types[node_uid] = ret_spec

    def resolve_IbClassDef(self, node: ast.IbClassDef):
        """解析类定义"""
        for stmt in node.body:
            self.resolve(stmt)

    def resolve_IbAssign(self, node: ast.IbAssign):
        """解析赋值中的类型标注"""
        for target in node.targets:
            if isinstance(target, ast.IbTypeAnnotatedExpr):
                type_spec = self.resolve_type_annotation(target.annotation)
                node_uid = getattr(target.annotation, 'uid', None)
                if node_uid and type_spec:
                    self.resolved_types[node_uid] = type_spec
        # 递归处理值表达式
        if node.value:
            self.resolve(node.value)

    def resolve_IbTypeAnnotatedExpr(self, node: ast.IbTypeAnnotatedExpr):
        """解析类型标注表达式"""
        type_spec = self.resolve_type_annotation(node.annotation)
        node_uid = getattr(node.annotation, 'uid', None)
        if node_uid and type_spec:
            self.resolved_types[node_uid] = type_spec
        self.resolve(node.target)

    def resolve_IbCastExpr(self, node: ast.IbCastExpr):
        """解析类型转换表达式"""
        type_spec = self.resolve_type_annotation(node.type_annotation)
        node_uid = getattr(node.type_annotation, 'uid', None)
        if node_uid and type_spec:
            self.resolved_types[node_uid] = type_spec
        self.resolve(node.value)
