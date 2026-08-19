"""
core/compiler/semantic/passes/_fn_callable.py

fn 可调用性判定共享 helper（方向 A：fn 是用户面唯一的"可调用"抽象）。

``registry.is_callable(CLASS)`` 恒真（get_call_cap 对 CLASS 返回 truthy 标记、
不查 __call__）——直接用它会把"无 __call__ 的类实例"漏检为可调用（整改）。
fn 参数/返回的"强制可调用"检查须与 fn 声明（``_infer_fn_type``）语义对齐：
CLASS 须定义 ``__call__`` 或是类名构造器引用（``fn f = Dog``）。
"""

from __future__ import annotations

from typing import Any, Optional

from core.kernel import ast
from core.kernel.symbols import SymbolKind
from core.kernel.spec.base import TypeKind


# callable 内部类型名的守卫错误消息（单点真理：三解析器 × 多分支共用，防文案漂移）。
CALLABLE_INTERNAL_TYPE_MSG = (
    "'callable' is an internal type name and cannot be used as a user type. "
    "Use 'fn' for an unconstrained callable, or 'fn[(...)]' for a signature constraint."
)


def is_constructor_ref_expr(lookup_symbol, expr_node) -> bool:
    """expr 是否为类名构造器引用（``fn f = Dog`` 的 Dog）。

    与 ``_infer_fn_type`` 的构造器引用判定同构：IbName 且指向 CLASS 符号。
    """
    if isinstance(expr_node, ast.IbName):
        sym = lookup_symbol(expr_node.id) if lookup_symbol else None
        return sym is not None and sym.kind == SymbolKind.CLASS
    return False


def is_fn_callable_value(
    registry: Any,
    spec: Optional[Any],
    expr_node,
    lookup_symbol,
) -> bool:
    """fn 参数/返回的"可调用"判定（与 fn 声明语义对齐）。

    非 CLASS 走 ``registry.is_callable``；CLASS 须定义 ``__call__`` 或是类名
    构造器引用（is_callable(CLASS) 恒真——get_call_cap 对 CLASS 返回 truthy
    标记不查 __call__，直接用它会把无 __call__ 实例漏检为可调用）。
    """
    if spec is None:
        return False
    if spec.kind == TypeKind.CLASS.value:
        if "__call__" in (getattr(spec, "members", None) or {}):
            return True
        return is_constructor_ref_expr(lookup_symbol, expr_node)
    return bool(registry.is_callable(spec))
