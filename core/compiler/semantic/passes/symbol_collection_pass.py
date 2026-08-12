"""
Symbol Collection Pass (SymbolPhase sub-step 1)

职责：收集所有符号定义（类、函数、全局变量）
输入：AST
输出：populated symbol_table（通过 SymbolTable 原地定义）
"""

from typing import Optional, List, Tuple

from core.base.diagnostics.codes import SEM_REDEFINITION, SEM_UNCATEGORIZED
from core.base.enums import Provenance, Visibility
from core.kernel import ast
from core.kernel.symbols import Symbol, SymbolTable, TypeSymbol, FunctionSymbol, VariableSymbol, SymbolKind
from core.kernel.spec import IbSpec
from core.kernel.spec.type_ref import TypeRef
from core.kernel.spec.member import MethodMemberSpec, MemberSpec

from ..result import PassResult, Diagnostic, DiagnosticLevel
from ..context import SemanticContext
from .base_pass import BasePass


class SymbolExtractor:
    """符号提取器：从 AST 节点中提取定义的符号名"""

    @staticmethod
    def get_assigned_names(node: ast.IbASTNode) -> List[Tuple[str, ast.IbASTNode]]:
        """提取赋值或迭代语句中的目标名称及对应的节点"""
        results = []

        def _extract(target: ast.IbASTNode):
            if isinstance(target, ast.IbName):
                results.append((target.id, target))
            elif isinstance(target, ast.IbTypeAnnotatedExpr):
                results.append((target.target.id, target))
                _extract(target.target)
            elif isinstance(target, ast.IbTuple):
                for el in target.elts:
                    _extract(el)

        if isinstance(node, ast.IbAssign):
            for target in node.targets:
                _extract(target)
        elif isinstance(node, ast.IbFor):
            if node.target:
                _extract(node.target)
        elif isinstance(node, ast.IbExceptHandler):
            if node.name:
                results.append((node.name, node))

        return results


class SymbolCollectionPass(BasePass):
    """符号收集 Pass（SymbolPhase sub-step 1）

    收集顶层符号：
    - 类定义（IbClassDef）
    - 函数定义（IbFunctionDef, IbLLMFunctionDef）
    - 全局变量（IbAssign with type annotation）
    """

    def __init__(self):
        super().__init__("SymbolCollectionPass")

    def run(self, context: SemanticContext) -> PassResult:
        visitor = SymbolCollector(context)
        visitor.visit(context.ast)
        return PassResult.ok(context, diagnostics=visitor.diagnostics)


