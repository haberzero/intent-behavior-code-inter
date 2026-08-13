"""
Statement Visitors Mixin for TypeCheckingVisitor.

Holds the visit methods for statement AST nodes:
assignment / type-inference helpers, control flow, and simple
statements. Split out from ``type_checking_pass.py`` as part of a
pure mechanical refactoring — no logic changes.
"""

from typing import Optional

from core.base.diagnostics.codes import SEM_TYPE_MISMATCH, SEM_UNRESOLVED_TYPE, ICE_TYPE_LEAK
from core.kernel import ast
from core.kernel.symbols import SymbolKind
from core.kernel.spec import IbSpec
from core.kernel.spec.base import TypeKind
from core.kernel.spec.type_ref import TypeRef


class StatementVisitorsMixin:
    """Statement visit methods (assignment, control flow, simple stmts)."""

    # ========== 模块和语句 ==========

    def visit_IbModule(self, node: ast.IbModule) -> Optional[IbSpec]:
        """访问模块节点"""
        for stmt in node.body:
            self.visit(stmt)
        return None

    def visit_IbAssign(self, node: ast.IbAssign) -> Optional[IbSpec]:
        """访问赋值节点"""
        # 先计算右侧表达式的类型
        val_type = self.visit(node.value)
        if not val_type:
            val_type = self._any_desc

        # 检查 void 赋值
        if val_type is self._void_desc and isinstance(node.value, ast.IbCall):
            self.error(
                "Cannot assign result of void function to a variable",
                node, code=SEM_TYPE_MISMATCH
            )
            val_type = self._any_desc

        # 处理每个赋值目标
        for target in node.targets:
            self._handle_assign_target(node, target, val_type)

        return self._void_desc

    def _handle_assign_target(self, node: ast.IbAssign, target: ast.IbASTNode, val_type: IbSpec):
        """处理单个赋值目标：auto 单次锁定 / any 永久动态"""
        # Store current node for use by _infer_fn_type
        self._current_node = node

        # Resolve TypeRef → IbSpec early to avoid downstream crashes
        if isinstance(val_type, TypeRef):
            resolved = self.registry.resolve_typeref(val_type)
            if not resolved:
                self.error(
                    f"Unresolved type '{val_type.head}' in assignment",
                    node, code=SEM_UNRESOLVED_TYPE,
                )
                resolved = self._any_desc
            val_type = resolved

        # 提取变量名和声明类型
        var_name, declared_type = self._resolve_target_name_and_type(target)

        if var_name:
            # 简单变量赋值
            sym = self.lookup_symbol(var_name)

            if declared_type:
                if isinstance(declared_type, TypeRef):
                    self.error(
                        f"Internal: unresolved TypeRef '{declared_type.head}' "
                        f"reached type checking (symbol spec leak)",
                        node, code=ICE_TYPE_LEAK,
                    )
                    declared_type = self.registry.resolve_typeref(declared_type) or self._any_desc
                # 类型推断策略
                target_type = self._infer_target_type_from_declared(declared_type, val_type)
            elif sym and sym.spec:
                # 已存在的符号：使用现有类型
                spec = sym.spec
                if isinstance(spec, TypeRef):
                    self.error(
                        f"Internal: unresolved TypeRef '{spec.head}' in symbol "
                        f"'{var_name}' reached type checking (symbol spec leak)",
                        node, code=ICE_TYPE_LEAK,
                    )
                    spec = self.registry.resolve_typeref(spec) or self._any_desc
                if getattr(spec, "name", None) == "auto":
                    # 裸赋值符号（auto 占位）：从首次赋值推断并锁定实际类型。
                    # 与 `auto x = expr` 语义一致——静态锁定，不再隐式退化为 any。
                    target_type = self._infer_target_type_from_declared(spec, val_type)
                else:
                    target_type = spec
            else:
                # 首次定义无类型标注：推断类型
                target_type = val_type

            # BehaviorExpr 特殊处理：行为表达式适配接收者类型
            # 这是 IBCI 核心语义 — @~...~ 的结果类型由左值决定
            # (支持 await <behavior> 的显式等待形式：解包 IbAwaitExpr 处理内层行为)
            rhs = node.value
            rhs_inner = rhs.value if isinstance(rhs, ast.IbAwaitExpr) else rhs
            if isinstance(rhs_inner, (ast.IbBehaviorExpr, ast.IbBehaviorInstance)):
                if target_type and not self.registry.is_dynamic(target_type):
                    # 行为表达式结果适配目标类型；具体目标类型必须可被 LLM 解析
                    self._check_behavior_output_parseable(target_type, node)
                    self.bind_type(rhs_inner, target_type)
                    if rhs is not rhs_inner:
                        self.bind_type(rhs, target_type)
                    val_type = target_type
                else:
                    # 动态类型或无类型：默认 str
                    val_type = self._str_desc

            # fn_callable 无返回标注时的 call-site 类型检查
            # fn f = lambda: EXPR; int r = f() → 如果 lambda 没有 -> TYPE 标注，
            # f() 返回 auto，不应静默赋给具体类型变量
            if (val_type and self.registry.is_dynamic(val_type)
                    and val_type.name == "auto"
                    and target_type and not self.registry.is_dynamic(target_type)
                    and isinstance(node.value, ast.IbCall)):
                # 检查被调用者是否为无标注 fn_callable
                call_node = node.value
                caller_type = self.type_bindings.get(call_node.func)
                if (caller_type and
                    caller_type.kind == TypeKind.CALLABLE_INSTANCE.value and
                    getattr(caller_type, 'value_type', None) and
                    getattr(caller_type.value_type, 'head', None) == "auto"):
                    self.error(
                        f"Cannot assign result of un-annotated callable to "
                        f"'{target_type.name}'. Add '-> {target_type.name}' to the lambda "
                        f"to declare its return type.",
                        node, code=SEM_TYPE_MISMATCH
                    )

            # 类型兼容性检查
            if not self.is_assignable(val_type, target_type):
                src_name = getattr(val_type, 'name', str(val_type))
                tgt_name = getattr(target_type, 'name', str(target_type))
                hint = self.registry.get_diff_hint(val_type, target_type)
                self.error(
                    f"Cannot assign '{src_name}' to '{tgt_name}'",
                    node, code=SEM_TYPE_MISMATCH, hint=hint
                )

            # 绑定类型
            self.bind_type(target, target_type)
            # 容器字面量 RHS 绑定目标特化类型（list[int] li = [1,2] → [1,2]
            # 节点的 node_to_type = list[int]），运行时值创建据此水化特化类
            # （缺陷二根治：内置泛型值层类型身份保真）。递归 helper 覆盖
            # 嵌套内层元素（list[list[int]] n = [[1],[2]] 的内层 [1]/[2]）。
            if target_type is not None and rhs_inner is not None and rhs is rhs_inner:
                self._bind_literal_with_type(rhs_inner, target_type)
            # 更新符号 spec：当 target_type 比已有 spec 更具体时更新
            if sym and target_type and target_type is not self._any_desc:
                existing = sym.spec
                if (not existing or
                    existing is self._any_desc or
                    self.registry.is_dynamic(existing) or
                    (declared_type and target_type.name != existing.name)):
                    sym.spec = target_type

        elif isinstance(target, (ast.IbAttribute, ast.IbSubscript)):
            # 属性或下标赋值
            target_type = self.visit(target)

            # Behavior 表达式特殊处理
            if isinstance(node.value, ast.IbBehaviorExpr):
                if target_type and not self.registry.is_dynamic(target_type):
                    self._check_behavior_output_parseable(target_type, node)
                    self.bind_type(node.value, target_type)
                return

            # 类型兼容性检查
            if target_type and not self.is_assignable(val_type, target_type):
                hint = self.registry.get_diff_hint(val_type, target_type)
                self.error(
                    f"Cannot assign '{getattr(val_type, 'name', str(val_type))}' to '{getattr(target_type, 'name', str(target_type))}'",
                    node, code=SEM_TYPE_MISMATCH, hint=hint
                )

            # 下标/属性赋值 RHS 容器字面量绑定目标特化类型（m[0] = [9] 且
            # m: list[list[int]] → [9] 节点 node_to_type = list[int]），值创建点
            # 据此水化特化类（缺陷二根治推广：下标赋值路径值层身份保真）。
            if target_type is not None and node.value is not None:
                self._bind_literal_with_type(node.value, target_type)

        elif isinstance(target, ast.IbTuple):
            # 元组解包：各元素接收 any（实际类型在运行时由 VM 赋值）。
            # RHS 是元组字面量时按位置绑定容器元素特化类型
            # （list[int] a, list[str] b = [1,2], ["x"] → [1,2] 绑 list[int]、
            # ["x"] 绑 list[str]），值创建点据此水化特化类（值层身份收敛）。
            rhs_tuple = node.value if isinstance(node.value, ast.IbTuple) else None
            for idx, elt in enumerate(target.elts):
                if rhs_tuple is not None and idx < len(rhs_tuple.elts):
                    rhs_elt = rhs_tuple.elts[idx]
                    elt_type = self.visit(elt)
                    if elt_type is not None:
                        self._bind_literal_with_type(rhs_elt, elt_type)
                self._handle_assign_target(node, elt, self._any_desc)

    def _resolve_target_name_and_type(self, target: ast.IbASTNode):
        """从赋值目标提取变量名和声明类型"""
        var_name = None
        declared_type = None

        if isinstance(target, ast.IbTypeAnnotatedExpr):
            declared_type = self._resolve_type(target.annotation)
            if isinstance(target.target, ast.IbName):
                var_name = target.target.id
        elif isinstance(target, ast.IbName):
            var_name = target.id

        return var_name, declared_type

    def _infer_target_type_from_declared(self, declared_type: IbSpec, val_type: IbSpec) -> IbSpec:
        """根据声明类型推导目标类型（auto 锁定 / any 永久 / fn 推断）。

        - `any`：变量 spec 永久保持为 any，不因首次赋值类型窄化。
        - `auto`：从首次赋值的实际类型推断并锁定。行为表达式的 LLM 输出天然是字符串。
        - `fn`：可调用类型推导。
        - `fn[(...)→(...)]`（CALLABLE_SIG）：结构签名匹配。
        - 其他：使用显式声明类型。
        """
        if declared_type.name == "fn" and declared_type.kind != TypeKind.CALLABLE_SIG.value:
            # fn 声明（无签名约束）：要求 RHS 必须是可调用的
            return self._infer_fn_type(declared_type, val_type)

        if declared_type.kind == TypeKind.CALLABLE_SIG.value:
            # fn[(...)→(...)] 签名标注 — 检查结构签名匹配
            return self._infer_fn_type_with_sig(declared_type, val_type)

        if self.registry.is_dynamic(declared_type):
            if declared_type.name == "any":
                # `any`：变量 spec 永久保持为 any，不因首次赋值类型窄化。
                return self._any_desc
            # `auto`：从首次赋值的实际类型推断并锁定。
            # 即时行为表达式的 LLM 输出天然是字符串，不应推断为 behavior spec。
            if self.registry.is_behavior(val_type):
                return self._str_desc
            return val_type

        return declared_type

    def _infer_fn_type(self, declared_type: IbSpec, val_type: IbSpec) -> IbSpec:
        """fn 声明（无签名约束）：要求 RHS 必须是可调用的。

        fn f = myFunc  → f 持有 myFunc 的具体 callable spec
        fn f = 42      → SEM_TYPE_MISMATCH（42 不可调用）
        """
        if val_type.kind == TypeKind.CLASS.value:
            # 区分类名引用（构造器）与类实例
            # (a) 类名引用（fn f = Dog）：始终允许
            node = self._current_node
            is_constructor_ref = False
            if isinstance(node, ast.IbAssign) and isinstance(node.value, ast.IbName):
                sym = self.lookup_symbol(node.value.id)
                if sym and sym.kind == SymbolKind.CLASS:
                    is_constructor_ref = True
            if is_constructor_ref:
                return val_type
            # (b) 类实例引用，且类定义了 __call__
            members = val_type.members
            if '__call__' in members:
                return val_type
            else:
                self.error(
                    f"'fn' requires a callable on the right-hand side. "
                    f"Type '{val_type.name}' does not define a '__call__' method. "
                    f"Add 'func __call__(self, ...)' to '{val_type.name}' "
                    f"to make its instances callable via 'fn'.",
                    self._current_node, code=SEM_TYPE_MISMATCH
                )
                return self.registry.resolve("callable") or self._any_desc
        elif self.registry.is_callable(val_type):
            return val_type
        elif self.registry.is_dynamic(val_type):
            return self.registry.resolve("callable") or self._any_desc
        else:
            self.error(
                f"'fn' requires a callable on the right-hand side, "
                f"but got '{val_type.name}'. "
                f"Use 'fn f = myFunction' or 'fn f = myLambda'.",
                self._current_node, code=SEM_TYPE_MISMATCH
            )
            return self.registry.resolve("callable") or self._any_desc

    def _infer_fn_type_with_sig(self, declared_type: IbSpec, val_type: IbSpec) -> IbSpec:
        """fn[(...)→(...)] 签名标注时，检查结构签名匹配。"""
        # If RHS isn't callable at all, error
        if not self.registry.is_callable(val_type) and not self.registry.is_dynamic(val_type):
            if val_type.kind != TypeKind.CLASS.value:
                self.error(
                    f"'fn' requires a callable on the right-hand side, "
                    f"but got '{val_type.name}'.",
                    self._current_node, code=SEM_TYPE_MISMATCH
                )
                return declared_type

        # Structural sig matching when RHS carries concrete signature.
        # CALLABLE_INSTANCE（behavior/fn lambda）按 value_type 校验返回类型：
        # lambda 的 CALLABLE_INSTANCE spec 不
        # 携带 param_types，参数约束由调用处实参解析覆盖，此处只校验返回）。
        if val_type.kind in (
            TypeKind.FUNCTION.value,
            TypeKind.CALLABLE_SIG.value,
            TypeKind.CALLABLE_INSTANCE.value,
        ):
            self._check_callable_sig_match(declared_type, val_type, self._current_node)

        return declared_type

    def _check_callable_sig_match(self, sig: IbSpec, actual: IbSpec, node: ast.IbASTNode):
        """Best-effort structural compatibility check between a CALLABLE_SIG constraint and a concrete callable."""
        expected_params = [t.head for t in sig.param_types]

        # CALLABLE_INSTANCE（behavior/fn lambda）：spec 不携带 param_types，只按
        # value_type 校验返回类型；参数约束由调用处实参解析覆盖。
        is_callable_instance = actual.kind == TypeKind.CALLABLE_INSTANCE.value
        actual_params = [] if is_callable_instance else [t.head for t in actual.param_types]

        # Param count check
        if not is_callable_instance and len(actual_params) != len(expected_params):
            self.error(
                f"Callable signature mismatch: expected {len(expected_params)} "
                f"parameter(s), but the callable has {len(actual_params)} parameter(s).",
                node, code=SEM_TYPE_MISMATCH,
            )
            return

        # Per-parameter type compatibility
        for i, (exp_name, act_name) in enumerate(zip(expected_params, actual_params)):
            exp_spec = self.registry.resolve(exp_name)
            act_spec = self.registry.resolve(act_name)
            if (exp_spec and act_spec
                    and not self.registry.is_dynamic(exp_spec)
                    and not self.registry.is_dynamic(act_spec)
                    and not self.registry.is_assignable(act_spec, exp_spec)):
                self.error(
                    f"Callable signature mismatch: parameter {i + 1} expects "
                    f"'{exp_name}', but the callable declares '{act_name}'.",
                    node, code=SEM_TYPE_MISMATCH,
                )

        # Return type compatibility
        sig_ret = sig.return_type
        actual_ret = actual.value_type if is_callable_instance else actual.return_type
        if sig_ret and actual_ret:
            exp_ret = self.registry.resolve_typeref(sig_ret)
            act_ret = self.registry.resolve_typeref(actual_ret)
            if (exp_ret and act_ret
                    and not self.registry.is_dynamic(exp_ret)
                    and not self.registry.is_dynamic(act_ret)
                    and not self.registry.is_assignable(act_ret, exp_ret)):
                self.error(
                    f"Callable signature mismatch: expected return type '{sig_ret.head}', "
                    f"but the callable returns '{actual_ret.head}'.",
                    node, code=SEM_TYPE_MISMATCH,
                )

    # ========== 控制流 ==========

    def visit_IbIf(self, node: ast.IbIf) -> Optional[IbSpec]:
        """访问 if 语句"""
        self.visit(node.test)
        # 布尔上下文中的行为表达式定型为 bool（含复合布尔表达式的递归传播）
        self._bind_condition_behavior_types(node.test)
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)
        return None

    def visit_IbWhile(self, node: ast.IbWhile) -> Optional[IbSpec]:
        """访问 while 语句"""
        self.visit(node.test)
        # 布尔上下文中的行为表达式定型为 bool（含复合布尔表达式的递归传播）
        self._bind_condition_behavior_types(node.test)
        for stmt in node.body:
            self.visit(stmt)
        return None

    def visit_IbFor(self, node: ast.IbFor) -> Optional[IbSpec]:
        """访问 for 语句"""
        if node.iter:
            # for...if 过滤语法：先访问实际迭代对象，再访问循环变量，最后访问过滤条件
            if isinstance(node.iter, ast.IbFilteredExpr):
                self.visit(node.iter.expr)
                # 条件驱动 for（target 为空）：迭代表达式是条件（布尔位置）
                if node.target is None:
                    self._bind_condition_behavior_types(node.iter.expr)
            else:
                self.visit(node.iter)
                # 条件驱动 for（target 为空）：迭代表达式是条件（布尔位置）
                if node.target is None:
                    self._bind_condition_behavior_types(node.iter)
        if node.target:
            target_type = self.visit(node.target)
            # for list[int] row in [[1],[2]]：迭代源字面量绑"元素类型容器"——
            # row 类型 list[int] → 迭代源 [[1],[2]] 绑 list[list[int]]（值创建点
            # 据此水化，迭代元素保真）。仅当 target 有具体类型（非动态）时。
            if target_type and node.iter is not None and not self.registry.is_dynamic(target_type):
                if isinstance(node.iter, ast.IbFilteredExpr):
                    iter_literal = node.iter.expr
                else:
                    iter_literal = node.iter
                # 迭代源容器类型 = list[T]（T = 循环变量完整 spec，结构化构造——
                # 嵌套 target_type 不扁平化）。经 resolve_typeref 懒构建特化 spec。
                from core.kernel.spec.type_ref import TypeRef
                elem_ref = TypeRef.from_spec(target_type)
                src_spec = self.registry.resolve_typeref(TypeRef.generic("list", elem_ref))
                if src_spec is not None:
                    self._bind_literal_with_type(iter_literal, src_spec)
        # 访问 for...if 的过滤条件（此时循环变量已注册）；filter 恒为布尔位置
        if node.iter and isinstance(node.iter, ast.IbFilteredExpr):
            self.visit(node.iter.filter)
            self._bind_condition_behavior_types(node.iter.filter)
        for stmt in node.body:
            self.visit(stmt)
        return None

    def visit_IbReturn(self, node: ast.IbReturn) -> Optional[IbSpec]:
        """访问 return 语句"""
        if node.value:
            # 禁止 `return @~...~`：行为表达式（@~）的输出类型与提示词约束
            # 由左值类型驱动，return 处没有左值——直接书写无法确定 LLM 输出
            # 的解析目标，运行时将按字符串 box（-> int 等具体类型失效，静默
            # 类型错流入）。用户应先赋值给有类型的局部变量，再 return 该变量。
            # （v1 曾实现此拦截，v2 语义重构时未随迁——此处补全设计意图。）
            rhs = node.value
            rhs_inner = rhs.value if isinstance(rhs, ast.IbAwaitExpr) else rhs
            if isinstance(rhs_inner, (ast.IbBehaviorExpr, ast.IbBehaviorInstance)):
                self.error(
                    "Cannot use a behavior expression directly in a return statement. "
                    "Assign it to a typed local variable first, then return that variable.",
                    node, code=SEM_TYPE_MISMATCH,
                )
                return self._void_desc
            ret_type = self.visit(node.value)
            # 返回容器字面量绑定函数返回特化类型（func f() -> list[int]:
            # return [1,2] → [1,2] 节点 node_to_type = list[int]），值创建点
            # 据此水化特化类（缺陷二根治推广：函数返回路径值层身份保真）。
            func_returns = getattr(self, "func_return_types", None) or []
            if func_returns and func_returns[-1] is not None:
                self._bind_literal_with_type(rhs_inner, func_returns[-1])
            # 如果在 auto 返回类型函数中，累积返回类型
            if self.auto_return_types is not None:
                self.auto_return_types.append(ret_type)
            return ret_type
        return self._void_desc

    def visit_IbTry(self, node: ast.IbTry) -> Optional[IbSpec]:
        """访问 try 语句"""
        for stmt in node.body:
            self.visit(stmt)
        for handler in node.handlers:
            self.visit(handler)
        for stmt in node.orelse:
            self.visit(stmt)
        for stmt in node.finalbody:
            self.visit(stmt)
        return None

    def visit_IbExceptHandler(self, node: ast.IbExceptHandler) -> Optional[IbSpec]:
        """访问异常处理器"""
        if node.type:
            self.visit(node.type)
        for stmt in node.body:
            self.visit(stmt)
        return None

    def visit_IbSwitch(self, node: ast.IbSwitch) -> Optional[IbSpec]:
        """访问 switch 语句"""
        self.visit(node.test)
        for case in node.cases:
            self.visit(case)
        return None

    def visit_IbCase(self, node: ast.IbCase) -> Optional[IbSpec]:
        """访问 switch case"""
        if node.pattern:
            self.visit(node.pattern)
        for stmt in node.body:
            self.visit(stmt)
        return None

    # ========== 简单语句 ==========

    def visit_IbExprStmt(self, node: ast.IbExprStmt) -> Optional[IbSpec]:
        """访问表达式语句"""
        return self.visit(node.value)

    def visit_IbAugAssign(self, node: ast.IbAugAssign) -> Optional[IbSpec]:
        """访问增量赋值 (e.g., x += 1)

        复合赋值 ``x <op>= y`` 语义上等价于 ``x = x <op> y``。
        公理只识别二元形式（``+``、``-`` 等），因此剥离尾部 ``=`` 后再检查--
        与运行时 VM handler (``assignment.py`` ``op_symbol.rstrip("=")``) 保持一致。
        """
        target_type = self.visit(node.target)
        val_type = self.visit(node.value)

        bin_op = node.op[:-1] if node.op.endswith("=") else node.op

        if target_type:
            result_type = self.registry.resolve_op(target_type, bin_op, val_type)
            if not result_type:
                self.error(
                    f"Augmented assignment operator '{node.op}' not supported for type '{target_type.name}'",
                    node, code=SEM_TYPE_MISMATCH
                )
            # 复合赋值 RHS 容器字面量绑定目标特化类型（list[int] a += [2] → [2]
            # 节点 node_to_type = list[int]），值创建点据此水化特化类（缺陷二
            # 根治推广：复合赋值路径值层身份保真）。
            self._bind_literal_with_type(node.value, target_type)
        return None

    def visit_IbImport(self, node: ast.IbImport) -> Optional[IbSpec]:
        """访问 import 语句"""
        return None

    def visit_IbImportFrom(self, node: ast.IbImportFrom) -> Optional[IbSpec]:
        """访问 from ... import 语句"""
        return None

    def visit_IbIntentStackOperation(self, node: ast.IbIntentStackOperation) -> Optional[IbSpec]:
        """访问意图栈操作 (@+ / @-)"""
        return None

    def visit_IbRaise(self, node: ast.IbRaise) -> Optional[IbSpec]:
        """访问 raise 语句"""
        if node.exc:
            self.visit(node.exc)
        return None

    def visit_IbRetry(self, node: ast.IbRetry) -> Optional[IbSpec]:
        """访问 retry 语句"""
        if node.hint:
            self.visit(node.hint)
        return None

    def visit_IbGlobalStmt(self, node: ast.IbGlobalStmt) -> Optional[IbSpec]:
        """访问 global 语句"""
        return None

    def visit_IbLLMExceptionalStmt(self, node: ast.IbLLMExceptionalStmt) -> Optional[IbSpec]:
        """访问 llmexcept 语句"""
        if node.target:
            self.visit(node.target)
        for stmt in node.body:
            self.visit(stmt)
        return None

    def visit_IbPass(self, node: ast.IbPass) -> Optional[IbSpec]:
        """访问 pass 语句"""
        return None

    def visit_IbBreak(self, node: ast.IbBreak) -> Optional[IbSpec]:
        """访问 break 语句"""
        return None

    def visit_IbContinue(self, node: ast.IbContinue) -> Optional[IbSpec]:
        """访问 continue 语句"""
        return None
