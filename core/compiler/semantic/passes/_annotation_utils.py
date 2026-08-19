"""
core/compiler/semantic/passes/_annotation_utils.py

AST 类型注解 → TypeRef 的单一权威转换（跨 pass 复用）。

``_annotation_to_typeref`` 原先内嵌于 ``SymbolCollector``（符号收集期），宿主绑定
（scheduler 构建宿主模块 spec）也需要同一转换，故提取为模块级函数，原调用方委托至此，
消除双真相。
"""

from typing import Callable, Optional

from core.kernel import ast
from core.kernel.spec.type_ref import TypeRef
from ._type_checking_base import module_qualified_annotation
from ._fn_callable import CALLABLE_INTERNAL_TYPE_MSG

ErrorFn = Callable[[str, ast.IbASTNode], None]


def annotation_to_typeref(
    annotation: ast.IbASTNode,
    error_fn: Optional[ErrorFn] = None,
) -> TypeRef:
    """Convert an AST annotation node to a TypeRef (结构化递归).

    ``fn[(args) -> ret]``（CALLABLE_SIG）保留结构化签名形态
    ``TypeRef('fn', (TypeRef('__args__', <params>), <ret>))``，与
    type-check 阶段 ``_param_type_ref`` 的 CALLABLE_SIG 分支同构——消除
    "param_types 与 param_descriptors 双真相"（S2：descriptor 双构造源收敛）。

    ``error_fn`` 可选：当注解使用内部类型名 ``callable`` 时回调（语义 pass
    上报 SEM_UNRESOLVED_TYPE；无回调场景则静默回退 any）。
    """
    if isinstance(annotation, ast.IbName):
        if annotation.id == "callable":
            if error_fn is not None:
                error_fn(CALLABLE_INTERNAL_TYPE_MSG, annotation)
            return TypeRef.of("any")
        return TypeRef.of(annotation.id)
    if isinstance(annotation, ast.IbAttribute):
        module_path, type_name = module_qualified_annotation(annotation)
        if type_name is None:
            return TypeRef.of("any")
        return TypeRef.of(type_name, module=module_path)
    if isinstance(annotation, ast.IbCallableType):
        params = tuple(annotation_to_typeref(pt, error_fn) for pt in annotation.param_types)
        ret = annotation.return_type
        ret_ref = annotation_to_typeref(ret, error_fn) if ret is not None else TypeRef.of("auto")
        return TypeRef(
            "fn",
            (TypeRef("__args__", params), ret_ref),
        )
    if isinstance(annotation, ast.IbSubscript) and isinstance(annotation.value, (ast.IbName, ast.IbAttribute)):
        if isinstance(annotation.value, ast.IbName):
            if annotation.value.id == "callable":
                if error_fn is not None:
                    error_fn(CALLABLE_INTERNAL_TYPE_MSG, annotation)
                return TypeRef.of("any")
            args = [
                annotation_to_typeref(elt, error_fn)
                for elt in annotation.slice.elts
            ] if isinstance(annotation.slice, ast.IbTuple) else [
                annotation_to_typeref(annotation.slice, error_fn)
            ]
            return TypeRef(annotation.value.id, tuple(args))
        module_path, type_name = module_qualified_annotation(annotation.value)
        if type_name is None:
            return TypeRef.of("any")
        if isinstance(annotation.slice, ast.IbTuple):
            args = [annotation_to_typeref(elt, error_fn) for elt in annotation.slice.elts]
        else:
            args = [annotation_to_typeref(annotation.slice, error_fn)]
        return TypeRef(type_name, tuple(args), module=module_path)
    return TypeRef.of("any")