class SymbolCollector:
    """符号收集访问者"""

    def __init__(self, context: SemanticContext):
        self.context = context
        self.symbol_table = context.symbol_table.current
        self.registry = context.registry
        self.diagnostics: List[Diagnostic] = []

        # 状态变量
        self.current_class: Optional[IbSpec] = None
        # 当前类是否为枚举（继承 Enum）：枚举成员字面值写入 MemberSpec.metadata["value"]，
        # 供 EnumAxiom.from_prompt 做"成员名 → 成员值"映射（非 str 枚举 LLM 集成）。
        self.current_class_is_enum: bool = False

        # 使用 registry 的 _any_desc
        self._any_desc = context.registry.resolve("any")
        if self._any_desc is None:
            raise RuntimeError("Internal: registry has no 'any' primitive; symbol collection cannot proceed.")

    def visit(self, node: ast.IbASTNode):
        """访问节点的分派方法"""
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

    def error(self, message: str, node: ast.IbASTNode, code: str = SEM_UNCATEGORIZED):
        """记录错误诊断"""
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.ERROR,
            message=message,
            code=code
        ))

    def _define(self, sym: Symbol, node: ast.IbASTNode):
        """定义符号到符号表"""
        try:
            self.symbol_table.define(sym)

            # 如果在类作用域内，同步到类的成员表
            if self.current_class:
                if sym.kind in (SymbolKind.FUNCTION, SymbolKind.LLM_FUNCTION):
                    llm_kind = "llm_method" if sym.kind == SymbolKind.LLM_FUNCTION else "method"
                    # Store full method signature in members
                    method_spec = MethodMemberSpec(
                        name=sym.name,
                        kind=llm_kind,
                        type_ref=TypeRef.of(sym.spec.name if sym.spec else "any")
                    )
                    # Copy signature from TypeDef (FunctionSymbol.spec is always TypeDef)
                    if sym.spec:
                        method_spec.param_types = list(sym.spec.param_types)
                        method_spec.return_type = sym.spec.return_type
                    self.current_class.members[sym.name] = method_spec
                else:
                    spec_name = "any"
                    if sym.spec:
                        spec_name = sym.spec.head if isinstance(sym.spec, TypeRef) else sym.spec.name
                    self.current_class.members[sym.name] = MemberSpec(
                        name=sym.name,
                        kind="field",
                        type_ref=TypeRef.of(spec_name)
                    )

        except ValueError as e:
            self.error(str(e), node, code=SEM_REDEFINITION)

    def visit_IbModule(self, node: ast.IbModule):
        """访问模块节点"""
        for stmt in node.body:
            self.visit(stmt)

    def visit_IbClassDef(self, node: ast.IbClassDef):
        """访问类定义节点"""
        # 1. 创建类元数据
        # 所有用户类隐式继承 Object（与运行时 artifact_loader 的默认行为对齐）。
        # Object 自身不设置父类以避免循环。
        effective_parent = node.parent if node.parent else ("Object" if node.name != "Object" else None)
        cls_meta = self.registry.factory.create_class(
            name=node.name,
            parent_name=effective_parent,
            provenance=Provenance.USER_DEFINED,
            visibility=Visibility.IMPORT_GATED,
        )

        # Enum Hook: 如果继承 Enum，设置 axiom_name
        if node.parent == "Enum":
            cls_meta._axiom_name = "enum"

        # 注册到 registry
        registered_meta = self.registry.register(cls_meta)

        # 2. 创建类符号
        sym = TypeSymbol(
            name=node.name,
            kind=SymbolKind.CLASS,
            def_node=node,
            spec=registered_meta
        )
        self._define(sym, node)

        # 3. 进入类作用域收集成员
        old_table = self.symbol_table
        self.symbol_table = SymbolTable(parent=old_table, name=node.name)

        old_class = self.current_class
        self.current_class = registered_meta

        old_is_enum = self.current_class_is_enum
        self.current_class_is_enum = node.parent == "Enum"

        try:
            for stmt in node.body:
                self.visit(stmt)
            # 记录类作用域
            sym.owned_scope = self.symbol_table
        finally:
            self.current_class = old_class
            self.current_class_is_enum = old_is_enum
            self.symbol_table = old_table

    def visit_IbFunctionDef(self, node: ast.IbFunctionDef):
        """访问函数定义节点"""
        # 创建函数元数据（暂定为 Any -> Any）
        func_meta = self.registry.factory.create_func(
            name=node.name,
            param_type_names=[],
            return_type_name="any",
            provenance=Provenance.USER_DEFINED,
            visibility=Visibility.IMPORT_GATED,
        )

        # Extract parameter types and return type from AST and store in spec
        param_type_refs = []
        for arg in node.args:
            # All args are now IbArg with optional annotation field
            if arg.annotation:
                param_type_refs.append(self._annotation_to_typeref(arg.annotation))
            else:
                param_type_refs.append(TypeRef.of("any"))

        if param_type_refs:
            func_meta.param_types = param_type_refs

        if node.returns:
            func_meta.return_type = self._annotation_to_typeref(node.returns)

        self.registry.register(func_meta)

        # 创建函数符号
        sym = FunctionSymbol(
            name=node.name,
            kind=SymbolKind.FUNCTION,
            def_node=node,
            spec=func_meta
        )
        self._define(sym, node)

    def visit_IbLLMFunctionDef(self, node: ast.IbLLMFunctionDef):
        """访问 LLM 函数定义节点"""
        # 创建函数元数据
        func_meta = self.registry.factory.create_func(
            name=node.name,
            param_type_names=[],
            return_type_name="any",
            provenance=Provenance.USER_DEFINED,
            visibility=Visibility.IMPORT_GATED,
        )
        self.registry.register(func_meta)

        # 创建 LLM 函数符号
        sym = FunctionSymbol(
            name=node.name,
            kind=SymbolKind.LLM_FUNCTION,
            def_node=node,
            spec=func_meta
        )
        self._define(sym, node)

    def visit_IbAssign(self, node: ast.IbAssign):
        """访问赋值节点（收集全局/类成员变量）"""
        for name, target in SymbolExtractor.get_assigned_names(node):
            # 避免重复定义
            if name not in self.symbol_table.symbols:
                # 尝试从类型标注解析 spec
                spec = None
                if isinstance(target, ast.IbTypeAnnotatedExpr) and target.annotation:
                    resolved = self._resolve_annotation(target.annotation)
                    if resolved:
                        spec = resolved
                    else:
                        spec = self._annotation_to_typeref(target.annotation)
                if spec is None:
                    # 裸赋值（无标注）：以 auto 语义占位——类型检查阶段从首次
                    # 赋值推断并锁定实际类型（不再静默退化为动态 any）。
                    spec = self.registry.resolve("auto")
                sym = VariableSymbol(
                    name=name,
                    kind=SymbolKind.VARIABLE,
                    def_node=node,
                    spec=spec
                )
                self._define(sym, target)
                # 枚举成员字面值 → MemberSpec.metadata["value"]（供 EnumAxiom 映射成员名→值）。
                # 仅限常量字面量（int/float/bool/str）；非字面量成员回退"名==值"语义。
                if self.current_class_is_enum and isinstance(node.value, ast.IbConstant):
                    literal = node.value.value
                    if isinstance(literal, (bool, int, float, str)):
                        member = self.current_class.members.get(name)
                        if member is not None and member.kind == "field":
                            member.metadata["value"] = literal

        # 递归扫描（处理嵌套结构）
        self.generic_visit(node)

    def _resolve_annotation(self, annotation: ast.IbASTNode) -> Optional[IbSpec]:
        """Resolve a type annotation to an IbSpec (best-effort at collection time).

        支持泛型注解：``list[int]`` / ``dict[str,int]`` / ``Optional[int]``
        等经 ``resolve_specialization`` 解析为特化 spec——符号 declared_type 保留
        泛型身份（此前只处理 ``IbName``，泛型注解退化为 any/基础类型，运行时
        内省/序列化丢泛型参数）。
        """
        if isinstance(annotation, ast.IbName):
            return self.registry.resolve(annotation.id)
        if isinstance(annotation, ast.IbSubscript):
            if isinstance(annotation.value, ast.IbName):
                base = self.registry.resolve(annotation.value.id)
                if base is None:
                    return None
                if isinstance(annotation.slice, ast.IbTuple):
                    arg_specs = [self._resolve_annotation(elt) for elt in annotation.slice.elts]
                else:
                    arg_specs = [self._resolve_annotation(annotation.slice)]
                arg_specs = [s for s in arg_specs if s is not None]
                if not arg_specs:
                    return base
                return self.registry.resolve_specialization(base, arg_specs)
            return None
        return None

    def _annotation_to_typeref(self, annotation: ast.IbASTNode) -> TypeRef:
        """Convert an AST annotation node to a TypeRef."""
        if isinstance(annotation, ast.IbName):
            return TypeRef.of(annotation.id)
        return TypeRef.of("any")

    def visit_IbTypeAnnotatedExpr(self, node: ast.IbTypeAnnotatedExpr):
        """访问带类型标注的表达式"""
        self.visit(node.target)

    def visit_IbFilteredExpr(self, node: ast.IbFilteredExpr):
        """访问带过滤条件的表达式"""
        self.visit(node.expr)
        self.visit(node.filter)
