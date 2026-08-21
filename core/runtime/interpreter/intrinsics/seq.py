from typing import Any, List

from core.runtime.objects.kernel import IbObject
from core.runtime.objects.kernel.base import unbox
from core.kernel.issue import InterpreterError
from core.runtime.shared.iterable import resolve_iterable, resolve_iterable_cps
from core.runtime.shared.waitable import Waitable
from core.runtime.shared.cps_drive import BaseCPSDrive


def _iter_elements(obj: IbObject) -> List[IbObject]:
    """提取可迭代对象的元素列表（非生成器面）。

    迭代解析收敛到 ``resolve_iterable``（单一权威源，与 ``for``/``yield from``
    同协议：序列 / ``__iter__`` / ``to_list``）；不可迭代时抛
    ``InterpreterError``（语义错误而非返回 None）。**生成器**由调用方经
    ``_with_elements`` / ``_IterableComputeDrive`` 协作消费，不经本函数。
    """
    seq = resolve_iterable(obj)
    if seq is None:
        raise InterpreterError(
            f"Object of type '{obj.ib_class.name}' is not iterable"
        )
    return list(seq.elements)


class _IterableComputeDrive(BaseCPSDrive):
    """迭代元素计算 drive（Waitable + CPSDrivable）。

    生成器迭代元素（可能含 Waitable）经**协作物化**（``resolve_iterable_cps``，
    生成器体内 Waitable 让出给调度器推进）后执行 ``compute(element_lists)``
    （每个 iterable 对应一个元素列表）。VM ``vm_handle_IbCall`` 识别其为
    ``Waitable`` + ``CPSDrivable`` 后 ``yield from cps_drive``；宿主/线程体
    无活跃 VM 时经 ``try_result``/``result`` 同步阻塞兜底（与
    ``_ClassInstantiateDrive`` 同构）。
    """

    def __init__(self, iterables: List[Any], compute):
        self._iterables = list(iterables)
        self._compute = compute
        super().__init__()

    def _materialize_cps(self, executor):
        lists: List[List[IbObject]] = []
        for it in self._iterables:
            seq = yield from resolve_iterable_cps(it)
            if seq is None:
                raise InterpreterError(
                    f"Object of type '{it.ib_class.name}' is not iterable"
                )
            lists.append(list(seq.elements))
        return lists

    def _materialize_blocking(self):
        lists: List[List[IbObject]] = []
        for it in self._iterables:
            seq = resolve_iterable(it)
            if seq is None:
                raise InterpreterError(
                    f"Object of type '{it.ib_class.name}' is not iterable"
                )
            lists.append(list(seq.elements))
        return lists

    def cps_drive(self, executor):
        lists = yield from self._materialize_cps(executor)
        self._result = self._compute(lists)
        self._done = True
        return self._result

    def _drive(self):
        lists = self._materialize_blocking()
        self._result = self._compute(lists)
        self._done = True
        return self._result


def _sort_key(elem: IbObject) -> Any:
    """比较键：原生值；非标量值退化为字符串表示（保持可比较）。"""
    native = elem.to_native()
    if isinstance(native, IbObject):
        return str(native)
    return native


def register_seq(manager: Any, execution_context: Any, service_context: Any):
    """注册序列/集合辅助内置函数。"""

    from core.runtime.objects.kernel.generator import IbGenerator

    def _with_elements(iterable: IbObject, compute):
        """单可迭代元素计算：生成器 → 协作 drive；序列 → 同步直算。

        生成器经 ``_IterableComputeDrive`` 协作物化（VM 帧内让出 Waitable）；
        序列无 Waitable 面，同步直算（与既有行为一致）。
        """
        if isinstance(iterable, IbGenerator):
            return _IterableComputeDrive([iterable], lambda lists: compute(lists[0]))
        return compute(_iter_elements(iterable))

    def _enumerate(iterable: IbObject):
        """enumerate(iterable) -> list[(index, value), ...]。"""
        def compute(elements):
            return manager.registry.box(
                [(i, e) for i, e in enumerate(elements)]
            )
        return _with_elements(iterable, compute)

    def _zip(*iterables: IbObject):
        """zip(a, b, ...) -> list[(a_i, b_i, ...), ...]（按最短序列截断）。"""
        def compute(element_lists):
            return manager.registry.box(
                [tuple(items) for items in zip(*element_lists)]
            )
        if any(isinstance(x, IbGenerator) for x in iterables):
            return _IterableComputeDrive(list(iterables), compute)
        return compute([_iter_elements(x) for x in iterables])

    def _sorted(iterable: IbObject):
        """sorted(iterable) -> 新排序列表（不修改原容器）。"""
        def compute(elements):
            try:
                ordered = sorted(elements, key=_sort_key)
            except TypeError as e:
                raise InterpreterError(
                    f"sorted: elements are not mutually comparable: {e}"
                ) from e
            return manager.registry.box(ordered)
        return _with_elements(iterable, compute)

    def _reversed(iterable: IbObject):
        """reversed(iterable) -> 新逆序列表（不修改原容器；区别于原地 reverse()）。"""
        def compute(elements):
            return manager.registry.box(list(reversed(elements)))
        return _with_elements(iterable, compute)

    def _sum(iterable: IbObject):
        """sum(iterable) -> 数值元素之和。"""
        def compute(elements):
            total = 0
            for elem in elements:
                total = total + unbox(elem)
            return manager.registry.box(total)
        return _with_elements(iterable, compute)

    def _next(iterable: IbObject):
        """next(iterable) -> 推进迭代器/生成器到下一个产出值。

        对惰性生成器（``IbGenerator``）经协作单步消费（返回 ``_GeneratorConsumeDrive``，
        VM ``vm_handle_IbCall`` 帧内 ``cps_drive`` 让出 Waitable；耗尽抛
        ``InterpreterError``）。对其它可迭代对象（序列 / __iter__）取**首个元素**
        ——语言设计决策：与 Python ``next(list)`` 抛 ``TypeError`` 不同，IBCI 的
        序列是随机可访问容器，取首元素更贴合语言直觉。
        """
        if isinstance(iterable, IbGenerator):
            return iterable.generic_next()
        elements = _iter_elements(iterable)
        if not elements:
            raise InterpreterError("next(): iterator is exhausted")
        return elements[0]

    def _all(iterable: IbObject):
        """all(iterable) -> 全部元素为真。"""
        def compute(elements):
            for elem in elements:
                if not elem.receive("to_bool", []).to_native():
                    return manager.registry.box(False)
            return manager.registry.box(True)
        return _with_elements(iterable, compute)

    def _extrema_elems(values: List[IbObject], is_max: bool):
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

    def _extrema(*args: IbObject, is_max: bool):
        """min/max 共用：单参视为集合，多参视为逐值比较。"""
        if len(args) == 1:
            return _with_elements(args[0], lambda elements: _extrema_elems(elements, is_max))
        return _extrema_elems(list(args), is_max)

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
