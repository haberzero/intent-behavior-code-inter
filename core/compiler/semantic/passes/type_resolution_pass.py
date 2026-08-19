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
from ._type_checking_base import module_qualified_annotation, module_qualified_display


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

        # 用户类泛型类型参数上下文栈：resolve_IbClassDef 进入类体时压入
        # 当前类的 type_params 集合，供类内 T 解析为占位 spec。
        self._type_param_stack: List[List[str]] = []

        # 常用类型描述符缓存
        self._any_desc = self.registry.resolve("any")
        if self._any_desc is None:
            raise RuntimeError("Internal: registry has no 'any' primitive; type resolution cannot proceed.")
        self._auto_desc = self.registry.resolve("auto")

    def error(self, message: str, node: ast.IbASTNode, code: str = SEM_UNCATEGORIZED):
        """记录错误诊断"""
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.ERROR,
            message=message,
            code=code
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
            # 用户类泛型类型参数：类体内 T 解析为占位 spec（TYPE_PARAM kind）。
            if self._type_param_stack and annotation.id in self._type_param_stack[-1]:
                return self._build_type_param_spec(annotation.id)
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
            # 经 resolve_specialization 保真实参（与 symbol_collection_pass 一致），
            # 不再擦除为基类型（消除 erasure/preserve 双口径）。
            if isinstance(annotation.value, (ast.IbName, ast.IbAttribute)):
                if isinstance(annotation.value, ast.IbName):
                    base_spec = self.registry.resolve(annotation.value.id)
                else:
                    module_path, type_name = module_qualified_annotation(annotation.value)
                    base_spec = self.registry.resolve(type_name, module=module_path) if type_name else None
                if base_spec:
                    if isinstance(annotation.slice, ast.IbTuple):
                        arg_specs = [
                            self.resolve_type_annotation(elt) for elt in annotation.slice.elts
                        ]
                    else:
                        arg_specs = [self.resolve_type_annotation(annotation.slice)]
                    arg_specs = [s for s in arg_specs if s is not None]
                    if arg_specs:
                        specialized = self.registry.resolve_specialization(base_spec, arg_specs)
                        if specialized is not None:
                            return specialized
                    return base_spec
            return self._any_desc

        elif isinstance(annotation, ast.IbAttribute):
            # 模块限定类型标注：geo.Counter / subpkg.util.Counter。
            # 与 _resolve_type 同构解析目标 spec（跨模块用户类）。
            module_path, type_name = module_qualified_annotation(annotation)
            if type_name is None:
                return self._any_desc
            spec = self.registry.resolve(type_name, module=module_path)
            if not spec:
                self.error(
                    f"Unknown type '{module_qualified_display(annotation)}'",
                    annotation, code=SEM_INVALID_SCOPE
                )
                return self._any_desc
            return spec

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
        # 类方法需要同时继承类类型参数与函数自身类型参数，不能用一个空列表
        # 遮蔽外层类作用域。
        inherited = list(self._type_param_stack[-1]) if self._type_param_stack else []
        combined = list(dict.fromkeys(inherited + list(node.type_params)))
        self._type_param_stack.append(combined)
        try:
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
        finally:
            self._type_param_stack.pop()

    def resolve_IbProtocolDef(self, node: ast.IbProtocolDef):
        """解析协议定义，支持协议类型参数。"""
        self._type_param_stack.append(list(node.type_params))
        try:
            for stmt in node.body:
                self.resolve(stmt)
        finally:
            self._type_param_stack.pop()

    def resolve_IbImplDef(self, node: ast.IbImplDef):
        """解析 retroactive implementation 块的方法体类型标注。

        v1 目标类非泛型（泛型目标由类型检查阶段拒绝），无需类型参数栈。
        """
        for stmt in node.body:
            self.resolve(stmt)

    def resolve_IbClassDef(self, node: ast.IbClassDef):
        """解析类定义"""
        self._type_param_stack.append(list(node.type_params))
        try:
            for stmt in node.body:
                self.resolve(stmt)
        finally:
            self._type_param_stack.pop()

    @staticmethod
    def _build_type_param_spec(name: str) -> IbSpec:
        """构造类型参数占位 spec（与 SpecFactory.create_type_param 同构）。"""
        from core.base.enums import Provenance, Visibility
        from core.kernel.spec.base import TypeKind, TypeDef
        return TypeDef(
            name=name,
            kind=TypeKind.TYPE_PARAM.value,
            provenance=Provenance.USER_DEFINED,
            visibility=Visibility.IMPORT_GATED,
        )

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
