"""
Declaration Visitors Mixin for TypeCheckingVisitor.

Holds the visit methods for declaration AST nodes (class / function /
LLM-function) plus the override-compatibility helper. Split out from
``type_checking_pass.py`` as part of a pure mechanical refactoring —
no logic changes.
"""

from typing import Optional
from core.base.enums import Provenance, Visibility

from core.base.diagnostics.codes import (
    SEM_DEFAULT_TYPE_MISMATCH,
    SEM_DUAL_ASSIGNABLE,
    SEM_MISSING_RETURN_ANNOTATION,
    SEM_PROTOCOL_SIGNATURE,
    SEM_TYPE_MISMATCH,
)
from core.kernel import ast
from core.kernel.symbols import SymbolTable, SymbolKind, VariableSymbol
from core.kernel.spec import IbSpec
from core.kernel.spec.base import TypeKind
from core.kernel.spec.type_ref import TypeRef
from core.kernel.spec.member import ParamDescriptor
from core.kernel.axioms.prompt_protocol import (
    validate_prompt_protocol_signature,
    is_prompt_protocol_method,
)


def _contains_yield(stmts) -> bool:
    """扫描语句列表是否含 ``IbYieldExpr`` / ``IbYieldFromExpr``（含嵌套 lambda 体，排除嵌套函数定义）。

    用于标记函数为惰性生成器（D-08 自标记函数种类）。不进入嵌套函数定义
    （``IbFunctionDef``/``IbLLMFunctionDef``/``IbClassDef``）——内层 yield 归属其自身。
    """
    from core.kernel import ast as _ast

    def _scan_stmt(stmt) -> bool:
        if isinstance(stmt, (_ast.IbFunctionDef, _ast.IbLLMFunctionDef, _ast.IbClassDef)):
            return False
        for attr in vars(stmt).values():
            if isinstance(attr, (_ast.IbYieldExpr, _ast.IbYieldFromExpr)):
                return True
            if isinstance(attr, list):
                for item in attr:
                    if isinstance(item, _ast.IbASTNode) and _scan_stmt(item):
                        return True
            elif isinstance(attr, _ast.IbASTNode) and _scan_stmt(attr):
                return True
        return False

    return any(_scan_stmt(s) for s in stmts or [])

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

        # 静态名义强类型：函数必须声明返回类型（显式 TYPE / auto 推断 / any 逃生）。
        # 缺标注不再静默回填 any（曾击穿类型推断与泛型体系）。
        if node.returns is None:
            self.error(
                f"Function '{node.name}' must declare a return type. "
                "Add '-> TYPE', '-> auto', or '-> any'.",
                node, code=SEM_MISSING_RETURN_ANNOTATION
            )

        # 参数签名唯一权威：解析类型 + 描述符 + 定义处默认值校验
        param_types, param_descriptors = self._build_function_signature(node.args)

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
            updated_spec = self.registry.factory.create_func(
                name=node.name,
                param_type_names=param_type_names,
                return_type_name=ret_type_name,
                provenance=Provenance.USER_DEFINED,
                visibility=Visibility.IMPORT_GATED,
            )
            updated_spec.param_descriptors = param_descriptors
            sym.spec = updated_spec

        # 同步精化后的签名到类成员表（运行期契约校验消费）
        self._sync_class_member(node.name, param_descriptors)

        # 创建函数作用域
        func_scope = SymbolTable(parent=self.current_scope, name=node.name)
        if sym and hasattr(sym, 'owned_scope'):
            sym.owned_scope = func_scope

        old_in_function = self.in_function_def
        old_auto_returns = self.auto_return_types

        self.in_function_def = True
        if is_auto_return:
            self.auto_return_types = []

        # 当前函数返回类型入栈（visit_IbReturn 绑定返回字面量特化类型用）。
        # 显式返回类型即 ret_type；auto 在函数体遍历后统一推断回填。
        func_returns = self.func_return_types
        func_returns.append(ret_type if not is_auto_return else None)

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
                        node, code=SEM_TYPE_MISMATCH
                    )
                    inferred_return = self._any_desc
                # 更新符号的返回类型
                if sym and sym.spec and hasattr(sym.spec, 'return_type'):
                    sym.spec.return_type = TypeRef.of(inferred_return.name, getattr(inferred_return, "module_path", None))

        finally:
            self.pop_scope()
            self.in_function_def = old_in_function
            self.auto_return_types = old_auto_returns
            if func_returns:
                func_returns.pop()

        # 含 yield → 惰性生成器（D-08 自标记函数种类）。扫描函数体（含嵌套
        # lambda，但排除嵌套函数定义——嵌套函数的 yield 归属其自身）。
        node.is_generator = _contains_yield(node.body)

        # 生成器函数的返回类型 = generator[元素类型]（yield 值的类型即元素类型）。
        # 声明层解析的元素类型（ret_type）作为生成器元素；函数符号返回类型改为
        # generator[T]，使 ``auto g = gen()`` / ``for`` 消费正确定型。
        # 显式 ``-> generator[T]`` 标注时 ret_type 已是 generator 特化 spec，
        # 直接用（不二次包裹——否则 generator[generator[T]] 双包致调用点退化 any）。
        if node.is_generator and sym and sym.spec and hasattr(sym.spec, 'return_type'):
            ret_base = ret_type.get_base_name() if ret_type is not None else None
            if ret_base == "generator":
                sym.spec.return_type = TypeRef.from_spec(ret_type)
            else:
                elem_name = ret_type.name if ret_type else "any"
                elem_mod = getattr(ret_type, "module_path", None) if ret_type else None
                gen_spec = self.registry.factory.create_generator(
                    value_type_name=elem_name, value_type_module=elem_mod
                )
                sym.spec.return_type = TypeRef.from_spec(gen_spec)

        # SEM_DUAL_ASSIGNABLE: Method override signature compatibility check
        if self.in_class_def and self.current_class and sym and sym.spec:
            self._check_override_compatibility(node, sym.spec)

        # SEM_PROTOCOL_SIGNATURE: Prompt protocol signature validation
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
                self.warn(diag_msg, node, code=SEM_PROTOCOL_SIGNATURE)

        return None

    @staticmethod
    def _extract_arg_name(arg_node) -> Optional[str]:
        """从参数节点提取参数名。IbArg now has annotation field directly."""
        if isinstance(arg_node, ast.IbArg):
            return arg_node.arg
        return None

    def _check_override_compatibility(self, node: ast.IbFunctionDef, child_spec: IbSpec):
        """SEM_DUAL_ASSIGNABLE: Check that overriding method's signature is compatible with parent.

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
            # 子类允许增加参数，但多出的参数必须带默认值或为 varargs，
            # 否则按父类签名的调用方在子类上会缺少实参。
            # param_descriptors 不含 self，故与 child_params 差一个偏移。
            child_desc = getattr(child_spec, 'param_descriptors', None) or []
            extra = len(child_params) - len(parent_params)
            flexible = False
            if extra > 0 and len(child_desc) >= extra:
                flexible = all(
                    d.has_default or d.kind in (ast.ARG_VAR_POSITIONAL, ast.ARG_VAR_KEYWORD)
                    for d in child_desc[-extra:]
                )
            if not flexible:
                self.warn(
                    f"Method '{method_name}' overrides parent with "
                    f"{len(parent_params)} parameter(s), but defines "
                    f"{len(child_params)} parameter(s).",
                    node, code=SEM_DUAL_ASSIGNABLE,
                    hint=f"Parent signature has {len(parent_params)} parameters (including self). "
                         f"Ensure override matches the parent signature."
                )
                return  # Cannot check individual params if count differs
            # 子类多出的参数均有默认值 / varargs：只对父类签名部分做类型对比
            child_params = child_params[: len(parent_params)]

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
                    node, code=SEM_DUAL_ASSIGNABLE,
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
                        node, code=SEM_DUAL_ASSIGNABLE,
                        hint=f"Override return type should be assignable to parent's return type."
                    )

    def visit_IbLLMFunctionDef(self, node: ast.IbLLMFunctionDef) -> Optional[IbSpec]:
        """访问 LLM 函数定义 — 与 visit_IbFunctionDef 对称：精化签名并回填 spec。"""
        sym = self.lookup_symbol(node.name)

        # 同 visit_IbFunctionDef：LLM 函数必须声明返回类型（LLM 输出解析的目标类型）。
        if node.returns is None:
            self.error(
                f"LLM function '{node.name}' must declare a return type. "
                "Add '-> TYPE', '-> auto', or '-> any'.",
                node, code=SEM_MISSING_RETURN_ANNOTATION
            )

        # 参数签名唯一权威（同 visit_IbFunctionDef）
        param_types, param_descriptors = self._build_function_signature(node.args)

        if self.in_class_def and self.current_class:
            param_types.insert(0, self.current_class)

        ret_type = self._resolve_type(node.returns) if node.returns else self._any_desc

        if sym and sym.spec and self.registry:
            param_type_names = [(p.name if p else "any") for p in param_types]
            ret_type_name = ret_type.name if ret_type else "void"
            updated_spec = self.registry.factory.create_func(
                name=node.name,
                param_type_names=param_type_names,
                return_type_name=ret_type_name,
                provenance=Provenance.USER_DEFINED,
                visibility=Visibility.IMPORT_GATED,
            )
            updated_spec.param_descriptors = param_descriptors
            sym.spec = updated_spec

        self._sync_class_member(node.name, param_descriptors)

        # 创建函数作用域
        func_scope = SymbolTable(parent=self.current_scope, name=node.name)

        old_in_function = self.in_function_def
        self.in_function_def = True
        self.push_scope(func_scope)

        try:
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

    def _build_function_signature(self, args):
        """构建函数参数签名（唯一权威，type-check 阶段，解析后精度）。

        对每个参数：解析标注类型、构建 ParamDescriptor（name/kind/type/has_default）、
        在包围作用域求值并校验默认值类型可赋值性（SEM_DEFAULT_TYPE_MISMATCH）。

        返回 (param_types, param_descriptors)；两者都不含 self（调用方按需插入）。
        """
        param_types = []
        param_descriptors = []
        for arg_node in args:
            arg_type = self._resolve_type(arg_node.annotation) if arg_node.annotation else self._any_desc
            param_types.append(arg_type)
            param_descriptors.append(ParamDescriptor(
                name=arg_node.arg,
                kind=arg_node.kind,
                type_ref=self._param_type_ref(arg_type),
                has_default=arg_node.default is not None,
            ))
            if arg_node.default is not None and arg_node.kind in (ast.ARG_POSITIONAL_OR_KEYWORD, ast.ARG_KEYWORD_ONLY):
                default_spec = self.visit(arg_node.default)
                # 默认值容器字面量绑定参数特化类型（func f(list[int] items=[1,2])
                # → [1,2] 节点 node_to_type = list[int]），运行时默认值创建据此
                # 水化特化类（缺陷二根治推广：函数默认参数路径值层身份保真）。
                self._bind_literal_with_type(arg_node.default, arg_type)
                if (default_spec and arg_type != self._any_desc
                        and not self.registry.is_dynamic(default_spec)
                        and not self.registry.is_dynamic(arg_type)
                        and not self.registry.is_assignable(default_spec, arg_type)):
                    self.error(
                        f"Default value for parameter '{arg_node.arg}' has type "
                        f"'{default_spec.name}', but the parameter is declared "
                        f"'{arg_type.name}'.",
                        arg_node, code=SEM_DEFAULT_TYPE_MISMATCH,
                    )
        return param_types, param_descriptors

    @staticmethod
    def _param_type_ref(arg_type: IbSpec) -> TypeRef:
        """把参数类型转成 descriptor 的 TypeRef。

        ``fn[(args) -> ret]``（CALLABLE_SIG）必须保留结构签名，否则扁平化为
        ``TypeRef('fn')`` 后调用点只见到裸 fn（动态）而跳过校验，导致
        ``fn[()->int]`` 参数收到返回类型不匹配的可调用时编译放行、运行期失败。
        结构化形态：``TypeRef('fn', (TypeRef('__args__', <params>), <ret>))``。

        其余类型统一走 ``TypeRef.from_spec``（结构化构造，保留泛型实参）——
        避免 ``TypeRef.of(name)`` 对泛型类参数（``Vec[T]``/``Vec[int]``）扁平化为
        ``TypeRef('Vec[T]')``（head 含方括号、args 空），导致特化时
        ``TypeRef.substitute`` 无法替换、调用点参数校验失效（GEN-6B）。
        """
        if getattr(arg_type, "kind", None) == TypeKind.CALLABLE_SIG.value:
            params = tuple(
                TypeRef.of(p.head, getattr(p, "module", None))
                for p in arg_type.param_types
            )
            ret = arg_type.return_type
            return TypeRef(
                "fn",
                (TypeRef("__args__", params), TypeRef.of(ret.head, getattr(ret, "module", None))),
                getattr(arg_type, "module_path", None),
            )
        return TypeRef.from_spec(arg_type)

    def _sync_class_member(self, method_name: str, param_descriptors: list) -> None:
        """把精化后的参数描述符同步到类成员表（供运行期契约校验消费）。

        泛型类特化成员同步：基类 descriptors 回填后，把当前类所有特化 spec
        （``Box[int]``）的对应成员 descriptors 同步替换——特化 spec 在
        ``resolve_specialization`` 时构造，早于此处回填，须随基类一并精化
        （类型参数占位 → 实参由各特化 spec 构造时替换）。
        """
        if not (self.in_class_def and self.current_class):
            return
        member = self.current_class.members.get(method_name)
        if member is not None:
            member.param_descriptors = list(param_descriptors)
            # 同步特化类成员（class Box[T] → Box[int] 的同一方法）。
            if getattr(self.current_class, "type_params", None):
                self._sync_specialized_members(method_name, param_descriptors)

    def _sync_specialized_members(self, method_name: str, param_descriptors: list) -> None:
        """把基类方法 descriptors 同步到所有特化类同名成员（类型参数替换）。

        遍历 registry 中所有 ``{base_name}[...]`` 特化 spec，对其同名成员用
        各特化 spec 的 ``type_args``（结构化实参）与基类 ``type_params``
        配对构造映射，替换 descriptors 中的类型参数。特化 spec 的 type_args
        由 ``_specialize_user_class`` 填充（非字符串反推——单一权威源）。
        """
        base_name = self.current_class.name
        base_type_params = list(getattr(self.current_class, "type_params", []) or [])
        if not base_type_params:
            return
        all_specs = getattr(self.registry, "all_specs", {}) or {}
        for spec in all_specs.values():
            spec_name = getattr(spec, "name", "")
            if not spec_name.startswith(base_name + "["):
                continue
            type_args = getattr(spec, "type_args", None) or []
            if len(type_args) != len(base_type_params):
                continue
            m = spec.members.get(method_name)
            if m is None or not hasattr(m, "param_descriptors"):
                continue
            mapping = {
                param: arg for param, arg in zip(base_type_params, type_args)
            }
            m.param_descriptors = [
                ParamDescriptor(
                    name=d.name,
                    kind=d.kind,
                    type_ref=d.type_ref.substitute(mapping) if mapping else d.type_ref,
                    has_default=d.has_default,
                    default_value=d.default_value,
                )
                for d in param_descriptors
            ]
