"""
Type Checking Base Mixin — Infrastructure methods for TypeCheckingVisitor.

Provides dispatch, diagnostic, and type-resolution helpers shared by every
other TypeCheckingVisitor mixin. Split out from ``type_checking_pass.py``
as part of a pure mechanical refactoring — no logic changes.
"""

from typing import Optional

from core.base.diagnostics.codes import (
    SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE,
    SEM_GENERIC_TYPE_ARG_COUNT,
    SEM_GENERIC_TYPE_NEEDS_ARGS,
    SEM_MULTI_TYPE_LIST_REMOVED,
    SEM_TYPE_MISMATCH,
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
from ._fn_callable import CALLABLE_INTERNAL_TYPE_MSG


def module_qualified_annotation(node: ast.IbASTNode):
    """从点号限定类型注解（IbAttribute 链）提取 (module_path, type_name)。

    ``geo.Counter`` → ("geo", "Counter")；``subpkg.util.Counter`` →
    ("subpkg.util", "Counter")。裸名（IbName）返回 (None, name)；
    其它节点返回 (None, None)。
    """
    parts: list = []
    cur = node
    while isinstance(cur, ast.IbAttribute):
        parts.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.IbName):
        return None, None
    parts.append(cur.id)
    parts.reverse()
    return ".".join(parts[:-1]) or None, parts[-1]


