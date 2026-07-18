"""
Type Checking Base Mixin — Infrastructure methods for TypeCheckingVisitor.

Provides dispatch, diagnostic, and type-resolution helpers shared by every
other TypeCheckingVisitor mixin. Split out from ``type_checking_pass.py``
as part of a pure mechanical refactoring — no logic changes.
"""

from typing import Optional

from core.base.enums import Provenance, Visibility
from core.kernel import ast
from core.kernel.symbols import Symbol
from core.kernel.spec import IbSpec
from core.kernel.spec.base import TypeKind, TypeDef
from core.kernel.spec.type_ref import TypeRef

from ..result import Diagnostic, DiagnosticLevel


class TypeCheckBase:
    """Infrastructure mixin for ``TypeCheckingVisitor``.

    Shared-state protocol — the following attributes are set up by
    ``TypeCheckingVisitor.__init__`` (and ``ScopedVisitor.__init__``) and
    may be relied on by every mixin defined on the composed class:

    - ``self.context`` (SemanticContext)
    - ``self.symbol_table`` (current root symbol table)
    - ``self.registry`` (TypeRegistry)
    - ``self.diagnostics`` (List[Diagnostic])
    - ``self.scope_stack`` / ``self.current_scope`` / ``push_scope`` /
      ``pop_scope`` (scope management, provided by ScopedVisitor)
    - ``self.type_bindings`` (Dict[Any, IbSpec])
    - ``self.auto_return_types`` (Optional[List[IbSpec]])
    - ``self.in_function_def`` / ``self.in_class_def`` (bool flags)
    - ``self.current_class`` (Optional[IbSpec])
    - ``self._any_desc`` / ``self._void_desc`` / ``self._behavior_desc``
      / ``self._int_desc`` / ``self._float_desc`` / ``self._str_desc``
      / ``self._bool_desc`` / ``self._none_desc`` (cached IbSpec descriptors)
    - ``self._current_node`` (set on demand by ``_handle_assign_target``)
    """

    def visit(self, node: ast.IbASTNode) -> Optional[IbSpec]:
        """访问节点的分派方法，返回节点的类型"""
        if node is None:
            return None
        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ast.IbASTNode) -> Optional[IbSpec]:
        """默认访问：递归访问所有子节点，返回 any 类型"""
        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        self.visit(item)
            elif isinstance(child, ast.IbASTNode):
                self.visit(child)
        return self._any_desc

    def error(self, message: str, node: ast.IbASTNode, code: str = "SEM_000", hint: str = None):
        """记录错误诊断"""
        node_uid = getattr(node, 'uid', None)
        full_message = message
        if hint:
            full_message = f"{message}\nHint: {hint}"
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.ERROR,
            message=full_message,
            code=code,
            node_uid=node_uid
        ))

    def bind_type(self, node: ast.IbASTNode, type_spec: IbSpec):
        """绑定类型到节点（使用节点对象作为键）"""
        if node and type_spec:
            self.type_bindings[node] = type_spec

    def lookup_symbol(self, name: str) -> Optional[Symbol]:
        """在当前作用域查找符号"""
        return self.current_scope.resolve(name)

    def is_assignable(self, source: IbSpec, target: IbSpec) -> bool:
        """检查源类型是否可以赋给目标类型（dynamic 类型跳过检查）"""
        if not source or not target:
            return True
        # Guard: resolve TypeRef to actual IbSpec if needed
        if isinstance(source, TypeRef):
            source = self.registry.resolve(source.head) or self._any_desc
        if isinstance(target, TypeRef):
            target = self.registry.resolve(target.head) or self._any_desc
        # 当源或目标为 dynamic（any/auto）时，跳过兼容性检查
        if self.registry.is_dynamic(source) or self.registry.is_dynamic(target):
            return True
        return self.registry.is_assignable(source, target)

    def warn(self, message: str, node: ast.IbASTNode, code: str = "SEM_000", hint: str = None):
        """记录警告诊断"""
        node_uid = getattr(node, 'uid', None)
        full_message = message
        if hint:
            full_message = f"{message}\nHint: {hint}"
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.WARNING,
            message=full_message,
            code=code,
            node_uid=node_uid
        ))

    def _resolve_type(self, annotation: ast.IbASTNode) -> Optional[IbSpec]:
        """解析类型标注"""
        if annotation is None:
            return self._any_desc
        if isinstance(annotation, ast.IbName):
            return self.registry.resolve(annotation.id) or self._any_desc
        elif isinstance(annotation, ast.IbCallableType):
            # D3: callable signature constraint fn[(param_types) -> return_type]
            param_specs = [self._resolve_type(pt) for pt in annotation.param_types]
            ret_spec = (
                self._resolve_type(annotation.return_type)
                if annotation.return_type is not None
                else self._any_desc
            )
            return TypeDef(
                name="fn",
                kind=TypeKind.CALLABLE_SIG.value,
                param_types=[TypeRef.of(p.name, getattr(p, 'module_path', None)) for p in param_specs],
                return_type=TypeRef.of(ret_spec.name, getattr(ret_spec, 'module_path', None)),
                provenance=Provenance.KERNEL_NATIVE,
                visibility=Visibility.PRELUDE_VISIBLE,
            )
        elif isinstance(annotation, ast.IbSubscript):
            # 泛型类型：list[int], dict[str, int], tuple[int, str], Optional[int] 等
            if isinstance(annotation.value, ast.IbName):
                base_type = self.registry.resolve(annotation.value.id)
                if base_type:
                    # 解析泛型参数
                    if isinstance(annotation.slice, ast.IbTuple):
                        generic_args = [self._resolve_type(elt) for elt in annotation.slice.elts]
                    else:
                        generic_args = [self._resolve_type(annotation.slice)]
                    # 使用 registry.resolve_specialization 解析特化
                    result = self.registry.resolve_specialization(base_type, generic_args)
                    return result if result is not None else base_type
                return self._any_desc
            return self._any_desc
        else:
            # 其他类型标注
            return self._any_desc
