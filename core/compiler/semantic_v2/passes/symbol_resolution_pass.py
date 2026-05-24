"""
Pass 2: Symbol Resolution Pass

职责：解析所有符号引用，绑定到 metadata
输入：Context with symbol_table
输出：Context with resolved symbol bindings
"""

from dataclasses import replace
from typing import Optional, List, Dict, Any

from core.kernel import ast
from core.kernel.symbols import Symbol, SymbolTable, SymbolKind

from ..result import PassResult, Diagnostic, DiagnosticLevel
from ..context import SemanticContext
from .base_pass import BasePass


class SymbolResolutionPass(BasePass):
    """符号解析 Pass（Pass 2）

    解析所有符号引用：
    - 名称引用（IbName）
    - 成员访问（IbAttribute）
    - 函数调用（IbCall）
    """

    def __init__(self):
        super().__init__("SymbolResolutionPass")

    def run(self, context: SemanticContext) -> PassResult:
        """运行符号解析 Pass"""
        visitor = SymbolResolver(context)
        visitor.visit(context.ast)

        # 更新 metadata 中的符号绑定（node object → Symbol）
        new_metadata = context.metadata
        for node, symbol in visitor.symbol_bindings.items():
            new_metadata.bind_symbol(node, symbol)

        new_context = context.with_metadata(new_metadata)

        return PassResult.ok(new_context, diagnostics=visitor.diagnostics)


