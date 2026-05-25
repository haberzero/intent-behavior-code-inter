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
from .scoped_visitor import ScopedVisitor


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


class SymbolResolver(ScopedVisitor):
    """符号解析访问者"""

    def __init__(self, context: SemanticContext):
        super().__init__(context)

        # 符号绑定：node object -> Symbol（使用对象身份作为键）
        self.symbol_bindings: Dict[Any, Symbol] = {}

        # 当前所在类的符号（用于注入 self）
        self.current_class_symbol: Optional[Symbol] = None

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
        if sym:
            # 绑定 IbClassDef 节点到符号（vm_handle_IbClassDef 通过 node_to_symbol 查找）
            self.bind_symbol(node, sym)
            saved_class = self.current_class_symbol
            self.current_class_symbol = sym
            if hasattr(sym, 'owned_scope') and sym.owned_scope:
                # 进入类作用域
                self.push_scope(sym.owned_scope)
                try:
                    for stmt in node.body:
                        self.visit(stmt)
                finally:
                    self.pop_scope()
            else:
                for stmt in node.body:
                    self.visit(stmt)
            self.current_class_symbol = saved_class
            return
        # 没有符号信息，只处理 body
        for stmt in node.body:
            self.visit(stmt)

    def _register_params(self, args: list, scope: SymbolTable):
        """将函数参数注册为局部符号，并绑定 IbArg 节点到 node_to_symbol。"""
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

                # 绑定 IbArg 节点到符号（vm_handle_IbCall 通过 node_to_symbol[arg_uid] 查找）
                # 如果外层是 IbTypeAnnotatedExpr，runtime 会先解包到 target (IbArg)
                if isinstance(arg_node, ast.IbArg):
                    self.bind_symbol(arg_node, param_sym)
                elif isinstance(arg_node, ast.IbTypeAnnotatedExpr):
                    if isinstance(arg_node.target, ast.IbArg):
                        self.bind_symbol(arg_node.target, param_sym)

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
            if hasattr(func_sym, 'owned_scope'):
                func_sym.owned_scope = func_scope

        # 进入函数作用域
        self.push_scope(func_scope)
        try:
            # 隐式 self 注入：如果是类方法，在局部作用域注入 self 符号
            # node_to_symbol[func_def_node] = self_symbol（runtime 通过此获取 self UID）
            if self.current_class_symbol:
                from core.kernel.symbols import VariableSymbol, SymbolKind
                self_sym = VariableSymbol(
                    name="self",
                    kind=SymbolKind.VARIABLE,
                    def_node=node,
                    spec=self.current_class_symbol.spec if hasattr(self.current_class_symbol, 'spec') else self.registry.resolve("any"),
                )
                func_scope.define(self_sym)
                # IbFunctionDef 节点绑定到 self 符号（runtime kernel.py:965 依赖此映射）
                self.bind_symbol(node, self_sym)
            elif func_sym:
                self.bind_symbol(node, func_sym)

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
        """访问赋值节点 — 绑定 IbAssign 和 IbTypeAnnotatedExpr 到目标符号"""
        # 先处理右侧表达式
        self.visit(node.value)

        # 处理左侧目标
        for target in node.targets:
            self.visit(target)

            # 将 IbAssign 和 IbTypeAnnotatedExpr 也绑定到符号
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
            elif isinstance(node.target, ast.IbTypeAnnotatedExpr):
                # for int item in items: — target is IbTypeAnnotatedExpr
                inner = node.target.target
                if isinstance(inner, ast.IbName):
                    self._register_loop_variable(inner.id, inner, node)
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

        # 注册 `as e` 捕获变量到当前作用域，并绑定 handler 节点到符号
        # (runtime vm_handle_IbTry:1883 通过 node_to_symbol[handler_uid] 获取 sym_uid)
        if node.name:
            from core.kernel.symbols import VariableSymbol, SymbolKind
            existing = self.lookup_symbol(node.name)
            if not existing:
                exc_sym = VariableSymbol(
                    name=node.name,
                    kind=SymbolKind.VARIABLE,
                    def_node=node,
                    spec=self.registry.resolve("any"),
                )
                self.current_scope.define(exc_sym)
                self.bind_symbol(node, exc_sym)
            else:
                self.bind_symbol(node, existing)

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
            # 注册参数并绑定 IbArg 节点
            self._register_params(node.params, lambda_scope)

            # 处理 body（lambda body 是单个表达式，不是列表）
            if node.body:
                self.visit(node.body)
        finally:
            self.pop_scope()

    def visit_IbBehaviorExpr(self, node: ast.IbBehaviorExpr):
        """访问行为表达式节点"""
        # 处理 segments 中的插值表达式
        for segment in node.segments:
            if isinstance(segment, ast.IbASTNode):
                self.visit(segment)

    def visit_IbImport(self, node: ast.IbImport):
        """访问 import 语句节点

        将 IbAlias 节点绑定到 scheduler 预注入的符号，
        以便 vm_handle_IbImport 能通过 node_to_symbol 获取正确的 UID。
        """
        for alias in node.names:
            name = alias.asname or alias.name
            sym = self.lookup_symbol(name)
            if sym:
                self.bind_symbol(alias, sym)
            else:
                self.error(f"Module '{name}' not found or failed to load", node, code="SEM_001")

    def visit_IbImportFrom(self, node: ast.IbImportFrom):
        """访问 from ... import 语句节点

        将每个 IbAlias 节点绑定到 scheduler 预注入的符号。
        """
        for alias in node.names:
            if alias.name == '*':
                # import * 由 Scheduler 处理符号注入，此处无需绑定
                continue
            name = alias.asname or alias.name
            sym = self.lookup_symbol(name)
            if sym:
                self.bind_symbol(alias, sym)
            else:
                self.error(f"Cannot import name '{alias.name}' from '{node.module}'", node, code="SEM_001")

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

        确保函数体内的变量在被引用时已经有定义（避免 SEM_001 误报）。
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
            elif isinstance(stmt, ast.IbFunctionDef):
                # 嵌套函数定义：在当前作用域注册函数名
                name = stmt.name
                if name and name not in scope.symbols:
                    sym = VariableSymbol(
                        name=name,
                        kind=SymbolKind.VARIABLE,
                        def_node=stmt,
                        spec=self.registry.resolve("fn"),
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
