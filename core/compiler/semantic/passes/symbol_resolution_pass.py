"""
Pass 2: Symbol Resolution Pass

职责：解析所有符号引用，绑定到 metadata
输入：Context with symbol_table
输出：Context with resolved symbol bindings
"""

from dataclasses import replace
from typing import Optional, List, Dict, Any

from core.kernel import ast
from core.kernel.symbols import Symbol, SymbolTable, SymbolKind, VariableSymbol

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

        # 更新 metadata 中的符号绑定
        new_bindings = visitor.symbol_bindings
        new_metadata = context.metadata
        # 直接更新 symbol_bindings
        for node_uid, symbol in new_bindings.items():
            new_metadata.symbol_bindings[node_uid] = symbol

        new_context = context.with_metadata(new_metadata)

        return PassResult.ok(new_context, diagnostics=visitor.diagnostics)


class SymbolResolver:
    """符号解析访问者"""

    def __init__(self, context: SemanticContext):
        self.context = context
        self.symbol_table = context.symbol_table.current
        self.registry = context.registry
        self.diagnostics: List[Diagnostic] = []

        # 符号绑定：node_uid -> Symbol
        self.symbol_bindings: Dict[str, Symbol] = {}

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
        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ast.IbASTNode):
        """默认访问：递归访问所有子节点"""
        # Skip if node is None
        if node is None:
            return

        # Use __dict__ for dataclass nodes, or iterate through known attributes
        if hasattr(node, '__dict__'):
            attrs = vars(node)
        else:
            # Fallback: just return for non-dict objects
            return

        for attr_name, child in attrs.items():
            if attr_name.startswith('_'):
                continue
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
        """在当前作用域及父作用域链中查找符号"""
        return self.current_scope.resolve(name)

    def bind_symbol(self, node: ast.IbASTNode, symbol: Symbol):
        """绑定符号到节点"""
        node_uid = getattr(node, 'uid', None)
        if node_uid:
            self.symbol_bindings[node_uid] = symbol

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

    def visit_IbFunctionDef(self, node: ast.IbFunctionDef):
        """访问函数定义节点"""
        # 创建函数作用域
        func_scope = SymbolTable(parent=self.current_scope, name=node.name)

        # 进入函数作用域
        self.push_scope(func_scope)
        try:
            # 处理参数 - 添加到函数作用域
            for arg in node.args:
                # arg can be IbArg or IbTypeAnnotatedExpr(target=IbArg, annotation=...)
                param_name = None
                if isinstance(arg, ast.IbTypeAnnotatedExpr) and isinstance(arg.target, ast.IbArg):
                    param_name = arg.target.arg
                elif isinstance(arg, ast.IbArg):
                    param_name = arg.arg

                if param_name:
                    # Define parameter as variable symbol in function scope
                    param_sym = VariableSymbol(
                        name=param_name,
                        kind=SymbolKind.VARIABLE,
                        spec=None  # Type will be resolved in type checking pass
                    )
                    func_scope.define(param_sym)

                # Visit for type resolution
                self.visit(arg)

            # 处理函数体
            for stmt in node.body:
                self.visit(stmt)
        finally:
            self.pop_scope()

    def visit_IbLLMFunctionDef(self, node: ast.IbLLMFunctionDef):
        """访问 LLM 函数定义节点"""
        # 创建函数作用域
        func_scope = SymbolTable(parent=self.current_scope, name=node.name)

        # 进入函数作用域
        self.push_scope(func_scope)
        try:
            # 处理参数 - 添加到函数作用域
            for arg in node.args:
                # arg can be IbArg or IbTypeAnnotatedExpr(target=IbArg, annotation=...)
                param_name = None
                if isinstance(arg, ast.IbTypeAnnotatedExpr) and isinstance(arg.target, ast.IbArg):
                    param_name = arg.target.arg
                elif isinstance(arg, ast.IbArg):
                    param_name = arg.arg

                if param_name:
                    # Define parameter as variable symbol in function scope
                    param_sym = VariableSymbol(
                        name=param_name,
                        kind=SymbolKind.VARIABLE,
                        spec=None  # Type will be resolved in type checking pass
                    )
                    func_scope.define(param_sym)

                # Visit for type resolution
                self.visit(arg)

            # 处理函数体（segments）
            for segment in node.segments:
                if isinstance(segment, ast.IbASTNode):
                    self.visit(segment)
        finally:
            self.pop_scope()

    def visit_IbAssign(self, node: ast.IbAssign):
        """访问赋值节点"""
        # 先处理右侧表达式（可能为None，如类字段声明）
        if node.value is not None:
            self.visit(node.value)

        # 处理左侧目标
        for target in node.targets:
            self.visit(target)

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
        self.visit(node.index)

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

    def visit_IbFor(self, node: ast.IbFor):
        """访问 for 语句节点"""
        # 处理迭代对象
        if node.iter:
            self.visit(node.iter)

        # 处理目标变量
        if node.target:
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
            # 处理参数 - 添加到lambda作用域
            for arg in node.args:
                # arg can be IbArg or IbTypeAnnotatedExpr(target=IbArg, annotation=...)
                param_name = None
                if isinstance(arg, ast.IbTypeAnnotatedExpr) and isinstance(arg.target, ast.IbArg):
                    param_name = arg.target.arg
                elif isinstance(arg, ast.IbArg):
                    param_name = arg.arg

                if param_name:
                    # Define parameter as variable symbol in lambda scope
                    param_sym = VariableSymbol(
                        name=param_name,
                        kind=SymbolKind.VARIABLE,
                        spec=None  # Type will be resolved in type checking pass
                    )
                    lambda_scope.define(param_sym)

                # Visit for type resolution
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
