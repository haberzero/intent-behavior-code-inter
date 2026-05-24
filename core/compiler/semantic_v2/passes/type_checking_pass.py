"""
Pass 3: Type Checking Pass

职责：类型检查和推断（简化的一次性推断，适配静态类型系统）
输入：Context with resolved symbols
输出：Context with type_bindings
"""

from dataclasses import replace
from typing import Optional, List, Dict, Any

from core.kernel import ast
from core.kernel.symbols import Symbol, SymbolTable, SymbolKind, VariableSymbol
from core.kernel.spec import IbSpec
from core.kernel.spec.base import TypeKind
from core.kernel.spec.type_ref import TypeRef

from ..result import PassResult, Diagnostic, DiagnosticLevel
from ..context import SemanticContext
from .base_pass import BasePass


class TypeCheckingPass(BasePass):
    """类型检查 Pass（Pass 3）

    简化的类型检查和推断：
    - 一次性推断（不需要约束求解）
    - auto 变量类型推断
    - -> auto 函数返回类型推断
    - 类型兼容性检查 (SEM_003)
    """

    def __init__(self):
        super().__init__("TypeCheckingPass")

    def run(self, context: SemanticContext) -> PassResult:
        """运行类型检查 Pass"""
        visitor = TypeCheckingVisitor(context)
        visitor.visit(context.ast)

        # 更新 metadata 中的类型绑定（node object → IbSpec）
        new_metadata = context.metadata
        for node, type_spec in visitor.type_bindings.items():
            new_metadata.bind_type(node, type_spec)

        # TypeEnvironment is updated through visitor operations
        # No need to explicitly update it here

        new_context = replace(context, metadata=new_metadata)

        return PassResult.ok(new_context, diagnostics=visitor.diagnostics)


