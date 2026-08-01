"""
Type Resolution Pass (TypePhase sub-step 1)

职责：解析类型标注，将 AST 中的类型名称字符串转换为 IbSpec 引用
输入：Context with resolved symbols
输出：PassOutput with type_bindings
"""

from typing import Optional, List, Dict, Any

from core.base.diagnostics.codes import SEM_INVALID_SCOPE, SEM_UNCATEGORIZED
from core.kernel import ast
from core.kernel.symbols import Symbol, SymbolTable, SymbolKind
from core.kernel.spec import IbSpec

from ..result import PassResult, PassOutput, Diagnostic, DiagnosticLevel
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
        resolver = TypeAnnotationResolver(context)
        resolver.resolve(context.ast)

        output = PassOutput(
            type_bindings=dict(resolver.resolved_types),
            diagnostics=resolver.diagnostics,
            success=True,
        )
        return PassResult.ok(context, output=output)


class TypeAnnotationResolver:
    """类型标注解析器

    遍历 AST，解析所有类型标注节点（IbName/IbSubscript/IbCallableType in annotation position）
    """

    def __init__(self, context: SemanticContext):
        self.context = context
        self.registry = context.registry
        self.diagnostics: List[Diagnostic] = []
        self.resolved_types: Dict[Any, IbSpec] = {}

        # 常用类型描述符缓存
        self._any_desc = self.registry.resolve("any")
        if self._any_desc is None:
            raise RuntimeError("Internal: registry has no 'any' primitive; type resolution cannot proceed.")
        self._auto_desc = self.registry.resolve("auto")

    def error(self, message: str, node: ast.IbASTNode, code: str = SEM_UNCATEGORIZED):
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
                    annotation, code=SEM_INVALID_SCOPE
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

        elif isinstance(annotation, ast.IbCallableType):
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
            if ret_spec:
                self.resolved_types[node.returns] = ret_spec

        # 递归处理函数体
        for stmt in node.body:
            self.resolve(stmt)

    def resolve_IbLLMFunctionDef(self, node: ast.IbLLMFunctionDef):
        """解析 LLM 函数定义的类型标注"""
        for arg in node.args:
            self.resolve(arg)
        if node.returns:
            ret_spec = self.resolve_type_annotation(node.returns)
            if ret_spec:
                self.resolved_types[node.returns] = ret_spec

    def resolve_IbClassDef(self, node: ast.IbClassDef):
        """解析类定义"""
        for stmt in node.body:
            self.resolve(stmt)

    def resolve_IbAssign(self, node: ast.IbAssign):
        """解析赋值中的类型标注"""
        for target in node.targets:
            if isinstance(target, ast.IbTypeAnnotatedExpr):
                type_spec = self.resolve_type_annotation(target.annotation)
                if type_spec:
                    self.resolved_types[target.annotation] = type_spec
        # 递归处理值表达式
        if node.value:
            self.resolve(node.value)

    def resolve_IbTypeAnnotatedExpr(self, node: ast.IbTypeAnnotatedExpr):
        """解析类型标注表达式"""
        type_spec = self.resolve_type_annotation(node.annotation)
        if type_spec:
            self.resolved_types[node.annotation] = type_spec
        self.resolve(node.target)

    def resolve_IbCastExpr(self, node: ast.IbCastExpr):
        """解析类型转换表达式"""
        type_spec = self.resolve_type_annotation(node.type_annotation)
        if type_spec:
            self.resolved_types[node.type_annotation] = type_spec
        self.resolve(node.value)