class SymbolResolver:
    """符号解析访问者"""

    def __init__(self, context: SemanticContext):
        self.context = context
        self.symbol_table = context.symbol_table.current
        self.registry = context.registry
        self.diagnostics: List[Diagnostic] = []

        # 符号绑定：node object -> Symbol（使用对象身份作为键）
        self.symbol_bindings: Dict[Any, Symbol] = {}

        # 作用域栈（用于处理嵌套作用域）
        self.scope_stack: List[SymbolTable] = [self.symbol_table]

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

    def visit(self, node: ast.IbASTNode):
        """访问节点的分派方法"""
        if node is None:
            return
        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ast.IbASTNode):
        """默认访问：递归访问所有子节点"""
        for attr in vars(node):
            child = getattr(node, attr)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.IbASTNode):
                        self.visit(item)
            elif isinstance(child, ast.IbASTNode):
                self.visit(child)

    def error(self, message: str, node: ast.IbASTNode, code: str = "SEM_000"):
        """记录错误诊断"""
        node_uid = getattr(node, 'uid', None)
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.ERROR,
            message=message,
            code=code,
            node_uid=node_uid
        ))

    def lookup_symbol(self, name: str) -> Optional[Symbol]:
        """在当前作用域查找符号"""
        return self.current_scope.resolve(name)

    def bind_symbol(self, node: ast.IbASTNode, symbol: Symbol):
        """绑定符号到节点（使用节点对象作为键）"""
        if node and symbol:
            self.symbol_bindings[node] = symbol

    def visit_IbModule(self, node: ast.IbModule):
        """访问模块节点"""
        for stmt in node.body:
            self.visit(stmt)

    def visit_IbName(self, node: ast.IbName):
        """访问名称引用节点"""
        # 查找符号定义
        sym = self.lookup_symbol(node.id)
        if not sym:
            self.error(f"Undefined symbol '{node.id}'", node, code="SEM_001")
            return

        # 绑定到 metadata
        self.bind_symbol(node, sym)

    def visit_IbClassDef(self, node: ast.IbClassDef):
        """访问类定义节点"""
        # 查找类符号
        sym = self.lookup_symbol(node.name)
        if sym and hasattr(sym, 'owned_scope') and sym.owned_scope:
            # 进入类作用域
            self.push_scope(sym.owned_scope)
            try:
                for stmt in node.body:
                    self.visit(stmt)
            finally:
                self.pop_scope()
        else:
            # 没有作用域信息，只处理 body
            for stmt in node.body:
                self.visit(stmt)

    def _register_params(self, args: list, scope: SymbolTable):
        """将函数参数注册为局部符号。"""
        from core.kernel.symbols import VariableSymbol, SymbolKind

        for arg_node in args:
            arg_name = self._extract_arg_name(arg_node)
            if arg_name:
                param_sym = VariableSymbol(
                    name=arg_name,
                    kind=SymbolKind.VARIABLE,
                    def_node=arg_node,
                    spec=self.registry.resolve("any"),
                )
                scope.define(param_sym)

    @staticmethod
    def _extract_arg_name(arg_node: ast.IbASTNode) -> Optional[str]:
        """从参数节点提取参数名。"""
        if isinstance(arg_node, ast.IbArg):
            return arg_node.arg
        elif isinstance(arg_node, ast.IbTypeAnnotatedExpr):
            if isinstance(arg_node.target, ast.IbArg):
                return arg_node.target.arg
            elif isinstance(arg_node.target, ast.IbName):
                return arg_node.target.id
        return None

    def visit_IbFunctionDef(self, node: ast.IbFunctionDef):
        """访问函数定义节点"""
        # 创建函数作用域
        func_scope = SymbolTable(parent=self.current_scope, name=node.name)

        # 绑定函数符号到节点
        func_sym = self.lookup_symbol(node.name)
        if func_sym:
            self.bind_symbol(node, func_sym)
            if hasattr(func_sym, 'owned_scope'):
                func_sym.owned_scope = func_scope

        # 进入函数作用域
        self.push_scope(func_scope)
        try:
            self._register_params(node.args, func_scope)
            self._prescan_body_locals(node.body, func_scope)

            for stmt in node.body:
                self.visit(stmt)
        finally:
            self.pop_scope()

    def visit_IbLLMFunctionDef(self, node: ast.IbLLMFunctionDef):
        """访问 LLM 函数定义节点"""
        # 创建函数作用域
        func_scope = SymbolTable(parent=self.current_scope, name=node.name)

        # 绑定函数符号到节点
        func_sym = self.lookup_symbol(node.name)
        if func_sym:
            self.bind_symbol(node, func_sym)
            if hasattr(func_sym, 'owned_scope'):
                func_sym.owned_scope = func_scope

        # 进入函数作用域
        self.push_scope(func_scope)
        try:
            self._register_params(node.args, func_scope)

            # LLM 函数的提示词段落（sys_prompt / user_prompt / retry_hint）
            for prompt_list in (node.sys_prompt, node.user_prompt, node.retry_hint):
                if prompt_list:
                    for segment in prompt_list:
                        if isinstance(segment, ast.IbASTNode):
                            self.visit(segment)
        finally:
            self.pop_scope()

    def visit_IbAssign(self, node: ast.IbAssign):
        """访问赋值节点 — 对齐 v1：绑定 IbAssign 和 IbTypeAnnotatedExpr 到目标符号"""
        # 先处理右侧表达式
        self.visit(node.value)

        # 处理左侧目标
        for target in node.targets:
            self.visit(target)

            # 对齐 v1 _bind_symbol_to_side_table：将 IbAssign 和 IbTypeAnnotatedExpr 也绑定到符号
            var_name = self._extract_target_name(target)
            if var_name:
                sym = self.lookup_symbol(var_name)
                if sym:
                    # 绑定 IbAssign 节点 → symbol
                    self.bind_symbol(node, sym)
                    # 绑定 IbTypeAnnotatedExpr 节点 → symbol（如果 target 是带类型的）
                    if isinstance(target, ast.IbTypeAnnotatedExpr):
                        self.bind_symbol(target, sym)

    @staticmethod
    def _extract_target_name(target) -> Optional[str]:
        """从赋值目标提取变量名。"""
        if isinstance(target, ast.IbName):
            return target.id
        elif isinstance(target, ast.IbTypeAnnotatedExpr):
            if isinstance(target.target, ast.IbName):
                return target.target.id
            elif isinstance(target.target, ast.IbArg):
                return target.target.arg
        return None

    def visit_IbBinOp(self, node: ast.IbBinOp):
        """访问二元运算节点"""
        self.visit(node.left)
        self.visit(node.right)

    def visit_IbUnaryOp(self, node: ast.IbUnaryOp):
        """访问一元运算节点"""
        self.visit(node.operand)

    def visit_IbCall(self, node: ast.IbCall):
        """访问函数调用节点"""
        # 处理被调用对象
        self.visit(node.func)

        # 处理参数
        for arg in node.args:
            self.visit(arg)

    def visit_IbAttribute(self, node: ast.IbAttribute):
        """访问属性访问节点"""
        # 处理对象
        self.visit(node.value)
        # attr 是字符串，不需要解析

    def visit_IbSubscript(self, node: ast.IbSubscript):
        """访问下标访问节点"""
        self.visit(node.value)
        self.visit(node.slice)

    def visit_IbIf(self, node: ast.IbIf):
        """访问 if 语句节点"""
        self.visit(node.test)
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_IbWhile(self, node: ast.IbWhile):
        """访问 while 语句节点"""
        self.visit(node.test)
        for stmt in node.body:
            self.visit(stmt)

    def _register_loop_variable(self, name: str, target_node: ast.IbASTNode, def_node: ast.IbASTNode):
        """Register a loop variable in scope and bind its symbol to the target node."""
        from core.kernel.symbols import VariableSymbol, SymbolKind

        if not self.lookup_symbol(name):
            loop_var_sym = VariableSymbol(
                name=name,
                kind=SymbolKind.VARIABLE,
                def_node=def_node,
                spec=self.registry.resolve("any"),
            )
            self.current_scope.define(loop_var_sym)
        sym = self.lookup_symbol(name)
        if sym:
            self.bind_symbol(target_node, sym)

    def visit_IbFor(self, node: ast.IbFor):
        """访问 for 语句节点"""
        # 处理迭代对象
        if node.iter:
            self.visit(node.iter)

        # 注册循环变量到当前作用域（确保循环体内可引用）
        if node.target:
            if isinstance(node.target, ast.IbName):
                self._register_loop_variable(node.target.id, node.target, node)
            elif isinstance(node.target, ast.IbTuple):
                # Tuple unpacking in for loop: for (a, b) in ...
                for elt in node.target.elts:
                    if isinstance(elt, ast.IbName):
                        self._register_loop_variable(elt.id, elt, node)
            else:
                self.visit(node.target)

        # 处理循环体
        for stmt in node.body:
            self.visit(stmt)

    def visit_IbReturn(self, node: ast.IbReturn):
        """访问 return 语句节点"""
        if node.value:
            self.visit(node.value)

    def visit_IbTry(self, node: ast.IbTry):
        """访问 try 语句节点"""
        for stmt in node.body:
            self.visit(stmt)

        for handler in node.handlers:
            self.visit(handler)

        for stmt in node.orelse:
            self.visit(stmt)

        for stmt in node.finalbody:
            self.visit(stmt)

    def visit_IbExceptHandler(self, node: ast.IbExceptHandler):
        """访问异常处理器节点"""
        if node.type:
            self.visit(node.type)

        for stmt in node.body:
            self.visit(stmt)

    def visit_IbTypeAnnotatedExpr(self, node: ast.IbTypeAnnotatedExpr):
        """访问带类型标注的表达式"""
        self.visit(node.target)
        # annotation 在 Pass 3 处理

    def visit_IbLambdaExpr(self, node: ast.IbLambdaExpr):
        """访问 lambda 表达式节点"""
        # 创建 lambda 作用域
        lambda_scope = SymbolTable(parent=self.current_scope, name="<lambda>")

        self.push_scope(lambda_scope)
        try:
            # 处理参数
            for arg in node.args:
                self.visit(arg)

            # 处理 body
            for stmt in node.body:
                self.visit(stmt)
        finally:
            self.pop_scope()

    def visit_IbBehaviorExpr(self, node: ast.IbBehaviorExpr):
        """访问行为表达式节点"""
        # 处理 segments 中的插值表达式
        for segment in node.segments:
            if isinstance(segment, ast.IbASTNode):
                self.visit(segment)

    # 字面量节点不需要符号解析
    def visit_IbConstant(self, node: ast.IbConstant):
        """访问常量字面量（int, float, str, bool, None）"""
        pass

    def visit_IbListExpr(self, node: ast.IbListExpr):
        """访问列表字面量"""
        for elt in node.elts:
            self.visit(elt)

    def visit_IbDict(self, node: ast.IbDict):
        """访问字典字面量"""
        for key, value in zip(node.keys, node.values):
            self.visit(key)
            self.visit(value)

    def visit_IbTuple(self, node: ast.IbTuple):
        """访问元组字面量"""
        for elt in node.elts:
            self.visit(elt)

    # ========== 辅助方法 ==========

    def _prescan_body_locals(self, body: list, scope: SymbolTable):
        """预扫描函数体，将赋值目标预注册为局部变量。

        这与 v1 的 Pass 2.5 预扫描逻辑对应：确保函数体内的变量
        在被引用时已经有定义（避免 SEM_001 误报）。
        """
        from core.kernel.symbols import VariableSymbol, SymbolKind
        from .symbol_collection_pass import SymbolExtractor

        for stmt in body:
            if isinstance(stmt, ast.IbAssign):
                for name, target in SymbolExtractor.get_assigned_names(stmt):
                    if name not in scope.symbols:
                        sym = VariableSymbol(
                            name=name,
                            kind=SymbolKind.VARIABLE,
                            def_node=stmt,
                            spec=self.registry.resolve("any"),
                        )
                        scope.define(sym)
            elif isinstance(stmt, ast.IbFor):
                # for 循环变量
                if stmt.target:
                    if isinstance(stmt.target, ast.IbName):
                        name = stmt.target.id
                        if name not in scope.symbols:
                            sym = VariableSymbol(
                                name=name,
                                kind=SymbolKind.VARIABLE,
                                def_node=stmt,
                                spec=self.registry.resolve("any"),
                            )
                            scope.define(sym)
            # 递归进入 if/for/while body
            if hasattr(stmt, 'body') and isinstance(getattr(stmt, 'body'), list):
                self._prescan_body_locals(getattr(stmt, 'body'), scope)
            if hasattr(stmt, 'orelse') and isinstance(getattr(stmt, 'orelse'), list):
                self._prescan_body_locals(getattr(stmt, 'orelse'), scope)
