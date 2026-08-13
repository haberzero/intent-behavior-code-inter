"""
TypeRef Resolution Pass (SymbolPhase sub-step 3)

职责：将符号表中残留的 TypeRef spec 解析为具体 IbSpec。
输入：populated symbol_table（所有类/函数已注册）
输出：所有 Symbol.spec 均为 IbSpec（或报错后降级为 any）

前置条件：SymbolCollectionPass 已完成全部定义收集，
所有同模块类型已注册到 SpecRegistry。循环导入已禁止，
跨模块类型亦已注册。因此 resolve() 失败即为真正的未知类型错误。
"""

from typing import Any, List, Optional

from core.base.diagnostics.codes import SEM_UNRESOLVED_TYPE
from core.kernel.symbols import SymbolTable
from core.kernel.spec.type_ref import TypeRef

from ..result import PassResult, PassOutput, Diagnostic, DiagnosticLevel
from ..context import SemanticContext
from .base_pass import BasePass


class TypeRefResolutionPass(BasePass):

    def __init__(self):
        super().__init__("TypeRefResolutionPass")

    def run(self, context: SemanticContext) -> PassResult:
        registry = context.registry
        root_table = context.symbol_table.current
        any_spec = registry.resolve("any")
        diagnostics: List[Diagnostic] = []

        self._resolve_table(root_table, registry, any_spec, diagnostics)

        output = PassOutput(
            diagnostics=diagnostics,
            success=not any(d.level == DiagnosticLevel.ERROR for d in diagnostics),
        )
        return PassResult.ok(context, output=output)

    def _resolve_table(self, table: SymbolTable, registry, any_spec, diagnostics: List[Diagnostic],
                       class_type_params: Optional[List[str]] = None):
        # 若本表是类作用域（含 type_params 参数符号），类型参数名作占位保留，
        # 不报"未知类型"——特化时替换为实参。
        table_type_params = class_type_params
        for name, sym in table.symbols.items():
            if isinstance(sym.spec, TypeRef):
                if table_type_params and sym.spec.head in table_type_params:
                    sym.spec = self._type_param_spec(sym.spec.head)
                    continue
                resolved = registry.resolve_typeref(sym.spec)
                if resolved:
                    sym.spec = resolved
                else:
                    diagnostics.append(Diagnostic(
                        level=DiagnosticLevel.ERROR,
                        message=f"Unknown type '{sym.spec.head}' in declaration of '{name}'",
                        code=SEM_UNRESOLVED_TYPE,
                    ))
                    sym.spec = any_spec

            owned = getattr(sym, 'owned_scope', None)
            if owned is not None:
                # 类符号的 owned_scope = 类作用域：携带该类 type_params 递归，
                # 使类体内 T 解析为类型参数占位而非报"未知类型"。
                child_type_params = None
                cls_type_params = getattr(sym.spec, "type_params", None)
                if cls_type_params:
                    child_type_params = list(cls_type_params)
                self._resolve_table(owned, registry, any_spec, diagnostics, child_type_params)

    @staticmethod
    def _type_param_spec(name: str) -> Any:
        """构造类型参数占位 spec（与 SpecFactory.create_type_param 同构）。"""
        from core.base.enums import Provenance, Visibility
        from core.kernel.spec.base import TypeKind, TypeDef
        return TypeDef(
            name=name,
            kind=TypeKind.TYPE_PARAM.value,
            provenance=Provenance.USER_DEFINED,
            visibility=Visibility.IMPORT_GATED,
        )
