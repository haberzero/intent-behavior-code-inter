"""
Expression Visitors Mixin for TypeCheckingVisitor.

Holds the visit methods for expression AST nodes:
literals, operators, calls (+ legality checks), attribute/subscript
access, and higher-order/behavior constructs. Split out from
``type_checking_pass.py`` as part of a pure mechanical refactoring —
no logic changes.
"""

from typing import Optional

from core.base.diagnostics.codes import (
    SEM_ARG_COUNT_MISMATCH,
    SEM_CAST_NO_CONVERTER,
    SEM_CONTAINER_METHOD_HINT,
    SEM_DUPLICATE_KEYWORD,
    SEM_INTENT_STATIC_CALL,
    SEM_MISSING_REQUIRED_ARG,
    SEM_SUPER_OUTSIDE_METHOD,
    SEM_TOO_MANY_POSITIONAL,
    SEM_TYPE_MISMATCH,
    SEM_UNKNOWN_KEYWORD,
    SEM_UNRESOLVED_TYPE,
    ICE_TYPE_LEAK,
)
from core.kernel import ast
from core.kernel.arg_binding import (
    MISSING_REQUIRED,
    TOO_MANY_POSITIONAL,
    ParamDecl,
    resolve_call_binding,
)
from core.kernel.symbols import SymbolTable, SymbolKind, VariableSymbol
from core.kernel.spec import IbSpec
from core.kernel.spec.base import TypeKind
from core.kernel.spec.type_ref import TypeRef


