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

        # 更新 metadata 中的类型绑定
        new_metadata = context.metadata
        for node_uid, type_spec in visitor.type_bindings.items():
            new_metadata.type_bindings[node_uid] = type_spec

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

        # 类型绑定：node_uid -> IbSpec
        self.type_bindings: Dict[str, IbSpec] = {}

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
        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ast.IbASTNode) -> Optional[IbSpec]:
        """默认访问：递归访问所有子节点，返回 any 类型"""
        for attr, child in (vars(node).items() if node and hasattr(node, '__dict__') else []):
            if attr.startswith('_'):
                continue
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
        """绑定类型到节点"""
        node_uid = getattr(node, 'uid', None)
        if node_uid and type_spec:
            self.type_bindings[node_uid] = type_spec

    def lookup_symbol(self, name: str) -> Optional[Symbol]:
        """在当前作用域查找符号"""
        return self.current_scope.symbols.get(name)

    def is_assignable(self, source: IbSpec, target: IbSpec) -> bool:
        """检查源类型是否可以赋给目标类型"""
        if not source or not target:
            return True
        return self.registry.is_assignable(source, target)

    def _resolve_type(self, annotation: ast.IbASTNode) -> Optional[IbSpec]:
        """解析类型标注"""
        if isinstance(annotation, ast.IbName):
            return self.registry.resolve(annotation.id)
        elif isinstance(annotation, ast.IbSubscript):
            # 泛型类型：list[int], dict[str, int] 等
            # value 是基础类型（如 list），slice 是类型参数（如 int）
            base_type = self.registry.resolve(annotation.value.id if isinstance(annotation.value, ast.IbName) else "any")
            # 简化处理：返回基础类型，忽略类型参数
            return base_type
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
        # 先计算右侧表达式的类型（可能为None，如类字段声明）
        if node.value is not None:
            val_type = self.visit(node.value)
            if not val_type:
                val_type = self._any_desc
        else:
            # 类字段声明（无初始化值）：不需要类型检查
            # 只需要绑定声明的类型
            for target in node.targets:
                var_name, declared_type = self._resolve_target_name_and_type(target)
                if var_name and declared_type:
                    self.bind_type(target, declared_type)
            return self._void_desc

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
        """处理单个赋值目标"""
        # 提取变量名和声明类型
        var_name, declared_type = self._resolve_target_name_and_type(target)

        if var_name:
            # 简单变量赋值
            sym = self.lookup_symbol(var_name)

            if declared_type:
                # 有类型标注：固定类型
                target_type = declared_type
            elif sym and sym.spec:
                # 已存在的符号：使用现有类型
                target_type = sym.spec
            else:
                # 首次定义无类型标注：推断类型
                target_type = val_type

            # 类型兼容性检查
            # 对于泛型类型，先尝试提取基础类型进行比较
            # 对于 any 类型，允许赋值给任何类型
            if val_type.name == 'any' or target_type.name == 'any':
                # any 可以赋值给任何类型，任何类型也可以赋值给 any
                pass
            elif not self.is_assignable(val_type, target_type):
                # 如果直接检查失败，且目标类型名包含 "[" (泛型)，尝试匹配基础类型
                # 例如：list 可以赋值给 list[int]
                target_base_name = target_type.name.split('[')[0] if '[' in target_type.name else target_type.name
                val_base_name = val_type.name.split('[')[0] if '[' in val_type.name else val_type.name

                if target_base_name != val_base_name:
                    hint = self.registry.get_diff_hint(val_type, target_type) if hasattr(self.registry, 'get_diff_hint') else None
                    self.error(
                        f"Cannot assign '{val_type.name}' to '{target_type.name}'",
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
                    f"Cannot assign '{val_type.name}' to '{target_type.name}'",
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

    def visit_IbIf(self, node: ast.IbIf) -> Optional[IbSpec]:
        """访问 if 语句"""
        self.visit(node.test)
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)
        return None

    def visit_IbWhile(self, node: ast.IbWhile) -> Optional[IbSpec]:
        """访问 while 语句"""
        self.visit(node.test)
        for stmt in node.body:
            self.visit(stmt)
        return None

    def visit_IbFor(self, node: ast.IbFor) -> Optional[IbSpec]:
        """访问 for 语句"""
        if node.iter:
            self.visit(node.iter)
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
        """访问函数定义"""
        # 创建函数作用域
        func_scope = SymbolTable(parent=self.current_scope, name=node.name)

        # 检查是否是 -> auto 函数
        is_auto_return = (node.returns and
                         isinstance(node.returns, ast.IbName) and
                         node.returns.id == "auto")

        old_in_function = self.in_function_def
        old_auto_returns = self.auto_return_types

        self.in_function_def = True
        if is_auto_return:
            self.auto_return_types = []

        self.push_scope(func_scope)
        try:
            # 处理参数
            for arg in node.args:
                self.visit(arg)

            # 处理函数体
            for stmt in node.body:
                self.visit(stmt)

            # 如果是 auto 返回，推断返回类型
            if is_auto_return and self.auto_return_types:
                # 简化处理：取第一个返回类型
                inferred_return = self.auto_return_types[0] if self.auto_return_types else self._void_desc
                # TODO: 更新符号的返回类型

        finally:
            self.pop_scope()
            self.in_function_def = old_in_function
            self.auto_return_types = old_auto_returns

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
            for segment in node.segments:
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
            self.bind_type(node, sym.spec)
            return sym.spec
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
        """访问二元运算"""
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)

        # 简化推断：数值运算
        if left_type in (self._int_desc, self._float_desc) and right_type in (self._int_desc, self._float_desc):
            # 如果任一为 float，结果为 float
            result_type = self._float_desc if (left_type == self._float_desc or right_type == self._float_desc) else self._int_desc
        elif left_type == self._str_desc or right_type == self._str_desc:
            # 字符串运算
            result_type = self._str_desc
        else:
            result_type = self._any_desc

        self.bind_type(node, result_type)
        return result_type

    def visit_IbUnaryOp(self, node: ast.IbUnaryOp) -> Optional[IbSpec]:
        """访问一元运算"""
        operand_type = self.visit(node.operand)
        # 简化处理：一元运算保持操作数类型
        self.bind_type(node, operand_type)
        return operand_type

    def visit_IbCompare(self, node: ast.IbCompare) -> Optional[IbSpec]:
        """访问比较运算"""
        self.visit(node.left)
        for comparator in node.comparators:
            self.visit(comparator)
        # 比较运算返回 bool
        self.bind_type(node, self._bool_desc)
        return self._bool_desc

    def visit_IbCall(self, node: ast.IbCall) -> Optional[IbSpec]:
        """访问函数调用"""
        # 处理被调用对象
        func_type = self.visit(node.func)

        # 处理参数
        for arg in node.args:
            self.visit(arg)

        # 推断返回类型
        if func_type and hasattr(func_type, 'ret'):
            return_type = func_type.ret
        else:
            return_type = self._any_desc

        self.bind_type(node, return_type)
        return return_type

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
            for arg in node.args:
                self.visit(arg)
            for stmt in node.body:
                self.visit(stmt)
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
