"""
Type Checking Pass (TypePhase sub-step 2)

职责：类型检查和推断
输入：Context with resolved symbols
输出：PassOutput with type_bindings

Implementation note: ``TypeCheckingVisitor`` is composed from four mixin
classes via multiple inheritance. The ~40 ``visit_*`` methods are split
across the mixin modules below; this file holds only the ``__init__``
that sets up the shared-state protocol relied on by every mixin.

See ``_type_checking_base.py`` for the shared-state protocol documentation.
"""

from typing import Optional, List, Dict, Any

from core.kernel.spec import IbSpec

from ..result import PassResult, PassOutput
from ..context import SemanticContext
from .base_pass import BasePass
from .scoped_visitor import ScopedVisitor
from ._type_checking_base import TypeCheckBase
from ._declaration_visitors import DeclarationVisitorsMixin
from ._statement_visitors import StatementVisitorsMixin
from ._expression_visitors import ExpressionVisitorsMixin
from ._overlay_registry import _OverlayRegistry


class TypeCheckingPass(BasePass):
    """类型检查 Pass（TypePhase sub-step 2）

    简化的类型检查和推断：
    - 一次性推断（不需要约束求解）
    - auto 变量类型推断
    - -> auto 函数返回类型推断
    - 类型兼容性检查 (SEM_TYPE_MISMATCH)
    """

    def __init__(self):
        super().__init__("TypeCheckingPass")

    def run(self, context: SemanticContext) -> PassResult:
        visitor = TypeCheckingVisitor(context)
        visitor.visit(context.ast)

        output = PassOutput(
            type_bindings=dict(visitor.type_bindings),
            diagnostics=visitor.diagnostics,
            success=True,
        )
        return PassResult.ok(context, output=output)


class TypeCheckingVisitor(
    DeclarationVisitorsMixin,
    StatementVisitorsMixin,
    ExpressionVisitorsMixin,
    TypeCheckBase,
    ScopedVisitor,
):
    """类型检查访问者

    Composed from mixins:
    - ``TypeCheckBase``: dispatch / diagnostics / type-resolution helpers
      (overrides ScopedVisitor's ``visit`` / ``error`` / ``warn``).
    - ``DeclarationVisitorsMixin``: class / function / LLM-function visitors.
    - ``StatementVisitorsMixin``: assignment, control-flow, simple-stmt visitors.
    - ``ExpressionVisitorsMixin``: literal / operator / call / access / HOF visitors.

    MRO places ``TypeCheckBase`` before ``ScopedVisitor`` so its ``visit`` /
    ``error`` / ``warn`` overrides (with the ``hint`` parameter and typed
    return values) take precedence over ScopedVisitor's plainer versions.
    """

    def __init__(self, context: SemanticContext):
        super().__init__(context)

        # 类型绑定：node object -> IbSpec（使用对象身份作为键）
        self.type_bindings: Dict[Any, IbSpec] = {}

        # 覆层声明登记：type_name -> 已声明覆层方法名集合。
        # 供 with overlay 目标校验（须存在对应覆层声明）与"存在未启用"告警
        # （模块内声明了覆层但从未被 with overlay 引用）。
        self._overlay_registry = _OverlayRegistry()

        # auto 返回类型累积（用于 -> auto 函数）
        self.auto_return_types: Optional[List[IbSpec]] = None

        # 当前函数返回类型栈（供 visit_IbReturn 绑定返回字面量特化类型）。
        # 函数定义处 push、退出 pop（与 in_function_def 同生命周期）。
        self.func_return_types: list = []

        # 状态标志
        self.in_function_def = False
        self.in_class_def = False
        self.current_class: Optional[IbSpec] = None
        self.current_function_type_params: Optional[List[str]] = None
        self.current_function_type_param_bounds: Dict[str, str] = {}

        # 常用类型描述符
        self._any_desc = self.registry.resolve("any")
        if self._any_desc is None:
            raise RuntimeError("Internal: registry has no 'any' primitive; type checking cannot proceed.")
        self._void_desc = self.registry.resolve("void")
        self._behavior_desc = self.registry.resolve("behavior")
        self._int_desc = self.registry.resolve("int")
        self._float_desc = self.registry.resolve("float")
        self._str_desc = self.registry.resolve("str")
        self._bool_desc = self.registry.resolve("bool")
        self._none_desc = self.registry.resolve("None")
