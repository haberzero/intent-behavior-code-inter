"""
Symbol Resolution Pass (SymbolPhase sub-step 2)

职责：解析所有符号引用
输入：Context with symbol_table
输出：PassOutput with symbol_bindings
"""

from typing import Optional, List, Dict, Any

from core.base.diagnostics.codes import (
    SEM_INTENT_PLACEMENT,
    SEM_NONLOCAL_NOT_FOUND,
    SEM_UNDEFINED_SYMBOL,
    SEM_UNRESOLVED_TYPE,
)
from ._fn_callable import CALLABLE_INTERNAL_TYPE_MSG
from core.kernel import ast
from core.kernel.symbols import Symbol, SymbolTable, SymbolKind, VariableSymbol
from core.base.uid import intrinsic_uid
from core.kernel.spec import IbSpec
from core.kernel.spec.base import TypeDef
from core.kernel.spec.type_ref import TypeRef

from ..result import PassResult, PassOutput, Diagnostic, DiagnosticLevel
from ..context import SemanticContext
from .base_pass import BasePass
from .scoped_visitor import ScopedVisitor
from .symbol_collection_pass import SymbolExtractor


class SymbolResolutionPass(BasePass):
    """符号解析 Pass（SymbolPhase sub-step 2）

    解析所有符号引用：
    - 名称引用（IbName）
    - 成员访问（IbAttribute）
    - 函数调用（IbCall）
    """

    def __init__(self):
        super().__init__("SymbolResolutionPass")

    def run(self, context: SemanticContext) -> PassResult:
        visitor = SymbolResolver(context)
        visitor.visit(context.ast)

        output = PassOutput(
            symbol_bindings=dict(visitor.symbol_bindings),
            diagnostics=visitor.diagnostics,
            success=True,
        )
        return PassResult.ok(context, output=output)


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
            # 布尔/空值字面量大小写引导：IBCI 与 Python 一致，字面量大写
            # （True/False/None）。用户写小写（true/false/none）时给出修正
            # 提示，避免误判为未定义变量。
            lower = node.id.lower()
            if lower in ("true", "false", "none"):
                self.error(
                    f"Undefined symbol '{node.id}'. Did you mean '{lower.capitalize()}'? "
                    f"IBCI boolean/null literals are capitalized (True/False/None).",
                    node, code=SEM_UNDEFINED_SYMBOL,
                )
            else:
                self.error(f"Undefined symbol '{node.id}'", node, code=SEM_UNDEFINED_SYMBOL)
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
        """将函数参数注册为局部符号，并绑定 IbArg 节点到 node_to_symbol。

        参数符号 spec 从类型标注解析（非恒 any）——运行时符号池（序列化）
        据此承载声明类型，使参数绑定路径可做 Optional 值包装（统一 Optional
        值模型：函数参数 Optional[T] 空值包装为 IbOptional，而非裸 None）。
        """
        for arg_node in args:
            arg_name = self._extract_arg_name(arg_node)
            if arg_name:
                param_spec = self._resolve_param_annotation(arg_node)
                param_sym = VariableSymbol(
                    name=arg_name,
                    kind=SymbolKind.VARIABLE,
                    def_node=arg_node,
                    spec=param_spec,
                )
                scope.define(param_sym)

                # 绑定 IbArg 节点到符号（vm_handle_IbCall 通过 node_to_symbol[arg_uid] 查找）
                # All args are now IbArg (no IbTypeAnnotatedExpr wrapper)
                if isinstance(arg_node, ast.IbArg):
                    self.bind_symbol(arg_node, param_sym)

    def _resolve_param_annotation(self, arg_node: ast.IbASTNode) -> Optional[IbSpec]:
        """从参数节点类型标注解析 spec（含泛型/模块限定；未标注回落 any）。"""
        annotation = getattr(arg_node, "annotation", None)
        if annotation is None:
            return self.registry.resolve("any")
        return self._resolve_annotation_spec(annotation)

    @staticmethod
    def _visit_param_defaults(visitor, args: list):
        """在定义包围作用域访问各参数的默认值表达式（默认值定义时求值）。"""
        for arg_node in args:
            target = arg_node.target if isinstance(arg_node, ast.IbTypeAnnotatedExpr) else arg_node
            if isinstance(target, ast.IbArg) and target.default is not None:
                visitor.visit(target.default)

    @staticmethod
    def _extract_arg_name(arg_node: ast.IbASTNode) -> Optional[str]:
        """从参数节点提取参数名。IbArg now has annotation field directly."""
        if isinstance(arg_node, ast.IbArg):
            return arg_node.arg
        return None

    def visit_IbFunctionDef(self, node: ast.IbFunctionDef):
        """访问函数定义节点"""
        # 默认值表达式在定义包围作用域求值（Python 语义）
        self._visit_param_defaults(self, node.args)

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
                self_sym = VariableSymbol(
                    name="self",
                    kind=SymbolKind.VARIABLE,
                    def_node=node,
                    spec=self.current_class_symbol.spec if hasattr(self.current_class_symbol, 'spec') else self.registry.resolve("any"),
                )
                func_scope.define(self_sym)
                # IbFunctionDef 节点绑定到 self 符号（runtime kernel.py:965 依赖此映射）
                self.bind_symbol(node, self_sym)

                # super() 注入：类有父类时，在方法作用域内注入 super 符号。
                # 与 runtime kernel.py:994-996 的 IbSuperProxy 注入逻辑对齐。
                # 使用固定 UID "intrinsic:super" 以匹配 runtime 的 define_variable 调用。
                cls_spec = getattr(self.current_class_symbol, 'spec', None)
                if cls_spec and getattr(cls_spec, 'parent_type', None):
                    super_sym = VariableSymbol(
                        name="super",
                        kind=SymbolKind.VARIABLE,
                        def_node=node,
                        spec=self.registry.resolve("any"),
                    )
                    super_sym.uid = intrinsic_uid("super")  # 固定 UID，与 runtime 对齐
                    func_scope.define(super_sym)
            elif func_sym:
                self.bind_symbol(node, func_sym)

            self._register_params(node.args, func_scope)

            # 收集 nonlocal/global 声明的名称，这些不应被 prescan 注册为局部变量
            nonlocal_names = self._collect_nonlocal_names(node.body)
            global_names = self._collect_global_names(node.body)
            self._prescan_body_locals(node.body, func_scope, nonlocal_names, global_names)

            for stmt in node.body:
                self.visit(stmt)
        finally:
            self.pop_scope()

    def visit_IbLLMFunctionDef(self, node: ast.IbLLMFunctionDef):
        """访问 LLM 函数定义节点"""
        # 默认值表达式在定义包围作用域求值（Python 语义）
        self._visit_param_defaults(self, node.args)

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

        # 处理参数（含 *expr 序列解包；IbStarred 经 generic_visit 访问其 value）
        for arg in node.args:
            self.visit(arg)

        # 处理具名实参（含 **expr 字典解包，IbKeyword.arg 为 None）
        for kw in node.keywords:
            self.visit(kw.value)

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

    def _resolve_annotation_spec(self, annotation: Optional[ast.IbASTNode]) -> Optional[IbSpec]:
        """解析类型标注（简单名 / 泛型 / 模块限定）。

        与 symbol_collection_pass ``_resolve_annotation`` 同构；未标注/无法解析
        回落 any。参数符号 spec 由此获得声明类型（运行时符号池承载），使参数
        绑定路径的 Optional 值包装可行。
        """
        if annotation is None:
            return self.registry.resolve("any")
        if isinstance(annotation, ast.IbName):
            # callable 内部类型名守卫（方向 A：用户面统一为 fn 族）。
            if annotation.id == "callable":
                self.error(
                    CALLABLE_INTERNAL_TYPE_MSG,
                    annotation, code=SEM_UNRESOLVED_TYPE,
                )
                return self.registry.resolve("any")
            return self.registry.resolve(annotation.id) or self.registry.resolve("any")
        if isinstance(annotation, ast.IbCallableType):
            # callable signature 约束 ``fn[(params) -> ret]``：与 type_checking
            # ``_resolve_type`` 同构，产出结构化 CALLABLE_SIG spec（否则退化为
            # 裸 fn，调用点参数个数/类型检查失效——参数/局部变量符号池承载
            # 的声明类型必须完整）。
            from core.kernel.spec.base import TypeKind
            from core.base.enums import Provenance, Visibility

            param_specs = [
                p for p in (self._resolve_annotation_spec(pt) for pt in annotation.param_types)
                if p is not None
            ]
            ret_spec = (
                self._resolve_annotation_spec(annotation.return_type)
                if annotation.return_type is not None
                else None
            )
            # 结构化构造（CALLABLE_SIG 签名模型根治）：参数/返回经 TypeRef.from_spec
            # 产结构化 ref，substitute 可穿透嵌套类型参数、resolve_typeref 可恢复。
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
        if isinstance(annotation, ast.IbAttribute):
            from ._type_checking_base import module_qualified_annotation

            module_path, type_name = module_qualified_annotation(annotation)
            if type_name is None:
                return self.registry.resolve("any")
            return (
                self.registry.resolve(type_name, module=module_path)
                or self.registry.resolve("any")
            )
        if isinstance(annotation, ast.IbSubscript):
            if isinstance(annotation.value, (ast.IbName, ast.IbAttribute)):
                if isinstance(annotation.value, ast.IbName):
                    base = self.registry.resolve(annotation.value.id)
                else:
                    from ._type_checking_base import module_qualified_annotation

                    module_path, type_name = module_qualified_annotation(annotation.value)
                    base = self.registry.resolve(type_name, module=module_path) if type_name else None
                if base is None:
                    return self.registry.resolve("any")
                if isinstance(annotation.slice, ast.IbTuple):
                    arg_specs = [
                        self._resolve_annotation_spec(elt) for elt in annotation.slice.elts
                    ]
                else:
                    arg_specs = [self._resolve_annotation_spec(annotation.slice)]
                arg_specs = [s for s in arg_specs if s is not None]
                if not arg_specs:
                    return base
                return (
                    self.registry.resolve_specialization(base, arg_specs)
                    or base
                )
            return self.registry.resolve("any")
        return self.registry.resolve("any")

    def _register_loop_variable(self, name: str, target_node: ast.IbASTNode, def_node: ast.IbASTNode,
                                spec: Optional[IbSpec] = None) -> None:
        """Register a loop variable in scope and bind its symbol to the target node.

        ``spec`` 为循环变量声明的类型（``for int x``）；未声明时回退 ``any``。
        声明类型在此传播，类型检查 pass 才能以具体类型解析循环体内的引用
        （否则恒为 any，使复合赋值等需要具体 RHS 类型的运算无法定型）。
        """
        if spec is None:
            spec = self.registry.resolve("any")

        if not self.lookup_symbol(name):
            loop_var_sym = VariableSymbol(
                name=name,
                kind=SymbolKind.VARIABLE,
                def_node=def_node,
                spec=spec,
            )
            self.current_scope.define(loop_var_sym)
        else:
            # 已存在符号（外层或先前声明）：本层声明带具体类型时更新其 spec
            sym = self.lookup_symbol(name)
            if spec is not None and not self.registry.is_dynamic(spec):
                sym.spec = spec
        sym = self.lookup_symbol(name)
        if sym:
            self.bind_symbol(target_node, sym)

    def visit_IbFor(self, node: ast.IbFor):
        """访问 for 语句节点"""
        # 处理迭代对象
        if node.iter:
            # for...if 过滤语法：先访问实际迭代对象，再注册循环变量，最后访问过滤条件
            if isinstance(node.iter, ast.IbFilteredExpr):
                self.visit(node.iter.expr)
            else:
                self.visit(node.iter)

        # 注册循环变量到当前作用域（确保循环体内可引用）
        if node.target:
            if isinstance(node.target, ast.IbName):
                self._register_loop_variable(node.target.id, node.target, node)
            elif isinstance(node.target, ast.IbTypeAnnotatedExpr):
                # for int item in items: - target is IbTypeAnnotatedExpr
                inner = node.target.target
                if isinstance(inner, ast.IbName):
                    self._register_loop_variable(
                        inner.id, inner, node,
                        spec=self._resolve_annotation_spec(node.target.annotation),
                    )
            elif isinstance(node.target, ast.IbTuple):
                # Tuple unpacking in for loop: for (a, b) in ...
                # 元素可为裸 IbName 或带类型标注的 IbTypeAnnotatedExpr(IbName)
                # （如 `for (int x, int y) in coords`），统一解包到内层名字。
                for elt in node.target.elts:
                    inner = elt.target if isinstance(elt, ast.IbTypeAnnotatedExpr) else elt
                    if isinstance(inner, ast.IbName):
                        self._register_loop_variable(
                            inner.id, inner, node,
                            spec=(self._resolve_annotation_spec(elt.annotation)
                                  if isinstance(elt, ast.IbTypeAnnotatedExpr) else None),
                        )
            else:
                self.visit(node.target)

        # 访问 for...if 的过滤条件（此时循环变量已注册，可安全引用）
        if node.iter and isinstance(node.iter, ast.IbFilteredExpr):
            self.visit(node.iter.filter)

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
        # annotation 在 TypePhase 处理

    def visit_IbLambdaExpr(self, node: ast.IbLambdaExpr):
        """访问 lambda 表达式节点"""
        # 默认值表达式在定义包围作用域求值（Python 语义）
        self._visit_param_defaults(self, node.params)

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
            # 多段导入（import a.b）无别名：局部绑定根段 a（Python 语义）。
            # scheduler 只注入根段符号；全名段经属性访问解析（subpkg.util 的
            # util 段在 subpkg 模块 spec 的 members 中，MemberSpec 纯数据形态）。
            local_name = name.split(".")[0] if (alias.asname is None and "." in name) else name
            sym = self.lookup_symbol(local_name)
            if sym:
                self.bind_symbol(alias, sym)
            else:
                self.error(f"Module '{name}' not found or failed to load", node, code=SEM_UNDEFINED_SYMBOL)

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
                self.error(f"Cannot import name '{alias.name}' from '{node.module}'", node, code=SEM_UNDEFINED_SYMBOL)

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

    def visit_IbNonlocalStmt(self, node: ast.IbNonlocalStmt):
        """访问 nonlocal 声明节点。

        验证 nonlocal 声明的名称确实存在于外层（父）作用域中。
        将每个 nonlocal 名称绑定到外层作用域的符号，使后续 visit_IbName
        能够正确解析到外层变量而非本地变量。
        """
        parent_scope = self.current_scope.parent if self.current_scope else None
        for name in node.names:
            if not parent_scope:
                self.error(
                    f"nonlocal declaration of '{name}' not allowed at module scope",
                    node, code=SEM_INTENT_PLACEMENT
                )
                continue
            # 在父作用域中查找符号
            outer_sym = parent_scope.resolve(name)
            if not outer_sym:
                self.error(
                    f"No binding for nonlocal '{name}' found in enclosing scope",
                    node, code=SEM_NONLOCAL_NOT_FOUND
                )
                continue
            # 将外层符号注册到当前作用域（不创建新符号，共享外层符号引用）
            # 这确保本作用域内对该名称的引用解析到外层符号的 UID
            if name not in self.current_scope.symbols:
                self.current_scope.symbols[name] = outer_sym

    def visit_IbGlobalStmt(self, node: ast.IbGlobalStmt):
        """访问 global 声明节点（docs/syntax/02_variables.md §2.6）。

        global 使函数内对声明的读写作用于模块级作用域（与 Python 语义一致）。
        把每个 global 名称解析/占位到模块根作用域，使函数内引用与赋值绑定到
        模块级符号 UID（scope_<module>:<name>），运行时经 UID 链命中全局路由。
        """
        global_scope = self.current_scope.get_global_scope() if self.current_scope else None
        for name in node.names:
            if global_scope is None:
                self.error(
                    f"global declaration of '{name}' not allowed",
                    node, code=SEM_INTENT_PLACEMENT
                )
                continue
            sym = global_scope.resolve(name)
            if sym is None:
                # 声明先于定义（Python 语义：global 之后才定义全局变量）→
                # 在模块作用域占位 any，运行时 define_variable_at_global 承载。
                sym = VariableSymbol(
                    name=name,
                    kind=SymbolKind.VARIABLE,
                    def_node=node,
                    spec=self.registry.resolve("any"),
                )
                sym.is_global = True
                global_scope.define(sym)
            else:
                sym.is_global = True
            global_scope.add_global_ref(name)
            # 当前函数作用域内注册对该全局符号的引用（不创建新局部符号），
            # 使 visit_IbName / visit_IbAssign 解析到模块级 UID。
            if name not in self.current_scope.symbols:
                self.current_scope.symbols[name] = sym

    # ========== 辅助方法 ==========

    def _prescan_target_spec(self, target: ast.IbASTNode) -> IbSpec:
        """预注册目标符号的类型 spec：带注解解析注解；无注解 auto 占位。

        与模块级语义对齐（``symbol_collection_pass``：带注解解析、裸赋值 auto
        占位由类型检查首赋值锁定）。此前硬编码 ``any`` 使函数局部变量的声明
        类型丢失（symbol_pool type_uid=any）：运行时 Optional 值包装失效、
        重赋值类型检查失效。注解解析失败回退 ``any``（prescan 宽容，不因
        前向引用误报）。
        """
        if isinstance(target, ast.IbTypeAnnotatedExpr) and target.annotation:
            spec = self._resolve_annotation_spec(target.annotation)
            if spec is not None:
                return spec
            return self.registry.resolve("any")
        return self.registry.resolve("auto")

    def _prescan_body_locals(self, body: list, scope: SymbolTable, nonlocal_names: Optional[set] = None,
                             global_names: Optional[set] = None):
        """预扫描函数体，将赋值目标预注册为局部变量。

        确保函数体内的变量在被引用时已经有定义（避免 SEM_UNDEFINED_SYMBOL 误报）。
        预注册即携带声明类型（``_prescan_target_spec``），非 any 占位——
        函数局部变量与模块级/参数路径的声明类型流转一致（统一 Optional 值
        模型 + 重赋值类型检查的编译期前提）。
        nonlocal_names 中的变量名不会被注册为局部变量（它们引用外层作用域）。
        global_names 中的变量名同样不会被注册为局部变量（它们引用模块级作用域）。
        """
        if nonlocal_names is None:
            nonlocal_names = set()
        if global_names is None:
            global_names = set()
        excluded = nonlocal_names | global_names

        for stmt in body:
            if isinstance(stmt, ast.IbAssign):
                for name, target in SymbolExtractor.get_assigned_names(stmt):
                    if name not in scope.symbols and name not in excluded:
                        sym = VariableSymbol(
                            name=name,
                            kind=SymbolKind.VARIABLE,
                            def_node=stmt,
                            spec=self._prescan_target_spec(target),
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
                # for 循环变量（含带注解目标 ``for int x in``）：预注册即携带
                # 声明类型（visit_IbFor 的 ``_register_loop_variable`` 会再次
                # 精化，prescan 保持同语义不退化）。
                for name, target in SymbolExtractor.get_assigned_names(stmt):
                    if name not in scope.symbols and name not in excluded:
                        sym = VariableSymbol(
                            name=name,
                            kind=SymbolKind.VARIABLE,
                            def_node=stmt,
                            spec=self._prescan_target_spec(target),
                        )
                        scope.define(sym)
            # 递归进入嵌套结构（vars() 遍历覆盖 body/orelse 等语句列表；不进入嵌套函数/类定义；
            # 仅递归纯 IbASTNode 列表——behavior 段等混合字符串字段须跳过）
            if not isinstance(stmt, (ast.IbFunctionDef, ast.IbLLMFunctionDef, ast.IbClassDef)):
                for attr in vars(stmt):
                    child = getattr(stmt, attr)
                    if isinstance(child, list) and all(isinstance(i, ast.IbASTNode) for i in child):
                        self._prescan_body_locals(child, scope, nonlocal_names, global_names)

    def _collect_nonlocal_names(self, body: list) -> set:
        """从函数体中收集所有 nonlocal 声明的变量名。

        扫描函数体顶层语句中的 IbNonlocalStmt 节点。
        """
        names = set()
        for stmt in body:
            if isinstance(stmt, ast.IbNonlocalStmt):
                names.update(stmt.names)
        return names

    def _collect_global_names(self, body: list) -> set:
        """从函数体中收集所有 global 声明的变量名。

        扫描函数体顶层语句中的 IbGlobalStmt 节点。
        """
        names = set()
        for stmt in body:
            if isinstance(stmt, ast.IbGlobalStmt):
                names.update(stmt.names)
        return names