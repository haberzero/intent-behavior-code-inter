"""
Type Checking Base Mixin — Infrastructure methods for TypeCheckingVisitor.

Provides dispatch, diagnostic, and type-resolution helpers shared by every
other TypeCheckingVisitor mixin. Split out from ``type_checking_pass.py``
as part of a pure mechanical refactoring — no logic changes.
"""

from typing import Optional

from core.base.diagnostics.codes import (
    SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE,
    SEM_MULTI_TYPE_LIST_REMOVED,
    SEM_UNCATEGORIZED,
    SEM_UNRESOLVED_TYPE,
    ICE_TYPE_LEAK,
)
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

    def error(self, message: str, node: ast.IbASTNode, code: str = SEM_UNCATEGORIZED, hint: str = None):
        """记录错误诊断"""
        full_message = message
        if hint:
            full_message = f"{message}\nHint: {hint}"
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.ERROR,
            message=full_message,
            code=code
        ))

    def bind_type(self, node: ast.IbASTNode, type_spec: IbSpec):
        """绑定类型到节点（使用节点对象作为键）"""
        if node and type_spec:
            self.type_bindings[node] = type_spec

    def _bind_condition_behavior_types(self, node: Optional[ast.IbASTNode]):
        """把布尔上下文中的行为表达式定型为 ``bool``（递归传播）。

        布尔位置：条件测试本身、``and``/``or`` 操作数、逻辑 ``not`` 操作数。
        不穿透：``BinOp``/``Compare``（行为按另一操作数适配，是值比较语义）、
        值上下文（赋值 LHS / 调用实参 / 容器元素等不由本方法处理）。

        与 ``visit_IbIf``/``visit_IbWhile``/条件驱动 ``visit_IbFor`` 的
        直接条件绑定同一条设计契约：行为表达式的结果类型由使用上下文决定，
        布尔上下文即 ``bool``。调用方须在 ``visit`` 之后执行（覆盖占位符绑定）。
        """
        if node is None:
            return
        if isinstance(node, ast.IbBehaviorExpr):
            self.bind_type(node, self._bool_desc)
        elif isinstance(node, ast.IbBoolOp):
            for val in node.values:
                self._bind_condition_behavior_types(val)
        elif isinstance(node, ast.IbUnaryOp) and node.op == "not":
            self._bind_condition_behavior_types(node.operand)

    def _class_has_member_method(self, spec: IbSpec, method_name: str) -> bool:
        """类（含继承链）是否声明了指定方法成员。

        类成员以 ``spec.members`` 承载（本地定义的类已回填方法 spec）。
        继承的方法沿 ``parent_type`` 向上查找。
        """
        seen = set()
        cur: Optional[IbSpec] = spec
        while cur is not None:
            name = getattr(cur, "name", None)
            if name in seen:
                break
            seen.add(name)
            if method_name in (getattr(cur, "members", None) or {}):
                return True
            parent_ref = getattr(cur, "parent_type", None)
            if parent_ref is None:
                break
            cur = self.registry.resolve(parent_ref.head)
        return False

    def _has_llm_parse_cap(self, spec: Optional[IbSpec]) -> bool:
        """目标类型能否作为 LLM 行为输出被解析回原类型。

        LLM 输出原始形态是字符串；要兑现声明的具体输出类型，目标必须有
        from_prompt/parser 能力（内建类型公理）或 ``__from_prompt__`` 方法
        （用户类）。auto/any/fn 等动态类型无输出契约（运行期 box 为字符串），
        视为可解析。无法确认的 spec（None/未解析）保守视为可解析，避免误伤
        运行时注册的解析能力。
        """
        if spec is None:
            return True
        if self.registry.is_dynamic(spec):
            return True
        # 行为本体（fn_callable/behavior）：目标类型未解析到真实声明类型时的
        # 兜底形态（如对既有变量赋行为，见 _handle_assign_target 的 target_type
        # 回退），无独立输出契约，运行期 box 为字符串。
        if spec.kind == TypeKind.CALLABLE_INSTANCE.value and spec.get_base_name() in ("behavior", "fn_callable"):
            return True
        if self.registry.get_from_prompt_cap(spec) is not None:
            return True
        if self.registry.get_parser_cap(spec) is not None:
            return True
        if spec.kind == TypeKind.CLASS.value:
            return self._class_has_member_method(spec, "__from_prompt__")
        return False

    def _check_behavior_output_parseable(self, spec: Optional[IbSpec], node: ast.IbASTNode) -> None:
        """行为输出的目标类型必须可被 LLM 解析；否则编译期错误（fail-fast）。

        声明的具体输出类型无解析能力时，运行期会把 LLM 字符串静默 box 成成功值，
        使错误类型流入后续代码。此处把根因（声明了无法兑现的输出类型）在编译期
        暴露，避免 llmexcept 重试空转（重试无法弥补缺失的解析能力）。
        """
        if self._has_llm_parse_cap(spec):
            return
        self.error(
            f"Behavior output type '{spec.name}' has no LLM parsing capability "
            f"(no __from_prompt__/parser). LLM output would silently become a string. "
            f"Add '__from_prompt__' to '{spec.name}', or declare '-> str'/'auto'/'any' "
            f"if the raw string is intended.",
            node, code=SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE,
        )

    def lookup_symbol(self, name: str) -> Optional[Symbol]:
        """在当前作用域查找符号"""
        return self.current_scope.resolve(name)

    def is_assignable(self, source: IbSpec, target: IbSpec) -> bool:
        """检查源类型是否可以赋给目标类型（dynamic 类型跳过检查）"""
        if not source or not target:
            return True
        if isinstance(source, TypeRef):
            resolved = self.registry.resolve(source.head)
            if not resolved:
                self.error(
                    f"Unresolved type '{source.head}' in assignability check",
                    self._current_node, code=SEM_UNRESOLVED_TYPE,
                )
                resolved = self._any_desc
            source = resolved
        if isinstance(target, TypeRef):
            resolved = self.registry.resolve(target.head)
            if not resolved:
                self.error(
                    f"Unresolved type '{target.head}' in assignability check",
                    self._current_node, code=SEM_UNRESOLVED_TYPE,
                )
                resolved = self._any_desc
            target = resolved
        if self.registry.is_dynamic(source) or self.registry.is_dynamic(target):
            return True
        return self.registry.is_assignable(source, target)

    def warn(self, message: str, node: ast.IbASTNode, code: str = SEM_UNCATEGORIZED, hint: str = None):
        """记录警告诊断"""
        full_message = message
        if hint:
            full_message = f"{message}\nHint: {hint}"
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.WARNING,
            message=full_message,
            code=code
        ))

    def _resolve_type(self, annotation: ast.IbASTNode) -> Optional[IbSpec]:
        """解析类型标注"""
        if annotation is None:
            return self._any_desc
        if isinstance(annotation, ast.IbName):
            resolved = self.registry.resolve(annotation.id)
            if not resolved:
                self.error(
                    f"Unknown type '{annotation.id}'",
                    annotation, code=SEM_UNRESOLVED_TYPE,
                )
                return self._any_desc
            return resolved
        elif isinstance(annotation, ast.IbCallableType):
            # callable signature constraint fn[(param_types) -> return_type]
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
                    # 多类型 list（list[int,str]）已移除：无 union 类型机制，元素读取
                    # 本应显式 any。异构容器必须显式声明 list[any]，不允许隐式异构
                    # 击穿元素类型（tuple 多参为位置元素类型，属合法特性，不受影响）。
                    if base_type.name == "list" and len(generic_args) > 1:
                        self.error(
                            "list 只接受单一元素类型参数（如 list[int]）。"
                            "异构容器请显式声明 list[any]。",
                            annotation, code=SEM_MULTI_TYPE_LIST_REMOVED,
                        )
                    # 使用 registry.resolve_specialization 解析特化
                    result = self.registry.resolve_specialization(base_type, generic_args)
                    return result if result is not None else base_type
                return self._any_desc
            return self._any_desc
        else:
            # 其他类型标注
            return self._any_desc