class TypeCheckingVisitor:
    """类型检查访问者"""

    def __init__(self, context: SemanticContext):
        self.context = context
        self.symbol_table = context.symbol_table.current
        self.registry = context.registry
        self.diagnostics: List[Diagnostic] = []

        # 类型绑定：node object -> IbSpec（使用对象身份作为键）
        self.type_bindings: Dict[Any, IbSpec] = {}

        # 作用域栈（用于处理嵌套作用域）
        self.scope_stack: List[SymbolTable] = [self.symbol_table]

        # auto 返回类型累积（用于 -> auto 函数）
        self.auto_return_types: Optional[List[IbSpec]] = None

        # 状态标志
        self.in_function_def = False
        self.in_class_def = False
        self.current_class: Optional[IbSpec] = None

        # 常用类型描述符
        self._any_desc = self.registry.resolve("any")
        self._void_desc = self.registry.resolve("void")
        self._behavior_desc = self.registry.resolve("behavior")
        self._int_desc = self.registry.resolve("int")
        self._float_desc = self.registry.resolve("float")
        self._str_desc = self.registry.resolve("str")
        self._bool_desc = self.registry.resolve("bool")
        self._none_desc = self.registry.resolve("None")

    @property
    def current_scope(self) -> SymbolTable:
        """当前作用域"""
        return self.scope_stack[-1]

    def push_scope(self, scope: SymbolTable):
        """进入新作用域"""
        self.scope_stack.append(scope)

    def pop_scope(self):
        """退出作用域"""
        if len(self.scope_stack) > 1:
            self.scope_stack.pop()

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
        """检查源类型是否可以赋给目标类型（对齐 v1：dynamic 类型跳过检查）"""
        if not source or not target:
            return True
        # Guard: resolve TypeRef to actual IbSpec if needed
        if isinstance(source, TypeRef):
            source = self.registry.resolve(source.head) or self._any_desc
        if isinstance(target, TypeRef):
            target = self.registry.resolve(target.head) or self._any_desc
        # 与 v1 对齐：当源或目标为 dynamic（any/auto）时，跳过兼容性检查
        if self.registry.is_dynamic(source) or self.registry.is_dynamic(target):
            return True
        return self.registry.is_assignable(source, target)

    def _resolve_type(self, annotation: ast.IbASTNode) -> Optional[IbSpec]:
        """解析类型标注"""
        if annotation is None:
            return self._any_desc
        if isinstance(annotation, ast.IbName):
            return self.registry.resolve(annotation.id) or self._any_desc
        elif isinstance(annotation, ast.IbSubscript):
            # 泛型类型：list[int], dict[str, int] 等
            if isinstance(annotation.value, ast.IbName):
                return self.registry.resolve(annotation.value.id) or self._any_desc
            return self._any_desc
        else:
            # 其他类型标注
            return self._any_desc

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
                node, code="SEM_003"
            )
            val_type = self._any_desc

        # 处理每个赋值目标
        for target in node.targets:
            self._handle_assign_target(node, target, val_type)

        return self._void_desc

    def _handle_assign_target(self, node: ast.IbAssign, target: ast.IbASTNode, val_type: IbSpec):
        """处理单个赋值目标 — P1-B: auto 单次锁定 / any 永久动态"""

        # Resolve TypeRef → IbSpec early to avoid downstream crashes
        if isinstance(val_type, TypeRef):
            val_type = self.registry.resolve(val_type.head) or self._any_desc

        # 提取变量名和声明类型
        var_name, declared_type = self._resolve_target_name_and_type(target)

        if var_name:
            # 简单变量赋值
            sym = self.lookup_symbol(var_name)

            if declared_type:
                # Resolve declared_type if it's a TypeRef
                if isinstance(declared_type, TypeRef):
                    declared_type = self.registry.resolve(declared_type.head) or self._any_desc
                # P1-B: 类型推断策略
                target_type = self._infer_target_type_from_declared(declared_type, val_type)
            elif sym and sym.spec:
                # 已存在的符号：使用现有类型
                spec = sym.spec
                if isinstance(spec, TypeRef):
                    spec = self.registry.resolve(spec.head) or self._any_desc
                target_type = spec
            else:
                # 首次定义无类型标注：推断类型
                target_type = val_type

            # BehaviorExpr 特殊处理：行为表达式适配接收者类型
            # 这是 IBCI 核心语义 — @~...~ 的结果类型由左值决定
            if isinstance(node.value, (ast.IbBehaviorExpr, ast.IbBehaviorInstance)):
                if target_type and not self.registry.is_dynamic(target_type):
                    # 行为表达式结果适配目标类型
                    self.bind_type(node.value, target_type)
                    val_type = target_type
                else:
                    # 动态类型或无类型：默认 str
                    val_type = self._str_desc

            # 类型兼容性检查
            if not self.is_assignable(val_type, target_type):
                src_name = getattr(val_type, 'name', str(val_type))
                tgt_name = getattr(target_type, 'name', str(target_type))
                hint = self.registry.get_diff_hint(val_type, target_type) if hasattr(self.registry, 'get_diff_hint') else None
                self.error(
                    f"Cannot assign '{src_name}' to '{tgt_name}'",
                    node, code="SEM_003", hint=hint
                )

            # 绑定类型
            self.bind_type(target, target_type)

        elif isinstance(target, (ast.IbAttribute, ast.IbSubscript)):
            # 属性或下标赋值
            target_type = self.visit(target)

            # Behavior 表达式特殊处理
            if isinstance(node.value, ast.IbBehaviorExpr):
                if target_type and not self.registry.is_dynamic(target_type):
                    self.bind_type(node.value, target_type)
                return

            # 类型兼容性检查
            if target_type and not self.is_assignable(val_type, target_type):
                hint = self.registry.get_diff_hint(val_type, target_type) if hasattr(self.registry, 'get_diff_hint') else None
                self.error(
                    f"Cannot assign '{getattr(val_type, 'name', str(val_type))}' to '{getattr(target_type, 'name', str(target_type))}'",
                    node, code="SEM_003", hint=hint
                )

        elif isinstance(target, ast.IbTuple):
            # 元组解包
            for elt in target.elts:
                self._handle_assign_target(node, elt, val_type)

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
        """P1-B: 根据声明类型推导目标类型（auto 锁定 / any 永久 / fn 推断）。

        - `any`：变量 spec 永久保持为 any，不因首次赋值类型窄化。
        - `auto`：从首次赋值的实际类型推断并锁定。行为表达式的 LLM 输出天然是字符串。
        - `fn`：可调用类型推导。
        - 其他：使用显式声明类型。
        """
        if declared_type.name == "fn":
            # fn 声明：fn 是动态可调用类型，接受任何可调用值（v1 permissive semantics）
            return val_type

        if hasattr(self.registry, 'is_dynamic') and self.registry.is_dynamic(declared_type):
            if declared_type.name == "any":
                # `any`：变量 spec 永久保持为 any，不因首次赋值类型窄化。
                return self._any_desc
            # `auto`：从首次赋值的实际类型推断并锁定。
            # 即时行为表达式的 LLM 输出天然是字符串，不应推断为 behavior spec。
            if hasattr(self.registry, 'is_behavior') and self.registry.is_behavior(val_type):
                return self._str_desc
            return val_type

        return declared_type

    def visit_IbIf(self, node: ast.IbIf) -> Optional[IbSpec]:
        """访问 if 语句"""
        self.visit(node.test)
        # if @~...~: 中的行为表达式应被解析为 bool 类型
        if isinstance(node.test, ast.IbBehaviorExpr):
            self.bind_type(node.test, self.registry.resolve("bool"))
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)
        return None

    def visit_IbWhile(self, node: ast.IbWhile) -> Optional[IbSpec]:
        """访问 while 语句"""
        self.visit(node.test)
        # while @~...~: 中的行为表达式应被解析为 bool 类型
        if isinstance(node.test, ast.IbBehaviorExpr):
            self.bind_type(node.test, self.registry.resolve("bool"))
        for stmt in node.body:
            self.visit(stmt)
        return None

    def visit_IbFor(self, node: ast.IbFor) -> Optional[IbSpec]:
        """访问 for 语句"""
        if node.iter:
            self.visit(node.iter)
            # 条件驱动循环中的行为表达式应被解析为 bool 类型
            # (v1 parity: semantic_analyzer.py:1273-1274)
            if isinstance(node.iter, ast.IbBehaviorExpr):
                self.bind_type(node.iter, self.registry.resolve("bool"))
        if node.target:
            self.visit(node.target)
        for stmt in node.body:
            self.visit(stmt)
        return None

    def visit_IbReturn(self, node: ast.IbReturn) -> Optional[IbSpec]:
        """访问 return 语句"""
        if node.value:
            ret_type = self.visit(node.value)
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
        """访问函数定义 — 对齐 v1：解析参数类型标注，回填 spec，参数以正确类型注册"""
        # 查找函数符号
        sym = self.lookup_symbol(node.name)

        # 解析参数类型标注（与 v1 visit_IbFunctionDef 对齐）
        param_types = []
        for arg_node in node.args:
            if isinstance(arg_node, ast.IbTypeAnnotatedExpr) and arg_node.annotation:
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

        # 回填函数 spec（与 v1 对齐：用 factory.create_func 重建 TypeDef 携带签名）
        if sym and sym.spec and self.registry:
            param_type_names = [(p.name if p else "any") for p in param_types]
            ret_type_name = ret_type.name if ret_type else "void"
            updated_spec = self.registry.factory.create_func(
                name=node.name,
                param_type_names=param_type_names,
                return_type_name=ret_type_name
            )
            updated_spec.is_user_defined = True
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

            # P1-B: -> auto 函数返回类型统一
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
                    from core.kernel.spec.type_ref import TypeRef as TR
                    sym.spec.return_type = TR.of(inferred_return.name, getattr(inferred_return, "module_path", None))

        finally:
            self.pop_scope()
            self.in_function_def = old_in_function
            self.auto_return_types = old_auto_returns

        return None

    @staticmethod
    def _extract_arg_name(arg_node) -> Optional[str]:
        """从参数节点提取参数名。"""
        if isinstance(arg_node, ast.IbArg):
            return arg_node.arg
        elif isinstance(arg_node, ast.IbTypeAnnotatedExpr):
            if isinstance(arg_node.target, ast.IbArg):
                return arg_node.target.arg
            elif isinstance(arg_node.target, ast.IbName):
                return arg_node.target.id
        return None

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

    # ========== 表达式 ==========

    def visit_IbName(self, node: ast.IbName) -> Optional[IbSpec]:
        """访问名称引用"""
        sym = self.lookup_symbol(node.id)
        if sym and sym.spec:
            spec = sym.spec
            # Resolve TypeRef → IbSpec
            if isinstance(spec, TypeRef):
                spec = self.registry.resolve(spec.head) or self._any_desc
            self.bind_type(node, spec)
            return spec
        # 未定义符号在 Pass 2 已报错，这里返回 any
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

    def visit_IbBinOp(self, node: ast.IbBinOp) -> Optional[IbSpec]:
        """访问二元运算 — P1-B: 接通 registry.resolve_op"""
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)

        # any 类型与任何操作兼容（v1 permissive semantics）
        if left_type == self._any_desc or right_type == self._any_desc:
            self.bind_type(node, self._any_desc)
            return self._any_desc

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
                    node, code="SEM_003"
                )
                result_type = self._any_desc

        self.bind_type(node, result_type)
        return result_type

    def visit_IbUnaryOp(self, node: ast.IbUnaryOp) -> Optional[IbSpec]:
        """访问一元运算 — P1-B: 接通 registry.resolve_op"""
        operand_type = self.visit(node.operand)

        # 贯彻"一切皆对象"：调用操作数的自决议方法 (other=None 表示一元运算)
        result_type = self.registry.resolve_op(operand_type, node.op, None) if operand_type else None
        if not result_type:
            # Fallback: 保持操作数类型
            result_type = operand_type or self._any_desc

        self.bind_type(node, result_type)
        return result_type

    def visit_IbCompare(self, node: ast.IbCompare) -> Optional[IbSpec]:
        """访问比较运算 — P1-B: 接通 registry.resolve_op"""
        left_type = self.visit(node.left)
        for comparator in node.comparators:
            self.visit(comparator)

        # 比较运算通过 resolve_op 确认合法性（大部分返回 bool）
        if left_type and node.ops:
            result_type = self.registry.resolve_op(left_type, node.ops[0], None)
            if result_type:
                self.bind_type(node, result_type)
                return result_type

        # 默认比较返回 bool
        self.bind_type(node, self._bool_desc)
        return self._bool_desc

    def visit_IbCall(self, node: ast.IbCall) -> Optional[IbSpec]:
        """访问函数调用 — 对齐 v1 逻辑：使用 registry.resolve_return() 推断返回类型"""
        # 处理被调用对象
        func_type = self.visit(node.func)

        # 处理参数并收集类型
        arg_types = [self.visit(arg) for arg in node.args]

        if not func_type:
            self.bind_type(node, self._any_desc)
            return self._any_desc

        # 0. 内置类型构造函数特殊处理（与 v1 对齐）
        if not self.registry.get_call_cap(func_type):
            type_name = func_type.name
            if type_name in ('str', 'int', 'float', 'bool', 'list', 'dict', 'Exception'):
                self.bind_type(node, func_type)
                return func_type

        # 0b. 可调用类实例：变量持有带 __call__ 的类实例（与 v1 对齐）
        if func_type.kind == TypeKind.CLASS.value and isinstance(node.func, ast.IbName):
            sym = self.lookup_symbol(node.func.id)
            if sym and not getattr(sym, 'is_type', True) and '__call__' in (func_type.members or {}):
                call_spec = self.registry.resolve_member(func_type, '__call__')
                if call_spec and call_spec.kind in (TypeKind.FUNCTION.value, TypeKind.CALLABLE_SIG.value):
                    ret = self.registry.resolve(call_spec.return_type.head) if hasattr(call_spec, 'return_type') and call_spec.return_type else self._any_desc
                    self.bind_type(node, ret)
                    return ret

        # 1. 检查是否可调用
        call_trait = self.registry.get_call_cap(func_type)
        if not call_trait:
            self.error(f"Type '{func_type.name}' is not callable", node, code="SEM_003")
            self.bind_type(node, self._any_desc)
            return self._any_desc

        # 2. 使用 registry.resolve_return() 推断返回类型（一切皆对象）
        res = self.registry.resolve_return(func_type, arg_types or [])

        if not res:
            # Fallback：尝试从 spec 上的 return_type 属性直接读取
            ret_ref = getattr(func_type, 'return_type', None)
            if ret_ref is not None:
                if isinstance(ret_ref, TypeRef):
                    res = self.registry.resolve(ret_ref.head) or self._any_desc
                elif hasattr(ret_ref, 'head') and ret_ref.head:
                    res = self.registry.resolve(ret_ref.head) or self._any_desc
                else:
                    res = self._any_desc
            else:
                res = self._any_desc

        self.bind_type(node, res)
        return res

    def visit_IbAttribute(self, node: ast.IbAttribute) -> Optional[IbSpec]:
        """访问属性访问"""
        obj_type = self.visit(node.value)

        # 尝试解析成员类型
        if obj_type:
            member_spec = self.registry.resolve_member(obj_type, node.attr)
            if member_spec and hasattr(member_spec, 'type_ref'):
                # 解析 type_ref
                member_type = self.registry.resolve(member_spec.type_ref.name if hasattr(member_spec.type_ref, 'name') else str(member_spec.type_ref))
                self.bind_type(node, member_type)
                return member_type

        # 默认返回 any
        self.bind_type(node, self._any_desc)
        return self._any_desc

    def visit_IbSubscript(self, node: ast.IbSubscript) -> Optional[IbSpec]:
        """访问下标访问"""
        self.visit(node.value)
        self.visit(node.slice)
        # 简化处理：返回 any
        self.bind_type(node, self._any_desc)
        return self._any_desc

    def visit_IbLambdaExpr(self, node: ast.IbLambdaExpr) -> Optional[IbSpec]:
        """访问 lambda 表达式"""
        # 创建 lambda 作用域
        lambda_scope = SymbolTable(parent=self.current_scope, name="<lambda>")

        self.push_scope(lambda_scope)
        try:
            for arg in node.params:
                self.visit(arg)
            if node.body:
                self.visit(node.body)
        finally:
            self.pop_scope()

        # 返回 callable 类型
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

    def visit_IbTypeAnnotatedExpr(self, node: ast.IbTypeAnnotatedExpr) -> Optional[IbSpec]:
        """访问带类型标注的表达式"""
        # 返回标注的类型
        declared_type = self._resolve_type(node.annotation)
        self.bind_type(node, declared_type)
        return declared_type

    # ========== P1-C: 补齐的 AST 节点 visitor ==========

    def visit_IbExprStmt(self, node: ast.IbExprStmt) -> Optional[IbSpec]:
        """访问表达式语句"""
        return self.visit(node.value)

    def visit_IbAugAssign(self, node: ast.IbAugAssign) -> Optional[IbSpec]:
        """访问增量赋值 (e.g., x += 1)"""
        target_type = self.visit(node.target)
        val_type = self.visit(node.value)

        # 通过 resolve_op 检查操作合法性
        if target_type:
            result_type = self.registry.resolve_op(target_type, node.op, val_type)
            if not result_type:
                self.error(
                    f"Augmented assignment operator '{node.op}' not supported for type '{target_type.name}'",
                    node, code="SEM_003"
                )
        return None

    def visit_IbCastExpr(self, node: ast.IbCastExpr) -> Optional[IbSpec]:
        """访问类型转换表达式 (e.g., (int) expr)"""
        self.visit(node.value)
        cast_type = self._resolve_type(node.type_annotation)
        self.bind_type(node, cast_type)
        return cast_type

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

    def visit_IbBoolOp(self, node: ast.IbBoolOp) -> Optional[IbSpec]:
        """访问布尔运算 (and/or)"""
        for val in node.values:
            self.visit(val)
        self.bind_type(node, self._bool_desc)
        return self._bool_desc

    def visit_IbIfExp(self, node: ast.IbIfExp) -> Optional[IbSpec]:
        """访问条件表达式 (x if cond else y)"""
        self.visit(node.test)
        body_type = self.visit(node.body)
        orelse_type = self.visit(node.orelse)
        # 两分支类型一致则返回该类型，否则返回 any
        if body_type and orelse_type and body_type.name == orelse_type.name:
            result_type = body_type
        else:
            result_type = self._any_desc
        self.bind_type(node, result_type)
        return result_type

    def visit_IbImport(self, node: ast.IbImport) -> Optional[IbSpec]:
        """访问 import 语句"""
        return None

    def visit_IbImportFrom(self, node: ast.IbImportFrom) -> Optional[IbSpec]:
        """访问 from ... import 语句"""
        return None

    def visit_IbIntentAnnotation(self, node: ast.IbIntentAnnotation) -> Optional[IbSpec]:
        """访问意图注释 (@ / @!)"""
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
        self.bind_type(node, expr_type)
        return expr_type

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