class ExpressionVisitorsMixin:
    """Expression visit methods (literals, operators, calls, access, HOF)."""

    # ========== 字面量 ==========

    def visit_IbName(self, node: ast.IbName) -> Optional[IbSpec]:
        """访问名称引用"""
        sym = self.lookup_symbol(node.id)
        if sym and sym.spec:
            spec = sym.spec
            if isinstance(spec, TypeRef):
                self.error(
                    f"Internal: unresolved TypeRef '{spec.head}' in symbol "
                    f"'{node.id}' reached type checking (symbol spec leak)",
                    node, code=ICE_TYPE_LEAK,
                )
                spec = self.registry.resolve(spec.head) or self._any_desc
            self.bind_type(node, spec)
            return spec
        # 未定义符号在 SymbolPhase 已报错，这里返回 any
        return self._any_desc

    def visit_IbConstant(self, node: ast.IbConstant) -> Optional[IbSpec]:
        """访问常量字面量（int, float, str, bool, None）"""
        # 使用 registry 根据值类型解析描述符
        val = node.value
        spec = self.registry.resolve_from_value(val)
        if spec:
            self.bind_type(node, spec)
            return spec
        # Fallback 到 any
        self.bind_type(node, self._any_desc)
        return self._any_desc

    def visit_IbListExpr(self, node: ast.IbListExpr) -> Optional[IbSpec]:
        """访问列表字面量"""
        for elt in node.elts:
            self.visit(elt)
        # 简化处理：返回 list 类型
        list_type = self.registry.resolve("list")
        self.bind_type(node, list_type)
        return list_type

    def visit_IbDict(self, node: ast.IbDict) -> Optional[IbSpec]:
        """访问字典字面量"""
        for key, value in zip(node.keys, node.values):
            self.visit(key)
            self.visit(value)
        dict_type = self.registry.resolve("dict")
        self.bind_type(node, dict_type)
        return dict_type

    def visit_IbTuple(self, node: ast.IbTuple) -> Optional[IbSpec]:
        """访问元组字面量"""
        for elt in node.elts:
            self.visit(elt)
        tuple_type = self.registry.resolve("tuple")
        self.bind_type(node, tuple_type)
        return tuple_type

    # ========== 运算符 ==========

    def visit_IbBinOp(self, node: ast.IbBinOp) -> Optional[IbSpec]:
        """访问二元运算"""
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)

        # any 类型与任何操作兼容（permissive semantics）
        if left_type == self._any_desc or right_type == self._any_desc:
            self.bind_type(node, self._any_desc)
            return self._any_desc

        # ── behavior 操作数适配 ──
        # 行为表达式的结果类型由上下文决定（与 visit_IbAssign 中的适配逻辑对齐）。
        # 当 behavior 出现在二元运算中，根据另一侧的具体类型进行适配。
        left_is_behavior = (left_type == self._behavior_desc)
        right_is_behavior = (right_type == self._behavior_desc)
        if left_is_behavior or right_is_behavior:
            if left_is_behavior and right_is_behavior:
                # 双侧均为 behavior：退化为 str（与无类型标注赋值一致）
                adapted = self._str_desc
                self.bind_type(node.left, adapted)
                self.bind_type(node.right, adapted)
                result_type = adapted
            elif left_is_behavior:
                # 左侧 behavior 适配为右侧类型
                self.bind_type(node.left, right_type)
                left_type = right_type
                result_type = self.registry.resolve_op(left_type, node.op, right_type)
                if not result_type:
                    result_type = right_type
            else:
                # 右侧 behavior 适配为左侧类型
                self.bind_type(node.right, left_type)
                right_type = left_type
                result_type = self.registry.resolve_op(left_type, node.op, right_type)
                if not result_type:
                    result_type = left_type
            self.bind_type(node, result_type)
            return result_type

        # 贯彻"一切皆对象"：调用左操作数的公理自决议方法
        result_type = self.registry.resolve_op(left_type, node.op, right_type) if left_type else None
        if not result_type:
            # Fallback: 基础数值推断
            if left_type in (self._int_desc, self._float_desc) and right_type in (self._int_desc, self._float_desc):
                result_type = self._float_desc if (left_type == self._float_desc or right_type == self._float_desc) else self._int_desc
            elif left_type == self._str_desc or right_type == self._str_desc:
                result_type = self._str_desc
            else:
                self.error(
                    f"Binary operator '{node.op}' not supported for types "
                    f"'{left_type.name if left_type else 'unknown'}' and "
                    f"'{right_type.name if right_type else 'unknown'}'",
                    node, code=SEM_TYPE_MISMATCH
                )
                result_type = self._any_desc

        self.bind_type(node, result_type)
        return result_type

    def visit_IbUnaryOp(self, node: ast.IbUnaryOp) -> Optional[IbSpec]:
        """访问一元运算"""
        operand_type = self.visit(node.operand)

        # 贯彻"一切皆对象"：调用操作数的自决议方法 (other=None 表示一元运算)
        result_type = self.registry.resolve_op(operand_type, node.op, None) if operand_type else None
        if not result_type:
            # Fallback: 保持操作数类型
            result_type = operand_type or self._any_desc

        self.bind_type(node, result_type)
        return result_type

    def visit_IbAwaitExpr(self, node: ast.IbAwaitExpr) -> Optional[IbSpec]:
        """访问 ``await <expr>``：显式等待一个 Waitable 完成。

        操作数的静态类型即其等待后的结果类型（LLMFuture 变量声明类型 / 容器
        元素类型 / 宿主结果类型）。``await`` 不改变类型，仅等待。
        """
        operand_type = self.visit(node.value)
        result_type = operand_type or self._any_desc
        self.bind_type(node, result_type)
        return result_type

    def visit_IbChannelExpr(self, node: ast.IbChannelExpr) -> Optional[IbSpec]:
        """``chan(T, ...)`` 的类型 = chan。

        元素类型 ``T`` 经 type_name 解析；当前保守返回 ``chan`` 基类型。
        """
        if node.type_name:
            self.registry.resolve(node.type_name)  # 触发解析校验
        chan_spec = self.registry.resolve("chan") or self._any_desc
        self.bind_type(node, chan_spec)
        return chan_spec

    def visit_IbSlotExpr(self, node: ast.IbSlotExpr) -> Optional[IbSpec]:
        """``slot(...)`` 的类型 = slot。"""
        if node.value is not None:
            self.visit(node.value)
        slot_spec = self.registry.resolve("slot") or self._any_desc
        self.bind_type(node, slot_spec)
        return slot_spec

    def visit_IbCompare(self, node: ast.IbCompare) -> Optional[IbSpec]:
        """访问比较运算"""
        left_type = self.visit(node.left)
        for comparator in node.comparators:
            self.visit(comparator)

        # ── behavior 操作数适配 ──
        # 比较运算中 behavior 操作数适配为另一侧类型，整体返回 bool。
        if left_type == self._behavior_desc:
            # 左侧为 behavior：根据第一个 comparator 类型适配
            if node.comparators:
                comp_type = self.type_bindings.get(node.comparators[0])
                if comp_type and comp_type != self._behavior_desc:
                    self.bind_type(node.left, comp_type)
        else:
            # 检查 comparators 中的 behavior 并适配为左侧类型
            if left_type:
                for comparator in node.comparators:
                    comp_type = self.type_bindings.get(comparator)
                    if comp_type == self._behavior_desc:
                        self.bind_type(comparator, left_type)

        # 比较运算通过 resolve_op 确认合法性（大部分返回 bool）
        if left_type and node.ops:
            result_type = self.registry.resolve_op(left_type, node.ops[0], None)
            if result_type:
                self.bind_type(node, result_type)
                return result_type

        # 默认比较返回 bool
        self.bind_type(node, self._bool_desc)
        return self._bool_desc

    def visit_IbBoolOp(self, node: ast.IbBoolOp) -> Optional[IbSpec]:
        """访问布尔运算 (and/or)"""
        for val in node.values:
            self.visit(val)
        self.bind_type(node, self._bool_desc)
        return self._bool_desc

    def visit_IbIfExp(self, node: ast.IbIfExp) -> Optional[IbSpec]:
        """访问条件表达式 (x if cond else y)"""
        self.visit(node.test)
        # 条件表达式的 test 恒为布尔位置
        self._bind_condition_behavior_types(node.test)
        body_type = self.visit(node.body)
        orelse_type = self.visit(node.orelse)
        # 两分支类型一致则返回该类型，否则返回 any
        if body_type and orelse_type and body_type.name == orelse_type.name:
            result_type = body_type
        else:
            result_type = self._any_desc
        self.bind_type(node, result_type)
        return result_type

    # ========== 调用与合法性检查 ==========

    # Methods on intent_context that are no-op when called on the class object
    # (as opposed to an instance obtained via get_current()).
    _INTENT_CTX_INSTANCE_ONLY_METHODS = frozenset({
        "push", "pop", "fork", "merge", "combine", "clear",
    })

    def visit_IbCall(self, node: ast.IbCall) -> Optional[IbSpec]:
        """访问函数调用 — 统一实参解析 + 使用 registry.resolve_call_return() 推断返回类型"""
        # 处理被调用对象
        func_type = self.visit(node.func)

        # --- 结构化实参收集：位置 / 序列解包 / 具名 / 字典解包 ---
        positional_specs: list = []
        starred_specs: list = []          # *expr：静态数量未知
        keyword_specs: list = []          # (name, spec)；name None 表示 **expr
        for arg in node.args:
            if isinstance(arg, ast.IbStarred):
                starred_specs.append(self.visit(arg.value))
            else:
                positional_specs.append(self.visit(arg))
        for kw in node.keywords:
            keyword_specs.append((kw.arg, self.visit(kw.value)))

        if not func_type:
            self.bind_type(node, self._any_desc)
            return self._any_desc

        # --- intent_context static call warning (SEM_INTENT_STATIC_CALL) ---
        # Detect intent_context.push() / pop() / ... called directly on the
        # class name without first obtaining an instance via get_current().
        self._check_intent_context_static_call(node)

        # --- SEM_SUPER_OUTSIDE_METHOD: super() called outside class method ---
        self._check_super_call_legality(node)

        # --- Callable class instance detection ---
        # If func_type is CLASS but the name refers to an *instance* variable
        # (not a type reference), route through __call__ protocol.
        if func_type.kind == TypeKind.CLASS.value and isinstance(node.func, ast.IbName):
            sym = self.lookup_symbol(node.func.id)
            if sym and not sym.is_type and '__call__' in func_type.members:
                def scope_lookup(class_name: str, method_name: str) -> Optional[IbSpec]:
                    class_sym = self.lookup_symbol(class_name)
                    if class_sym and hasattr(class_sym, 'owned_scope') and class_sym.owned_scope:
                        method_sym = class_sym.owned_scope.resolve(method_name)
                        if method_sym and method_sym.spec:
                            return method_sym.spec
                    return None

                ret = self.registry.resolve_callable_instance_return(
                    func_type, positional_specs, class_scope_lookup=scope_lookup
                )
                if ret:
                    self.bind_type(node, ret)
                    return ret

        # --- Callability check ---
        call_trait = self.registry.get_call_cap(func_type)
        if not call_trait:
            self.error(f"Type '{func_type.name}' is not callable", node, code=SEM_TYPE_MISMATCH)
            self.bind_type(node, self._any_desc)
            return self._any_desc

        # --- 统一实参解析：单一入口，按调用体可用静态签名选择解析策略 ---
        arg_specs = self._resolve_call_arguments(
            node, func_type, positional_specs, starred_specs, keyword_specs,
        )

        # --- Unified return type resolution ---
        # 单一入口：resolve_call_return 已覆盖直读 return_type 的兜底（Layer 6）；
        # 此处不再重复直读，避免双通道。未解析则回退 any。
        res = self.registry.resolve_call_return(func_type, arg_specs or [])

        if not res:
            res = self._any_desc

        self.bind_type(node, res)
        return res

    def _resolve_call_arguments(
        self,
        node: ast.IbCall,
        func_type: IbSpec,
        positional_specs: list,
        starred_specs: list,
        keyword_specs: list,
    ) -> list:
        """统一实参解析：单一入口，按调用体可用的静态签名选择解析策略。

        策略一：``param_descriptors`` 存在（用户/LLM 函数；vtable 模块函数在
          签名升级后同样进入此路径）→ 全量解析：位置 → 具名 → 默认填充 →
          varargs/varkw，结构/类型错误（SEM_* 新码）。
        策略二：仅 ``param_types``（结构化签名 ``fn[...]``、容器特化方法）
          → 位置数量 + 类型检查。容器方法无具名签名，故只按位置校验。
        策略三：无静态签名（内置构造器 / axiom-backed / 运行时 callable）
          → 动态跳过，不报告。

        返回位置实参类型列表（供返回类型推断的近似输入）。
        """
        descriptors = getattr(func_type, "param_descriptors", None) or []
        if descriptors:
            return self._resolve_with_descriptors(
                node, func_type, descriptors,
                positional_specs, starred_specs, keyword_specs,
            )

        param_types = getattr(func_type, "param_types", None) or []
        if not param_types:
            return positional_specs  # 策略三：无静态签名

        # 策略二：仅位置签名
        if func_type.kind == TypeKind.CALLABLE_SIG.value:
            expected_names = [t.head for t in param_types]
            if len(positional_specs) != len(expected_names):
                self.error(
                    f"Callable expected {len(expected_names)} argument(s), "
                    f"but got {len(positional_specs)}.",
                    node, code=SEM_ARG_COUNT_MISMATCH,
                )
            else:
                for i, (exp_name, actual_type) in enumerate(zip(expected_names, positional_specs)):
                    exp_spec = self.registry.resolve(exp_name)
                    if (exp_spec and actual_type
                            and not self.registry.is_dynamic(exp_spec)
                            and not self.registry.is_dynamic(actual_type)
                            and not self.registry.is_assignable(actual_type, exp_spec)):
                        self.error(
                            f"Argument {i + 1} type mismatch: expected '{exp_name}', "
                            f"but got '{actual_type.name}'.",
                            node, code=SEM_TYPE_MISMATCH,
                            hint=self.registry.get_diff_hint(actual_type, exp_spec),
                        )
        elif func_type.kind == TypeKind.FUNCTION.value:
            # 容器特化写方法的类型提示（如 list[int].append("x")）
            param_type_names = [t.head for t in param_types]
            for i, (expected_name, actual_type) in enumerate(zip(param_type_names, positional_specs)):
                if expected_name == "any":
                    continue
                if actual_type is None:
                    continue
                exp_spec = self.registry.resolve(expected_name)
                if (exp_spec and not self.registry.is_dynamic(actual_type)
                        and not self.registry.is_assignable(actual_type, exp_spec)):
                    self.warn(
                        f"Argument {i + 1} type mismatch: expected '{expected_name}', "
                        f"got '{actual_type.name}'",
                        node, code=SEM_CONTAINER_METHOD_HINT,
                        hint=self.registry.get_diff_hint(actual_type, exp_spec),
                    )

        return positional_specs

    def _resolve_with_descriptors(
        self,
        node: ast.IbCall,
        func_type: IbSpec,
        descriptors: list,
        positional_specs: list,
        starred_specs: list,
        keyword_specs: list,
    ) -> list:
        """参数描述符驱动的实参解析：位置 → 具名 → 默认填充 → varargs/varkw。

        绑定算法收敛于 `core.kernel.arg_binding.resolve_call_binding`（共享纯核心）；
        本方法把其中性问题映射为 SEM_* 诊断，并对绑定实参做类型校验。
        返回位置实参类型列表（供返回类型推断的近似输入）。
        """
        params = [
            ParamDecl(name=d.name, kind=d.kind, has_default=d.has_default)
            for d in descriptors
        ]
        binding = resolve_call_binding(params, positional_specs, keyword_specs)

        # 位置实参类型校验（按声明序）；*args 之后的 keyword-only 槽不参与位置绑定
        pos_or_kw_count = sum(
            1 for d in descriptors if d.kind == ast.ARG_POSITIONAL_OR_KEYWORD
        )
        for i, actual in enumerate(positional_specs[:pos_or_kw_count]):
            self._check_call_arg_type(node, descriptors[i].name, actual, descriptors[i])

        # 具名实参：重复 / 未知 结构错误 + 绑定槽位类型校验（按关键字序）
        for (name, actual), outcome in zip(keyword_specs, binding.keyword_outcomes):
            if outcome[0] == "bound":
                desc = descriptors[outcome[1]]
                self._check_call_arg_type(node, name, actual, desc)
            elif outcome[0] == "duplicate":
                self.error(
                    f"Keyword argument '{name}' provided multiple times.",
                    node, code=SEM_DUPLICATE_KEYWORD,
                )
            elif outcome[0] == "unknown":
                self.error(
                    f"Function '{func_type.name}' has no parameter named '{name}'.",
                    node, code=SEM_UNKNOWN_KEYWORD,
                )

        # 结构性问题：*expr/**expr 存在时缺失必填与位置超限交由运行期裁决
        has_dynamic = bool(starred_specs) or any(
            name is None for name, _ in keyword_specs
        )
        for issue in binding.issues:
            if issue.code == TOO_MANY_POSITIONAL:
                if not has_dynamic:
                    self.error(
                        f"Function '{func_type.name}' expects at most "
                        f"{pos_or_kw_count} positional argument(s), "
                        f"but got {len(positional_specs)}.",
                        node, code=SEM_TOO_MANY_POSITIONAL,
                    )
            elif issue.code == MISSING_REQUIRED:
                if not has_dynamic:
                    self.error(
                        f"Function '{func_type.name}' missing required "
                        f"argument '{issue.name}'.",
                        node, code=SEM_MISSING_REQUIRED_ARG,
                    )

        return positional_specs

    def _check_call_arg_type(self, node: ast.IbCall, name: str, actual_spec, descriptor) -> None:
        """单参数类型可赋值性校验（SEM_TYPE_MISMATCH）。"""
        if not descriptor.type_ref:
            return
        exp_spec = self.registry.resolve_typeref(descriptor.type_ref)
        if (exp_spec and actual_spec
                and not self.registry.is_dynamic(exp_spec)
                and not self.registry.is_dynamic(actual_spec)
                and not self.registry.is_assignable(actual_spec, exp_spec)):
            self.error(
                f"Argument '{name}' type mismatch: expected '{descriptor.type_ref.head}', "
                f"but got '{actual_spec.name}'.",
                node, code=SEM_TYPE_MISMATCH,
                hint=self.registry.get_diff_hint(actual_spec, exp_spec),
            )

    def _check_intent_context_static_call(self, node: ast.IbCall):
        """检查 intent_context.<method>() 是否在类级别调用（SEM_INTENT_STATIC_CALL）

        intent_context.push() / pop() / fork() / merge() / combine() / clear()
        在类对象上调用（而非实例）是无效的 no-op。正确用法是先通过
        get_current() 获取实例，再调用实例方法。
        """
        func = node.func
        if not isinstance(func, ast.IbAttribute):
            return
        if func.attr not in self._INTENT_CTX_INSTANCE_ONLY_METHODS:
            return
        # Check if the receiver is the class name "intent_context"
        if not isinstance(func.value, ast.IbName):
            return
        if func.value.id != "intent_context":
            return
        # Verify the symbol is a TYPE (class), not an instance variable
        sym = self.lookup_symbol("intent_context")
        if sym and sym.kind == SymbolKind.CLASS:
            self.warn(
                f"'{func.attr}()' called on 'intent_context' class has no effect. "
                f"Use 'intent_context ctx = intent_context.get_current()' first, "
                f"then call 'ctx.{func.attr}(...)' followed by 'intent_context.use(ctx)'.",
                node, code=SEM_INTENT_STATIC_CALL,
            )

    def _check_super_call_legality(self, node: ast.IbCall):
        """SEM_SUPER_OUTSIDE_METHOD: Check that super() is only called inside a class method.

        super() is only meaningful inside an instance method of a class.
        All user classes implicitly inherit from Object, so super() is always
        valid inside a class method.
        """
        func = node.func
        if not isinstance(func, ast.IbName):
            return
        if func.id != "super":
            return

        # super() must be inside a class method
        if not self.in_class_def or not self.current_class:
            self.error(
                "super() can only be used inside a class method.",
                node, code=SEM_SUPER_OUTSIDE_METHOD,
                hint="Move this call into a method of a class."
            )
            return

        if not self.in_function_def:
            self.error(
                "super() can only be used inside a class method.",
                node, code=SEM_SUPER_OUTSIDE_METHOD,
                hint="super() must be called within a method body (func), not at class level."
            )
            return

    # ========== 属性与下标访问 ==========

    def visit_IbAttribute(self, node: ast.IbAttribute) -> Optional[IbSpec]:
        """访问属性访问"""
        obj_type = self.visit(node.value)

        # 尝试解析成员类型
        if obj_type:
            member_spec = self.registry.resolve_member(obj_type, node.attr)
            if member_spec:
                # IbSpec with callable kind and non-void param info: use directly
                if (hasattr(member_spec, 'kind') and member_spec.kind
                        and member_spec.kind in (TypeKind.FUNCTION.value, TypeKind.CALLABLE_SIG.value, TypeKind.BOUND_METHOD.value)
                        and getattr(member_spec, 'param_types', None)):
                    self.bind_type(node, member_spec)
                    return member_spec
                # Non-callable member with meaningful kind: use directly
                if (hasattr(member_spec, 'kind') and member_spec.kind
                        and member_spec.kind not in (TypeKind.FUNCTION.value, TypeKind.CALLABLE_SIG.value, TypeKind.BOUND_METHOD.value)):
                    self.bind_type(node, member_spec)
                    return member_spec
                # Fallback: type_ref resolution
                if hasattr(member_spec, 'type_ref') and member_spec.type_ref:
                    type_ref = member_spec.type_ref
                    ref_name = type_ref.name if hasattr(type_ref, 'name') else (type_ref.head if hasattr(type_ref, 'head') else str(type_ref))
                    member_type = self.registry.resolve(ref_name)
                    if member_type:
                        self.bind_type(node, member_type)
                        return member_type

        # 默认返回 any
        self.bind_type(node, self._any_desc)
        return self._any_desc

    def visit_IbSubscript(self, node: ast.IbSubscript) -> Optional[IbSpec]:
        """访问下标访问 — tuple 位置类型 + list 元素类型推断"""
        value_type = self.visit(node.value)
        key_type = self.visit(node.slice)

        if not value_type:
            self.bind_type(node, self._any_desc)
            return self._any_desc

        # 切片操作返回同类型容器
        if isinstance(node.slice, ast.IbSlice):
            self.bind_type(node, value_type)
            return value_type

        # 元组位置元素类型精确推断
        if (value_type.kind == TypeKind.TUPLE.value
                and value_type.positional_element_types
                and isinstance(node.slice, ast.IbConstant)
                and isinstance(node.slice.value, int)
                and not isinstance(node.slice.value, bool)):
            idx = node.slice.value
            positional = value_type.positional_element_types
            if 0 <= idx < len(positional):
                pos_ref = positional[idx]
                resolved = self.registry.resolve(pos_ref.head, pos_ref.module)
                if resolved is not None:
                    self.bind_type(node, resolved)
                    return resolved

        # 使用 registry.resolve_subscript 推断下标结果类型
        res = None
        if hasattr(self.registry, 'resolve_subscript') and key_type:
            res = self.registry.resolve_subscript(value_type, key_type)
        if not res:
            # Fallback: 尝试从 iter_element 获取（list[int] → int）
            if hasattr(self.registry, 'resolve_iter_element'):
                iter_elem = self.registry.resolve_iter_element(value_type)
                if iter_elem:
                    res = iter_elem

        result = res or self._any_desc
        self.bind_type(node, result)
        return result

    # ========== 高阶与行为表达式 ==========

    def visit_IbLambdaExpr(self, node: ast.IbLambdaExpr) -> Optional[IbSpec]:
        """访问 lambda 表达式 — 返回类型检查与 CALLABLE_SIG 传播"""
        # 1. 确定返回类型标注
        returns_type: Optional[IbSpec] = (
            self._resolve_type(node.returns) if node.returns is not None else None
        )

        # 2. 创建 lambda 作用域并注册参数
        lambda_scope = SymbolTable(parent=self.current_scope, name="<lambda>")

        self.push_scope(lambda_scope)
        try:
            # 注册参数到 lambda 作用域（与 visit_IbFunctionDef 对齐）
            for arg_node in node.params:
                arg_type = self._any_desc
                # IbArg now has annotation field directly
                if arg_node.annotation:
                    arg_type = self._resolve_type(arg_node.annotation)

                arg_name = None
                if isinstance(arg_node, ast.IbArg):
                    arg_name = arg_node.arg

                if arg_name:
                    param_sym = VariableSymbol(
                        name=arg_name,
                        kind=SymbolKind.VARIABLE,
                        def_node=arg_node,
                        spec=arg_type,
                    )
                    lambda_scope.define(param_sym)

            body_type = self.visit(node.body) if node.body else self._void_desc
        finally:
            self.pop_scope()

        # 3. body 是 BehaviorExpr 时的特殊处理
        is_behavior_body = isinstance(node.body, ast.IbBehaviorExpr)
        has_concrete_returns = (
            returns_type is not None
            and not self.registry.is_dynamic(returns_type)
        )

        # 4. 非行为 body：检查 body 类型与 returns_type 的兼容性
        if (not is_behavior_body
                and has_concrete_returns
                and body_type is not None
                and body_type is not self._void_desc
                and not self.registry.is_assignable(body_type, returns_type)
                and not self.registry.is_dynamic(body_type)):
            self.error(
                f"Lambda body type '{body_type.name}' is not compatible with "
                f"declared return type '{returns_type.name}'.",
                node, code=SEM_TYPE_MISMATCH,
            )

        # 5. 返回带 return_type 的 Spec（使调用处 resolve_return 能推导出具体类型）
        if is_behavior_body:
            if has_concrete_returns:
                # 行为表达式 + 具体返回类型：bind body node 并返回带 value_type 的 spec
                self.bind_type(node.body, returns_type)
                result = self.registry.factory.create_behavior(
                    value_type_name=returns_type.name,
                    value_type_module=returns_type.module_path,
                )
                self.bind_type(node, result)
                return result
            self.bind_type(node, self._behavior_desc)
            return self._behavior_desc
        else:
            if has_concrete_returns:
                result = self.registry.factory.create_fn_callable(
                    value_type_name=returns_type.name,
                    value_type_module=returns_type.module_path,
                )
                self.bind_type(node, result)
                return result
            # 无标注时返回通用 fn_callable
            callable_type = self.registry.resolve("fn_callable")
            self.bind_type(node, callable_type)
            return callable_type

    def visit_IbBehaviorExpr(self, node: ast.IbBehaviorExpr) -> Optional[IbSpec]:
        """访问行为表达式"""
        for segment in node.segments:
            if isinstance(segment, ast.IbASTNode):
                self.visit(segment)
        # 返回 behavior 类型
        self.bind_type(node, self._behavior_desc)
        return self._behavior_desc

    def visit_IbBehaviorInstance(self, node: ast.IbBehaviorInstance) -> Optional[IbSpec]:
        """访问行为实例化表达式"""
        for segment in node.segments:
            if isinstance(segment, ast.IbASTNode):
                self.visit(segment)
        # 返回目标类型
        if node.target_type_name:
            target_type = self.registry.resolve(node.target_type_name)
            if target_type:
                self.bind_type(node, target_type)
                return target_type
        self.bind_type(node, self._any_desc)
        return self._any_desc

    def visit_IbTypeAnnotatedExpr(self, node: ast.IbTypeAnnotatedExpr) -> Optional[IbSpec]:
        """访问带类型标注的表达式"""
        # 返回标注的类型
        declared_type = self._resolve_type(node.annotation)
        self.bind_type(node, declared_type)
        return declared_type

    def visit_IbCastExpr(self, node: ast.IbCastExpr) -> Optional[IbSpec]:
        """访问类型转换表达式 (e.g., (int) expr)

        使用 can_convert_from 进行编译期 cast 校验。
        当目标类型的公理明确拒绝从源类型转换时，发出 SEM_CAST_NO_CONVERTER 错误。
        """
        source_type = self.visit(node.value)
        cast_type = self._resolve_type(node.type_annotation)

        # compile-time cast validation via can_convert_from
        if (source_type and cast_type
                and not self.registry.is_dynamic(source_type)
                and not self.registry.is_dynamic(cast_type)
                and source_type.name != cast_type.name):
            converter = self.registry.get_converter_cap(cast_type)
            if converter and not converter.can_convert_from(source_type.name):
                self.error(
                    f"Cast from '{source_type.name}' to '{cast_type.name}' "
                    f"is not supported by the type's conversion rules.",
                    node, code=SEM_CAST_NO_CONVERTER,
                )

        self.bind_type(node, cast_type)
        return cast_type

    def visit_IbSlice(self, node: ast.IbSlice) -> Optional[IbSpec]:
        """访问切片"""
        if node.lower:
            self.visit(node.lower)
        if node.upper:
            self.visit(node.upper)
        if node.step:
            self.visit(node.step)
        return None

    def visit_IbFilteredExpr(self, node: ast.IbFilteredExpr) -> Optional[IbSpec]:
        """访问带过滤条件的表达式"""
        expr_type = self.visit(node.expr)
        self.visit(node.filter)
        # filter 恒为布尔位置
        self._bind_condition_behavior_types(node.filter)
        self.bind_type(node, expr_type)
        return expr_type
