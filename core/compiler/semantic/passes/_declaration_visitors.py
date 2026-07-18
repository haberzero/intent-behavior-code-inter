"""
Declaration Visitors Mixin for TypeCheckingVisitor.

Holds the visit methods for declaration AST nodes (class / function /
LLM-function) plus the override-compatibility helper. Split out from
``type_checking_pass.py`` as part of a pure mechanical refactoring —
no logic changes.
"""

from typing import Optional

from core.kernel import ast
from core.kernel.symbols import SymbolTable, SymbolKind, VariableSymbol
from core.kernel.spec import IbSpec
from core.kernel.spec.type_ref import TypeRef
from core.kernel.axioms.prompt_protocol import (
    validate_prompt_protocol_signature,
    is_prompt_protocol_method,
)

# Methods whose signatures are not constrained by parent class
# (constructors and protocol methods may freely change signature).
_OVERRIDE_SIGNATURE_FREE: frozenset = frozenset({
    "__init__", "__snapshot__", "__restore__",
    "__to_prompt__", "__from_prompt__", "__outputhint_prompt__",
    "__validate_prompt__",
})


class DeclarationVisitorsMixin:
    """Declaration visit methods (class / function / LLM-function)."""

    # ========== 定义 ==========

    def visit_IbClassDef(self, node: ast.IbClassDef) -> Optional[IbSpec]:
        """访问类定义"""
        sym = self.lookup_symbol(node.name)
        if sym and hasattr(sym, 'owned_scope') and sym.owned_scope:
            # 进入类作用域
            old_class = self.current_class
            old_in_class = self.in_class_def

            self.current_class = sym.spec
            self.in_class_def = True
            self.push_scope(sym.owned_scope)

            try:
                for stmt in node.body:
                    self.visit(stmt)
            finally:
                self.pop_scope()
                self.in_class_def = old_in_class
                self.current_class = old_class

        return None

    def visit_IbFunctionDef(self, node: ast.IbFunctionDef) -> Optional[IbSpec]:
        """访问函数定义 — 解析参数类型标注，回填 spec，参数以正确类型注册"""
        # 查找函数符号
        sym = self.lookup_symbol(node.name)

        # 解析参数类型标注
        param_types = []
        for arg_node in node.args:
            # IbArg now has annotation field directly
            if arg_node.annotation:
                arg_type = self._resolve_type(arg_node.annotation) or self._any_desc
            else:
                arg_type = self._any_desc
            param_types.append(arg_type)

        # 如果在类定义中，插入 self 类型
        if self.in_class_def and self.current_class:
            param_types.insert(0, self.current_class)

        # 解析返回类型标注
        ret_type = self._resolve_type(node.returns) if node.returns else self._any_desc
        is_auto_return = (node.returns and
                         isinstance(node.returns, ast.IbName) and
                         node.returns.id == "auto")

        # 回填函数 spec（用 factory.create_func 重建 TypeDef 携带签名）
        if sym and sym.spec and self.registry:
            param_type_names = [(p.name if p else "any") for p in param_types]
            ret_type_name = ret_type.name if ret_type else "void"
            from core.base.enums import Provenance, Visibility
            updated_spec = self.registry.factory.create_func(
                name=node.name,
                param_type_names=param_type_names,
                return_type_name=ret_type_name,
                provenance=Provenance.USER_DEFINED,
                visibility=Visibility.IMPORT_GATED,
            )
            sym.spec = updated_spec

        # 创建函数作用域
        func_scope = SymbolTable(parent=self.current_scope, name=node.name)
        if sym and hasattr(sym, 'owned_scope'):
            sym.owned_scope = func_scope

        old_in_function = self.in_function_def
        old_auto_returns = self.auto_return_types

        self.in_function_def = True
        if is_auto_return:
            self.auto_return_types = []

        self.push_scope(func_scope)
        try:
            # 注册参数到函数作用域（使用解析后的类型，非 any）
            for i, arg_node in enumerate(node.args):
                arg_name = self._extract_arg_name(arg_node)
                # 类方法有 self 偏移
                sig_idx = i + 1 if (self.in_class_def and self.current_class) else i
                arg_type = param_types[sig_idx] if sig_idx < len(param_types) else self._any_desc
                if arg_name:
                    param_sym = VariableSymbol(
                        name=arg_name,
                        kind=SymbolKind.VARIABLE,
                        def_node=arg_node,
                        spec=arg_type,
                    )
                    func_scope.define(param_sym)

            # 处理函数体
            for stmt in node.body:
                self.visit(stmt)

            # -> auto 函数返回类型统一
            if is_auto_return and self.auto_return_types:
                unique = list({s.name: s for s in self.auto_return_types if s}.values())
                if len(unique) == 1:
                    inferred_return = unique[0]
                elif len(unique) == 0:
                    inferred_return = self._void_desc
                else:
                    self.error(
                        f"Function '{node.name}' is declared '-> auto' but returns conflicting types: "
                        f"{', '.join(t.name for t in unique)}",
                        node, code="SEM_003"
                    )
                    inferred_return = self._any_desc
                # 更新符号的返回类型
                if sym and sym.spec and hasattr(sym.spec, 'return_type'):
                    sym.spec.return_type = TypeRef.of(inferred_return.name, getattr(inferred_return, "module_path", None))

        finally:
            self.pop_scope()
            self.in_function_def = old_in_function
            self.auto_return_types = old_auto_returns

        # SEM_092: Method override signature compatibility check
        if self.in_class_def and self.current_class and sym and sym.spec:
            self._check_override_compatibility(node, sym.spec)

        # SEM_095: Prompt protocol signature validation
        if self.in_class_def and is_prompt_protocol_method(node.name):
            # Count params excluding self
            user_param_count = len(node.args)
            ret_type_name = None
            if node.returns and isinstance(node.returns, ast.IbName):
                ret_type_name = node.returns.id
            diagnostics = validate_prompt_protocol_signature(
                node.name, user_param_count, ret_type_name
            )
            for diag_msg in diagnostics:
                self.warn(diag_msg, node, code="SEM_095")

        return None

    @staticmethod
    def _extract_arg_name(arg_node) -> Optional[str]:
        """从参数节点提取参数名。IbArg now has annotation field directly."""
        if isinstance(arg_node, ast.IbArg):
            return arg_node.arg
        return None

    def _check_override_compatibility(self, node: ast.IbFunctionDef, child_spec: IbSpec):
        """SEM_092: Check that overriding method's signature is compatible with parent.

        Rules:
        - Parameter count must match (including self).
        - Parameter types must be compatible (parent param assignable to child param — contravariance).
        - Return type must be compatible (child return assignable to parent return — covariance).
        - __init__ and protocol methods are exempt.
        """
        method_name = node.name
        if method_name in _OVERRIDE_SIGNATURE_FREE:
            return

        # Find parent class spec
        parent_type_ref = getattr(self.current_class, 'parent_type', None)
        if not parent_type_ref:
            return
        parent_class_name = parent_type_ref.head
        if not parent_class_name:
            return

        # Look up parent class symbol to access its owned_scope (has refined specs)
        parent_class_sym = self.lookup_symbol(parent_class_name)
        if not parent_class_sym or not hasattr(parent_class_sym, 'owned_scope') or not parent_class_sym.owned_scope:
            return

        # Find same-named method in parent's scope
        parent_method_sym = parent_class_sym.owned_scope.resolve(method_name)
        if not parent_method_sym or not parent_method_sym.spec:
            return  # Not an override, just a new method

        parent_method_spec = parent_method_sym.spec
        # Only check if parent method is callable (has param_types / return_type)
        parent_params = getattr(parent_method_spec, 'param_types', None)
        parent_return = getattr(parent_method_spec, 'return_type', None)
        if parent_params is None:
            return

        child_params = getattr(child_spec, 'param_types', None) or []
        child_return = getattr(child_spec, 'return_type', None)

        # Compare parameter count (both include self as first param)
        if len(child_params) != len(parent_params):
            self.warn(
                f"Method '{method_name}' overrides parent with "
                f"{len(parent_params)} parameter(s), but defines "
                f"{len(child_params)} parameter(s).",
                node, code="SEM_092",
                hint=f"Parent signature has {len(parent_params)} parameters (including self). "
                     f"Ensure override matches the parent signature."
            )
            return  # Cannot check individual params if count differs

        # Check parameter types (skip self at index 0)
        for i in range(1, len(parent_params)):
            parent_p = parent_params[i]
            child_p = child_params[i] if i < len(child_params) else None

            if not parent_p or not child_p:
                continue
            parent_p_head = parent_p.head if isinstance(parent_p, TypeRef) else getattr(parent_p, 'head', None)
            child_p_head = child_p.head if isinstance(child_p, TypeRef) else getattr(child_p, 'head', None)

            if not parent_p_head or not child_p_head:
                continue
            # Skip dynamic types
            if parent_p_head in ("any", "auto") or child_p_head in ("any", "auto"):
                continue

            parent_p_spec = self.registry.resolve(parent_p_head)
            child_p_spec = self.registry.resolve(child_p_head)
            if not parent_p_spec or not child_p_spec:
                continue

            # Simplified compatibility: for IBCI we accept bidirectional assignability
            # (not strict contravariance) since user-defined classes rarely use deep
            # type hierarchies where variance rules matter.
            if (not self.registry.is_assignable(parent_p_spec, child_p_spec)
                    and not self.registry.is_assignable(child_p_spec, parent_p_spec)):
                self.warn(
                    f"Method '{method_name}' parameter {i} type '{child_p_head}' "
                    f"is incompatible with parent's '{parent_p_head}'.",
                    node, code="SEM_092",
                    hint=f"Override parameter types should be compatible with the parent method."
                )

        # Check return type (covariance: child return assignable to parent return)
        if parent_return and child_return:
            parent_r_head = parent_return.head if isinstance(parent_return, TypeRef) else getattr(parent_return, 'head', None)
            child_r_head = child_return.head if isinstance(child_return, TypeRef) else getattr(child_return, 'head', None)

            if (parent_r_head and child_r_head
                    and parent_r_head not in ("any", "auto", "void")
                    and child_r_head not in ("any", "auto", "void")):
                parent_r_spec = self.registry.resolve(parent_r_head)
                child_r_spec = self.registry.resolve(child_r_head)
                if (parent_r_spec and child_r_spec
                        and not self.registry.is_assignable(child_r_spec, parent_r_spec)):
                    self.warn(
                        f"Method '{method_name}' return type '{child_r_head}' "
                        f"is incompatible with parent's '{parent_r_head}'.",
                        node, code="SEM_092",
                        hint=f"Override return type should be assignable to parent's return type."
                    )

    def visit_IbLLMFunctionDef(self, node: ast.IbLLMFunctionDef) -> Optional[IbSpec]:
        """访问 LLM 函数定义"""
        # 类似 IbFunctionDef
        func_scope = SymbolTable(parent=self.current_scope, name=node.name)

        old_in_function = self.in_function_def
        self.in_function_def = True
        self.push_scope(func_scope)

        try:
            for arg in node.args:
                self.visit(arg)
            # LLM 函数的提示词段落（sys_prompt / user_prompt / retry_hint）
            for prompt_list in (node.sys_prompt, node.user_prompt, node.retry_hint):
                if prompt_list:
                    for segment in prompt_list:
                        if isinstance(segment, ast.IbASTNode):
                            self.visit(segment)
        finally:
            self.pop_scope()
            self.in_function_def = old_in_function

        return None
