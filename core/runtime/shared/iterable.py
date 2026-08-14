"""
core.runtime.shared.iterable — 可迭代解析单一权威源。

把"可迭代值 → 元素序列"的解析（序列直取 / IbGenerator→to_list / ``__iter__`` /
``to_list`` 协议）收敛为跨子系统共用函数。VM 侧（``for`` 循环 / ``yield from``）
与解释器内建（``enumerate``/``zip``/``sum``/``next`` 等 seq 内建）均经此解析——
单一权威源，避免双写。

放置于 ``shared`` 层（运行时叶子）：vm handler 与 intrinsics（interpreter 层）
都能经此依赖，不形成 vm ↔ interpreter 交叉。
"""

from __future__ import annotations

from typing import Any

from core.runtime.objects.kernel.base import is_sequence_value


def resolve_iterable(iterable_obj: Any):
    """把可迭代值解析为元素序列对象（单一权威源）。

    解析协议（与语言迭代语义一致）：序列直取；IbGenerator → to_list；
    结构化能力查询（``__iter__`` 预检存在才调用，用户实现体内真实错误不被
    宽 except 折叠）；to_list 兜底。返回序列对象（IbValue），不可迭代返回 None。
    """
    if is_sequence_value(iterable_obj):
        return iterable_obj
    # Optional 透明包装：持有值时按内层值解析（Optional[list[int]] 可 for 迭代 /
    # enumerate / zip / next——与 len/下标/方法调用的委托语义一致）；空值
    # fail-fast（明确"空 Optional 不可迭代"，不静默返回空序列掩盖错误值）。
    from core.runtime.objects.primitives.optional import IbOptional

    if isinstance(iterable_obj, IbOptional):
        if not iterable_obj._is_some:
            from core.kernel.issue import InterpreterError

            raise InterpreterError(
                "Cannot iterate an empty Optional"
            )
        return resolve_iterable(iterable_obj.payload)
    from core.runtime.objects.kernel.generator import IbGenerator
    if isinstance(iterable_obj, IbGenerator):
        return iterable_obj.to_list()
    if iterable_obj.ib_class.lookup_method("__iter__") is not None:
        r = iterable_obj.receive("__iter__", [])
        if is_sequence_value(r):
            return r
        # 用户类 __iter__ 写成分片生成器方法：receive 返回 IbGenerator
        # （IbUserFunction.call 的生成器感知），与顶层 IbGenerator 处理一致
        # to_list 物化——消除 `for x in obj` 的 GeneratorYield 泄漏崩溃。
        from core.runtime.objects.kernel.generator import IbGenerator
        if isinstance(r, IbGenerator):
            return r.to_list()
    if iterable_obj.ib_class.lookup_method("to_list") is not None:
        r = iterable_obj.receive("to_list", [])
        if is_sequence_value(r):
            return r
    return None
