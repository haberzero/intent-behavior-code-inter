from typing import Any, List
from core.runtime.objects.kernel import IbObject
from core.runtime.objects.kernel.base import unbox
from core.kernel.issue import InterpreterError
from core.runtime.vm.handlers._shared import _resolve_iterable


def _iter_elements(obj: IbObject) -> List[IbObject]:
    """提取可迭代对象的元素列表。

    迭代解析收敛到 ``_resolve_iterable``（单一权威源，与 ``for``/``yield from``
    同协议：序列 / 生成器 / ``__iter__`` / ``to_list``）；不可迭代时抛
    ``InterpreterError``（语义错误而非返回 None）。
    """
    seq = _resolve_iterable(obj)
    if seq is None:
        raise InterpreterError(
            f"Object of type '{obj.ib_class.name}' is not iterable"
        )
    return list(seq.elements)


def _sort_key(elem: IbObject) -> Any:
    """比较键：原生值；非标量值退化为字符串表示（保持可比较）。"""
    native = elem.to_native()
    if isinstance(native, IbObject):
        return str(native)
    return native


def register_seq(manager: Any, execution_context: Any, service_context: Any):
    """注册序列/集合辅助内置函数。"""

    def _enumerate(iterable: IbObject):
        """enumerate(iterable) -> list[(index, value), ...]。"""
        elements = _iter_elements(iterable)
        return manager.registry.box(
            [(i, e) for i, e in enumerate(elements)]
        )

    def _zip(*iterables: IbObject):
        """zip(a, b, ...) -> list[(a_i, b_i, ...), ...]（按最短序列截断）。"""
        element_lists = [_iter_elements(x) for x in iterables]
        return manager.registry.box(
            [tuple(items) for items in zip(*element_lists)]
        )

    def _sorted(iterable: IbObject):
        """sorted(iterable) -> 新排序列表（不修改原容器）。"""
        elements = _iter_elements(iterable)
        try:
            ordered = sorted(elements, key=_sort_key)
        except TypeError as e:
            raise InterpreterError(
                f"sorted: elements are not mutually comparable: {e}"
            ) from e
        return manager.registry.box(ordered)

    def _reversed(iterable: IbObject):
        """reversed(iterable) -> 新逆序列表（不修改原容器；区别于原地 reverse()）。"""
        elements = _iter_elements(iterable)
        return manager.registry.box(list(reversed(elements)))

    def _sum(iterable: IbObject):
        """sum(iterable) -> 数值元素之和。"""
        total = 0
        for elem in _iter_elements(iterable):
            total = total + unbox(elem)
        return manager.registry.box(total)

    def _next(iterable: IbObject):
        """next(iterable) -> 推进迭代器/生成器到下一个产出值。

        对惰性生成器（``IbGenerator``）经 ``generic_next`` 惰性推进；耗尽抛
        ``InterpreterError``。对其它可迭代对象（序列 / __iter__）取**首个元素**
        ——语言设计决策：与 Python ``next(list)`` 抛 ``TypeError`` 不同，IBCI 的
        序列是随机可访问容器，取首元素更贴合语言直觉（阶段 5 增量）。
        """
        from core.runtime.objects.kernel.generator import IbGenerator

        if isinstance(iterable, IbGenerator):
            try:
                return iterable.generic_next()
            except StopIteration:
                raise InterpreterError("next(): generator is exhausted")
        elements = _iter_elements(iterable)
        if not elements:
            raise InterpreterError("next(): iterator is exhausted")
        return elements[0]

    def _all(iterable: IbObject):
        """all(iterable) -> 全部元素为真。"""
        for elem in _iter_elements(iterable):
            if not elem.receive("to_bool", []).to_native():
                return manager.registry.box(False)
        return manager.registry.box(True)

    def _extrema(*args: IbObject, is_max: bool):
        """min/max 共用：单参视为集合，多参视为逐值比较。"""
        if len(args) == 1:
            values = _iter_elements(args[0])
        else:
            values = list(args)
        if not values:
            raise InterpreterError("min/max: empty sequence")
        best = values[0]
        best_key = _sort_key(best)
        try:
            for v in values[1:]:
                k = _sort_key(v)
                if (k > best_key) if is_max else (k < best_key):
                    best, best_key = v, k
        except TypeError as e:
            raise InterpreterError(
                f"{'max' if is_max else 'min'}: elements are not mutually comparable: {e}"
            ) from e
        return best

    def _min(*args: IbObject):
        """min(a, b, ...) 或 min(iterable) -> 最小值。"""
        return _extrema(*args, is_max=False)

    def _max(*args: IbObject):
        """max(a, b, ...) 或 max(iterable) -> 最大值。"""
        return _extrema(*args, is_max=True)

    manager.register("enumerate", _enumerate, unbox=False)
    manager.register("zip", _zip, unbox=False)
    manager.register("sorted", _sorted, unbox=False)
    manager.register("reversed", _reversed, unbox=False)
    manager.register("sum", _sum, unbox=False)
    manager.register("next", _next, unbox=False)
    manager.register("all", _all, unbox=False)
    manager.register("min", _min, unbox=False)
    manager.register("max", _max, unbox=False)