def module_qualified_display(node: ast.IbASTNode) -> str:
    """点号限定类型注解的可读全名（``geo.Counter``）；非限定返回单名。"""
    module, name = module_qualified_annotation(node)
    if name is None:
        return ""
    return f"{module}.{name}" if module else name


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

    def _bind_literal_with_type(self, node: Optional[ast.IbASTNode], spec: Optional[IbSpec]) -> None:
        """把目标特化类型绑到容器字面量节点（含递归内层元素）。

        值创建点类型化的统一传递机制（缺陷二根治推广）：编译期建立
        ``node_to_type = 特化类型``，运行时 VM 字面量 handler 据此水化特化类。
        与简单变量赋值（``_statement_visitors``）同构，覆盖函数返回 / 调用实参 /
        下标赋值 / 嵌套内层元素等全部容器字面量上下文。

        仅容器字面量 + 内置泛型特化目标参与：裸基类（list/dict/tuple/Optional）
        无特化身份，不 bind（保持既有行为）；非容器节点 / 非内置泛型不处理。
        """
        if node is None or spec is None:
            return
        # 条件表达式：结果类型传播到两分支（list[int] a = [1] if c else [2]
        # → [1]/[2] 节点绑 list[int]）。
        if isinstance(node, ast.IbIfExp):
            self._bind_literal_with_type(node.body, spec)
            self._bind_literal_with_type(node.orelse, spec)
            return
        if not isinstance(node, (ast.IbListExpr, ast.IbDict, ast.IbTuple)):
            return
        kind = getattr(spec, "kind", None)
        if kind not in (
            TypeKind.LIST.value,
            TypeKind.TUPLE.value,
            TypeKind.DICT.value,
            TypeKind.OPTIONAL.value,
        ):
            return
        # 裸基类（无特化实参）：name 无方括号，无特化身份，但须显式 bind——
        # 覆盖 S6 容器字面量推断（`list bare = [1,2]` 的 RHS 推断 list[int]，
        # 显式裸声明应强制值层保持裸 list，不水化特化类）。
        if "[" not in spec.name:
            self.bind_type(node, spec)
            return
        # Optional[list[int]] o = [1,2]：容器字面量绑内层 wrapped_type（list[int]），
        # 非 Optional 本身——运行时 _bind_container_specialization 按容器 kind 匹配。
        if kind == TypeKind.OPTIONAL.value:
            wrapped = self.registry.resolve_typeref(spec.wrapped_type) or self._any_desc
            self._bind_literal_with_type(node, wrapped)
            return
        self.bind_type(node, spec)
        # 递归内层元素：从 spec 提取元素类型传内层容器字面量。
        if isinstance(node, ast.IbListExpr) and kind == TypeKind.LIST.value:
            elem = self.registry.resolve_typeref(spec.element_type) or self._any_desc
            for elt in node.elts:
                self._bind_literal_with_type(elt, elem)
        elif isinstance(node, ast.IbDict) and kind == TypeKind.DICT.value:
            val = self.registry.resolve_typeref(spec.value_type) or self._any_desc
            for v in node.values:
                self._bind_literal_with_type(v, val)
        elif isinstance(node, ast.IbTuple) and kind == TypeKind.TUPLE.value:
            positional = getattr(spec, "positional_element_types", None) or []
            if positional:
                for elt, ref in zip(node.elts, positional):
                    inner = self.registry.resolve_typeref(ref) or self._any_desc
                    self._bind_literal_with_type(elt, inner)
            else:
                elem = self.registry.resolve_typeref(spec.element_type) or self._any_desc
                for elt in node.elts:
                    self._bind_literal_with_type(elt, elem)

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
            cur = self.registry.resolve_typeref(parent_ref)
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
        # Protocol-kernel path: from_prompt/parser are now first-class
        # protocols. This replaces the previous hard-coded capability and
        # dunder-member checks.
        if self.registry.satisfies_protocol(spec, "from_prompt"):
            return True
        if self.registry.satisfies_protocol(spec, "parser"):
            return True
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
            resolved = self.registry.resolve_typeref(source)
            if not resolved:
                self.error(
                    f"Unresolved type '{source.head}' in assignability check",
                    self._current_node, code=SEM_UNRESOLVED_TYPE,
                )
                resolved = self._any_desc
            source = resolved
        if isinstance(target, TypeRef):
            resolved = self.registry.resolve_typeref(target)
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
            # callable 是内部类型名（运行期函数对象基类 + 公理族根），不作为用户
            # 可写类型（方向 A：用户面统一为 fn 族）。`callable f`/`-> callable`
            # 报清晰错误而非半成品语义（此前只对 lambda/绑定方法生效、误拒裸函数）。
            if annotation.id == "callable":
                self.error(
                    CALLABLE_INTERNAL_TYPE_MSG,
                    annotation, code=SEM_UNRESOLVED_TYPE,
                )
                return self._any_desc
            # 用户类/泛型函数类型参数：T 解析为占位 spec（非实体类型），
            # 供特化/调用点推断时替换。
            type_param_spec = self._lookup_type_param(annotation.id)
            if type_param_spec is not None:
                return type_param_spec
            resolved = self.registry.resolve(annotation.id)
            if not resolved:
                self.error(
                    f"Unknown type '{annotation.id}'",
                    annotation, code=SEM_UNRESOLVED_TYPE,
                )
                return self._any_desc
            # 泛型类裸用拦截（class Box[T] 无类型参数直接作类型注解 → SEM）。
            # 特化 `Box[int]` 走 IbSubscript 分支，不在此处。
            if resolved.kind == TypeKind.CLASS.value and getattr(resolved, "type_params", None):
                self.error(
                    f"Generic class '{annotation.id}' requires type arguments "
                    f"(e.g. {annotation.id}[int]).",
                    annotation, code=SEM_GENERIC_TYPE_NEEDS_ARGS,
                )
                return self._any_desc
            return resolved
        elif isinstance(annotation, ast.IbAttribute):
            # 模块限定类型注解：geo.Counter / subpkg.util.Counter。
            # 解析目标 spec（跨模块用户类），使行为表达式 node_to_type 等
            # 绑定到带 module 的 spec（CROSSMOD-LLM-1 根治：此前退化 any）。
            module_path, type_name = module_qualified_annotation(annotation)
            if type_name is None:
                return self._any_desc
            resolved = self.registry.resolve(type_name, module=module_path)
            if not resolved:
                self.error(
                    f"Unknown type '{module_qualified_display(annotation)}'",
                    annotation, code=SEM_UNRESOLVED_TYPE,
                )
                return self._any_desc
            # 泛型类裸用拦截（class geo.Box[T] 无类型参数直接作类型注解 → SEM）。
            # 特化 `geo.Box[int]` 走 IbSubscript 分支，不在此处。
            if resolved.kind == TypeKind.CLASS.value and getattr(resolved, "type_params", None):
                self.error(
                    f"Generic class '{module_qualified_display(annotation)}' requires "
                    f"type arguments (e.g. {module_qualified_display(annotation)}[int]).",
                    annotation, code=SEM_GENERIC_TYPE_NEEDS_ARGS,
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
            # 结构化构造（CALLABLE_SIG 签名模型根治）：参数/返回经 TypeRef.from_spec
            # 产结构化 ref（list[int] → TypeRef('list',(int,))；Box[T] 特化 → 
            # TypeRef('Box',(T,))）——替代 TypeRef.of(p.name) 扁平化（head 含方括号、
            # args 空），使 substitute 可穿透嵌套类型参数（Box[T]→Box[int]），
            # resolve_typeref 可结构化恢复。
            return TypeDef(
                name="fn",
                kind=TypeKind.CALLABLE_SIG.value,
                param_types=[
                    TypeRef.from_spec(p) if p is not None else TypeRef.of("any")
                    for p in param_specs
                ],
                return_type=(
                    TypeRef.from_spec(ret_spec) if ret_spec is not None else TypeRef.of("any")
                ),
                provenance=Provenance.KERNEL_NATIVE,
                visibility=Visibility.PRELUDE_VISIBLE,
            )
        elif isinstance(annotation, ast.IbSubscript):
            # 泛型类型：list[int], dict[str, int], tuple[int, str], Optional[int] 等
            if isinstance(annotation.value, (ast.IbName, ast.IbAttribute)):
                if isinstance(annotation.value, ast.IbName):
                    # callable 内部类型名守卫（list[callable] 等基类形态）。
                    if annotation.value.id == "callable":
                        self.error(
                            CALLABLE_INTERNAL_TYPE_MSG,
                            annotation, code=SEM_UNRESOLVED_TYPE,
                        )
                        return self._any_desc
                    base_type = self.registry.resolve(annotation.value.id)
                    base_display = annotation.value.id
                else:
                    module_path, type_name = module_qualified_annotation(annotation.value)
                    base_type = self.registry.resolve(type_name, module=module_path) if type_name else None
                    base_display = module_qualified_display(annotation.value)
                if base_type:
                    # 泛型实参必须为**类型**（IbName/IbSubscript/IbCallableType）。
                    # 字面量/None 等值（Box[42]）是非法特化——fail-fast 而非
                    # 运行期裸 AttributeError。
                    if isinstance(annotation.slice, ast.IbConstant):
                        self.error(
                            f"Generic type argument must be a type, not a value "
                            f"('{annotation.slice.value}'). Use e.g. "
                            f"{base_display}[int].",
                            annotation, code=SEM_GENERIC_TYPE_NEEDS_ARGS,
                        )
                        return self._any_desc
                    # 解析泛型参数
                    if isinstance(annotation.slice, ast.IbTuple):
                        generic_args = [self._resolve_type(elt) for elt in annotation.slice.elts]
                    else:
                        generic_args = [self._resolve_type(annotation.slice)]
                    # 泛型实参不得为哨兵/动态类型（None/auto）——它们不是实体类型，
                    # 特化会产生幻影 spec（Box[None]）。void 仅对内置 thread 合法
                    # （thread[void] 无返回线程）；用户泛型/其它 base 拒绝。
                    for _ga in generic_args:
                        _ga_name = getattr(_ga, "name", None)
                        _void_ok = (
                            _ga_name == "void"
                            and base_type.name == "thread"
                            and base_type.kind == TypeKind.THREAD.value
                        )
                        if _ga is not None and (_ga_name in ("None", "auto") or (_ga_name == "void" and not _void_ok)):
                            self.error(
                                f"Generic type argument '{_ga_name}' is not a concrete "
                                f"type. Use an entity type such as int/str/list[..].",
                                annotation, code=SEM_GENERIC_TYPE_NEEDS_ARGS,
                            )
                            return self._any_desc
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
                    if result is not None:
                        return result
                    # 用户类泛型类型参数协议约束失败（resolve_specialization 拒绝）→ SEM。
                    if (base_type.kind == TypeKind.CLASS.value
                            and getattr(base_type, "type_params", None)):
                        bound_errors = self.registry.type_param_bound_errors(
                            base_type, generic_args
                        )
                        if bound_errors:
                            for msg in bound_errors:
                                self.error(
                                    msg,
                                    annotation,
                                    code=SEM_TYPE_MISMATCH,
                                )
                            return self._any_desc
                    # 用户类泛型实参数量不匹配（resolve_specialization 拒绝构造）→ SEM。
                    if (base_type.kind == TypeKind.CLASS.value
                            and getattr(base_type, "type_params", None)
                            and len(generic_args) != len(base_type.type_params)):
                        self.error(
                            f"Generic class '{base_type.name}' expects "
                            f"{len(base_type.type_params)} type argument(s), "
                            f"got {len(generic_args)}.",
                            annotation, code=SEM_GENERIC_TYPE_ARG_COUNT,
                        )
                        return self._any_desc
                    return base_type
                return self._any_desc
            return self._any_desc
        else:
            # 其他类型标注
            return self._any_desc

    def _lookup_type_param(self, name: str) -> Optional[IbSpec]:
        """在类/泛型函数作用域内查找类型参数（class Box[T] / func f[T] 的 T）。

        权威源 = ``current_class.type_params`` 或
        ``current_function_type_params``。命中返回占位 spec（TYPE_PARAM kind）。
        """
        from core.kernel.spec.base import TypeKind
        cls_spec = self.current_class
        if cls_spec is not None and getattr(cls_spec, "type_params", None) and name in cls_spec.type_params:
            return TypeDef(
                name=name,
                kind=TypeKind.TYPE_PARAM.value,
                provenance=cls_spec.provenance,
                visibility=cls_spec.visibility,
            )
        if self.current_function_type_params and name in self.current_function_type_params:
            return TypeDef(
                name=name,
                kind=TypeKind.TYPE_PARAM.value,
                provenance=Provenance.USER_DEFINED,
                visibility=Visibility.IMPORT_GATED,
            )
        return None
