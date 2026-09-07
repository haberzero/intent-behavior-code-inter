"""
Symbol Collection Pass (SymbolPhase sub-step 1)

职责：收集所有符号定义（类、函数、全局变量）
输入：AST
输出：populated symbol_table（通过 SymbolTable 原地定义）
"""

from typing import Optional, List, Tuple

from core.base.diagnostics.codes import SEM_REDEFINITION, SEM_TYPE_MISMATCH, SEM_UNCATEGORIZED, SEM_UNRESOLVED_TYPE
from ._fn_callable import CALLABLE_INTERNAL_TYPE_MSG
from core.base.enums import Provenance, Visibility
from core.kernel import ast
from core.kernel.symbols import Symbol, SymbolTable, TypeSymbol, FunctionSymbol, VariableSymbol, SymbolKind
from core.kernel.spec import IbSpec
from core.kernel.spec.type_ref import TypeRef
from core.kernel.spec.member import MethodMemberSpec, MemberSpec

from ..result import PassResult, Diagnostic, DiagnosticLevel
from ..context import SemanticContext
from .base_pass import BasePass
from ._type_checking_base import module_qualified_annotation
from ._annotation_utils import annotation_to_typeref


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
    - 函数定义（IbFunctionDef）
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
        """记录错误诊断（位置取节点解析期附着的 loc，单一权威源）"""
        self.diagnostics.append(Diagnostic(
            level=DiagnosticLevel.ERROR,
            message=message,
            code=code,
            line=node.lineno or None,
            column=node.col_offset or None,
        ))

    def _define(self, sym: Symbol, node: ast.IbASTNode):
        """定义符号到符号表"""
        try:
            self.symbol_table.define(sym)

            # 如果在类作用域内，同步到类的成员表
            if self.current_class:
                if sym.kind == SymbolKind.FUNCTION:
                    # Store full method signature in members
                    method_spec = MethodMemberSpec(
                        name=sym.name,
                        kind="method",
                        type_ref=TypeRef.of(sym.spec.name if sym.spec else "any")
                    )
                    # Copy signature from TypeDef (FunctionSymbol.spec is always TypeDef)
                    if sym.spec:
                        method_spec.param_types = list(sym.spec.param_types)
                        method_spec.return_type = sym.spec.return_type
                    self.current_class.members[sym.name] = method_spec
                elif sym.kind == SymbolKind.TYPE_PARAM:
                    # 类型参数符号不落类成员表（成员表只放字段/方法）。
                    pass
                else:
                    # 字段类型：优先结构化 TypeRef（保留 list[T] 等泛型实参，
                    # 供特化替换）；退化 fallback 用扁平名。
                    if isinstance(sym.spec, TypeRef):
                        field_type_ref = sym.spec
                    elif sym.spec is not None:
                        field_type_ref = TypeRef.from_spec(sym.spec)
                    else:
                        field_type_ref = TypeRef.of("any")
                    self.current_class.members[sym.name] = MemberSpec(
                        name=sym.name,
                        kind="field",
                        type_ref=field_type_ref
                    )

        except ValueError as e:
            self.error(str(e), node, code=SEM_REDEFINITION)

    def visit_IbProtocolDef(self, node: ast.IbProtocolDef):
        """访问协议定义节点。

        协议在编译期注册为 PROTOCOL-kind TypeDef，并将其方法签名收集到
        members 中。随后通过 ProtocolRegistry.register_from_spec 登记为
        内核协议，使后续 satisfies_protocol 可以识别它。
        """
        proto_spec = self.registry.factory.create_protocol(
            name=node.name,
            module=self.context.module_name,
            provenance=Provenance.USER_DEFINED,
            visibility=Visibility.IMPORT_GATED,
        )
        if node.parent:
            proto_spec.parent_type = TypeRef.of(node.parent)
        proto_spec.type_params = list(node.type_params)

        registered = self.registry.register(proto_spec)

        sym = Symbol(
            name=node.name,
            kind=SymbolKind.PROTOCOL,
            def_node=node,
            spec=registered,
        )
        self._define(sym, node)

        old_table = self.symbol_table
        self.symbol_table = SymbolTable(parent=old_table, name=node.name)
        old_class = self.current_class
        self.current_class = registered
        try:
            for stmt in node.body:
                self.visit(stmt)
        finally:
            self.current_class = old_class
            self.symbol_table = old_table

        # 登记到协议注册表（成员表已由方法访问填充）。
        self.registry.protocols.register_from_spec(registered)

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
        # callable 内部类型名守卫（方向 A）：`class X(callable)` 基类继承位置
        # 亦不可使用内部类型名（callable 非 CLASS kind，本就不能作为基类）。
        if effective_parent == "callable":
            self.error(
                CALLABLE_INTERNAL_TYPE_MSG,
                node, code=SEM_UNRESOLVED_TYPE,
            )
        # 用户类身份统一 (module_path, name)：所有模块（含入口）带 module 限定
        # （S2 类身份统一——入口模块类不再裸名，与被 import 模块类对称，
        # geo.Box / graph.Box / main.Box 各自独立）。
        class_module = self.context.module_name
        # 父引用 module（类身份统一 S2）：非泛型父（class Dog(Animal)）的
        # parent_type 亦须带 module——否则运行时 resolve_typeref(parent_type)
        # 裸名解析 miss（入口父已 qualified），is_assignable 继承链断裂。
        # 内置父（Object/list 等）module_path=None，parent_module=None 不加前缀。
        parent_module = None
        if self.registry is not None and effective_parent:
            parent_spec = self.registry.resolve(effective_parent)
            if parent_spec is not None:
                parent_module = parent_spec.module_path
        cls_meta = self.registry.factory.create_class(
            name=node.name,
            module=class_module,
            parent_name=effective_parent,
            parent_module=parent_module,
            provenance=Provenance.USER_DEFINED,
            visibility=Visibility.IMPORT_GATED,
        )
        cls_meta.type_params = list(node.type_params)
        cls_meta.type_param_bounds = dict(node.type_param_bounds)
        cls_meta.implements = list(node.implements)
        cls_meta.implements_args = {
            k: list(v) for k, v in node.implements_args.items()
        }
        # 父类泛型实参（class Sub[T](Box[T])）：parent_type 构造为泛型引用
        # TypeRef(Box, (T,))，供特化时递归替换。
        if node.parent_args:
            parent_head = effective_parent or "Object"
            # [Module Identity] 父引用带 module：同模块父经
            # SpecRegistry.current_module 上下文解析出 module_path，运行期父链
            # 据此对齐 qualified 键（geo.Sub[int] 的父 = "geo.Box[int]"）。
            # 父类尚未注册（前向引用）时 module 缺省，运行期以子类 module 补全。
            parent_module = None
            if self.registry is not None:
                parent_spec = self.registry.resolve(parent_head)
                if parent_spec is not None:
                    parent_module = parent_spec.module_path
            cls_meta.parent_type = TypeRef.generic(
                parent_head,
                *[TypeRef.of(a) for a in node.parent_args],
                module=parent_module,
            )
            # 首版边界：非泛型子类继承具体特化（class Sub(Box[int])）不支持——
            # 子类无 type_params 却继承带实参父类，特化参数无传递来源，fail-fast。
            if not node.type_params:
                self.error(
                    f"Class '{node.name}' inherits a specialized generic parent "
                    f"'{parent_head}[...]' without declaring type parameters "
                    f"(e.g. class {node.name}[T]({parent_head}[T])).",
                    node, code=SEM_UNCATEGORIZED,
                )

        # Enum Hook: 如果继承 Enum，设置 axiom_name
        if node.parent == "Enum":
            cls_meta._axiom_name = "enum"
            # Enum 值模型不支持类型参数（成员=底层值非实例，泛型实例化冲突）。
            if node.type_params:
                self.error(
                    f"Enum class '{node.name}' does not support type parameters.",
                    node, code=SEM_UNCATEGORIZED,
                )

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
            # 注册泛型类型参数符号（class Box[T] 的 T）——类体内 T 作类型占位
            # 解析，不落类成员表。显式优于隐式：参数名与类内已有成员同名冲突
            # 时 fail-fast（语义错误）。
            for tp_name in node.type_params:
                if tp_name in self.symbol_table.symbols:
                    self.error(
                        f"Type parameter '{tp_name}' conflicts with existing member name in class '{node.name}'.",
                        node, code=SEM_UNCATEGORIZED,
                    )
                    continue
                # 类型参数名不得遮蔽内置/已注册类型（class Box[int] 非法）：
                # 特化时实参名与参数名同构会歧义。
                if self.registry.resolve(tp_name) is not None:
                    self.error(
                        f"Type parameter '{tp_name}' shadows existing type "
                        f"'{tp_name}'. Choose a different name.",
                        node, code=SEM_UNCATEGORIZED,
                    )
                    continue
                tp_spec = self.registry.factory.create_type_param(tp_name)
                self._define(
                    TypeSymbol(
                        name=tp_name,
                        kind=SymbolKind.TYPE_PARAM,
                        def_node=node,
                        spec=tp_spec,
                    ),
                    node,
                )
            for stmt in node.body:
                self.visit(stmt)
            # 记录类作用域
            sym.owned_scope = self.symbol_table
        finally:
            self.current_class = old_class
            self.current_class_is_enum = old_is_enum
            self.symbol_table = old_table

    def visit_IbImplDef(self, node: ast.IbImplDef):
        """访问 retroactive implementation 块：进入目标类成员上下文收集方法。

        方法符号定义进目标类 owned_scope、成员同步进目标类 members
        （与 visit_IbClassDef 同构）。与类自身成员同名的方法跳过定义
        （冲突由类型检查阶段报单一明确错误）。

        覆层变体（node.is_overlay）：方法符号仍进目标类 owned_scope
        （供类型检查访问方法体），但**不**同步进 target spec.members / 不登记
        implements——覆层不改写类型协议满足判定，仅登记运行时影子条目
        （协议方法表），语义由声明访客 + 运行时水化承接。
        """
        if not node.body:
            return
        sym = self.symbol_table.resolve(node.type_name)
        if sym is None or sym.kind != SymbolKind.CLASS:
            return  # 目标解析错误由类型检查阶段报
        target_spec = sym.spec
        if target_spec is None:
            return
        is_kernel_native = getattr(target_spec, "provenance", None) == Provenance.KERNEL_NATIVE
        owned_scope = getattr(sym, "owned_scope", None)
        if owned_scope is None:
            if not is_kernel_native:
                return
            # 内置类型无 AST 类作用域：合成 owned_scope（与宿主类注入同构——
            # 无 AST 作用域的类在符号定义处合成，scheduler._inject_host_class
            # 模式），impl 方法符号据此收集。
            owned_scope = SymbolTable(parent=self.symbol_table, name=node.type_name)
            sym.owned_scope = owned_scope

        # 冲突面（目标类型既有方法，单一判定集）——**仅普通 impl**：
        # - target_spec.members：类体成员 + 先前 impl 补充 + 公理方法声明
        # - 内置类型另有公理声明的运算符（__add__ 等）：运行期自动绑定
        # 覆层不参与冲突判定（覆层是影子条目，专为改写内置协议方法分派，
        # 覆写原生方法是其语义本意）。
        conflict_names: set = set()
        if not node.is_overlay:
            conflict_names.update(target_spec.members)
            if is_kernel_native:
                axiom = self.registry.get_axiom(target_spec)
                if axiom is not None:
                    conflict_names.update(axiom.get_operators().values())

        old_table = self.symbol_table
        old_class = self.current_class
        old_is_enum = self.current_class_is_enum
        self.symbol_table = owned_scope
        self.current_class = target_spec
        self.current_class_is_enum = False
        try:
            for stmt in node.body:
                # body 语句类型由 parser 保证（func / llm func）
                if not node.is_overlay and is_kernel_native and stmt.name == "__init__":
                    # 内置类型构造走 boxer/__call__ 原生路径，永不分派 impl
                    # 补充的构造器——收集即半接通（注册了从不执行），fail-fast。
                    self.error(
                        f"impl on built-in type '{node.type_name}' cannot define "
                        "'__init__': built-in construction never dispatches to "
                        "impl-supplied constructors.",
                        stmt, code=SEM_TYPE_MISMATCH,
                    )
                    continue
                if (
                    not node.is_overlay
                    and is_kernel_native
                    and stmt.name in ("__from_prompt__", "__validate_prompt__")
                ):
                    # 内置类型 LLM 输出解析走 AxiomParsingStrategy（from_prompt_cap/
                    # 内建解析器，单一权威），永不分派 impl 补充的解析协议方法——
                    # 收集即半接通（声明即"满足协议"但从不执行），fail-fast。
                    # （同 __init__ 先例；P5 已定内置预校验由内建解析器承担）
                    self.error(
                        f"impl on built-in type '{node.type_name}' cannot define "
                        f"'{stmt.name}': built-in LLM output parsing never dispatches "
                        "impl-supplied prompt-protocol methods.",
                        stmt, code=SEM_TYPE_MISMATCH,
                    )
                    continue
                if not node.is_overlay and (stmt.name in self.symbol_table.symbols or stmt.name in conflict_names):
                    # 与类自身（或先前 impl / 宿主 bind 声明 / 内置公理方法面）
                    # 已定义成员冲突：fail-fast，跳过定义（类型检查阶段不再重复报）
                    self.error(
                        f"impl method '{stmt.name}' conflicts with an existing "
                        f"member of class '{node.type_name}'.",
                        stmt, code=SEM_REDEFINITION,
                    )
                    continue
                self.visit(stmt)
        finally:
            self.symbol_table = old_table
            self.current_class = old_class
            self.current_class_is_enum = old_is_enum

    def visit_IbFunctionDef(self, node: ast.IbFunctionDef):
        """访问函数定义节点（参数/返回注解解析、spec 构造、符号定义）。"""
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

        func_meta.type_params = list(node.type_params)
        func_meta.type_param_bounds = dict(node.type_param_bounds)

        self.registry.register(func_meta)

        # 创建函数符号
        sym = FunctionSymbol(
            name=node.name,
            kind=SymbolKind.FUNCTION,
            def_node=node,
            spec=func_meta
        )
        self._define(sym, node)

    def visit_IbAssign(self, node: ast.IbAssign):
        """访问赋值节点（收集全局/类成员变量）"""
        for name, target in SymbolExtractor.get_assigned_names(node):
            # 字段与类型参数同名冲突（类作用域内）→ fail-fast：类型参数是
            # 类级占位名，字段遮蔽它会造成特化替换歧义。
            if (self.current_class is not None
                    and name in (getattr(self.current_class, "type_params", None) or [])):
                self.error(
                    f"Field '{name}' conflicts with type parameter of class '{self.current_class.name}'.",
                    node, code=SEM_UNCATEGORIZED,
                )
                continue
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
                # 仅限枚举类体内的常量字面量（含一元负号字面量 -1/-1.5）；非字面量
                # 表达式成员回退"名==值"。
                literal = self._extract_literal_value(node.value)
                if self.current_class_is_enum and literal is not None:
                    member = self.current_class.members.get(name)
                    if member is not None and member.kind == "field":
                        member.metadata["value"] = literal

        # 递归扫描（处理嵌套结构）
        self.generic_visit(node)

    def _extract_literal_value(self, node: ast.IbASTNode):
        """提取赋值右侧的常量字面值（int/float/bool/str，含一元负号）。

        供枚举成员 metadata["value"] 使用；非字面量表达式（变量引用/运算等）返回
        None，调用方回退"名==值"语义。一元负号字面量（``-1``/``-1.5``）解析为
        ``IbUnaryOp``，折叠回负数字面量，避免与"名==值"回退静默分歧。
        """
        if isinstance(node, ast.IbConstant):
            return node.value if isinstance(node.value, (bool, int, float, str)) else None
        if (
            isinstance(node, ast.IbUnaryOp)
            and node.op == "-"
            and isinstance(node.operand, ast.IbConstant)
            and isinstance(node.operand.value, (int, float))
        ):
            return -node.operand.value
        return None

    def _resolve_annotation(self, annotation: ast.IbASTNode) -> Optional[IbSpec]:
        """Resolve a type annotation to an IbSpec (best-effort at collection time).

        支持泛型注解：``list[int]`` / ``dict[str,int]`` / ``Optional[int]``
        等经 ``resolve_specialization`` 解析为特化 spec——符号 declared_type 保留
        泛型身份（只处理 ``IbName`` 时泛型注解退化为 any/基础类型，运行时内省/
        序列化丢泛型参数）。用户类泛型内层（``list[T]``）经类型参数
        符号解析为占位 spec（T），特化时替换。
        """
        if isinstance(annotation, ast.IbName):
            tp = self._lookup_type_param(annotation.id)
            if tp is not None:
                return tp
            return self.registry.resolve(annotation.id)
        if isinstance(annotation, ast.IbAttribute):
            # 模块限定类型注解：geo.Counter / subpkg.util.Counter
            module_path, type_name = module_qualified_annotation(annotation)
            if type_name is None:
                return None
            return self.registry.resolve(type_name, module=module_path)
        if isinstance(annotation, ast.IbSubscript):
            if isinstance(annotation.value, (ast.IbName, ast.IbAttribute)):
                if isinstance(annotation.value, ast.IbName):
                    base = self.registry.resolve(annotation.value.id)
                else:
                    module_path, type_name = module_qualified_annotation(annotation.value)
                    base = self.registry.resolve(type_name, module=module_path) if type_name else None
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
    def _lookup_type_param(self, name: str) -> Optional[IbSpec]:
        """在类作用域内查找用户类泛型类型参数（class Box[T] 的 T）。

        命中返回占位 spec（TYPE_PARAM kind）；未命中返回 None。
        """
        if self.current_class is not None:
            tps = getattr(self.current_class, "type_params", None) or []
            if name in tps:
                return self.registry.factory.create_type_param(name)
        return None

    def _annotation_to_typeref(self, annotation: ast.IbASTNode) -> TypeRef:
        """委托至模块级单一权威转换（_annotation_utils.annotation_to_typeref）。"""
        return annotation_to_typeref(annotation, self.error)

    def visit_IbTypeAnnotatedExpr(self, node: ast.IbTypeAnnotatedExpr):
        """访问带类型标注的表达式"""
        self.visit(node.target)

    def visit_IbFilteredExpr(self, node: ast.IbFilteredExpr):
        """访问带过滤条件的表达式"""
        self.visit(node.expr)
        self.visit(node.filter)
