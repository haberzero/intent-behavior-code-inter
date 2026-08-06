from typing import Any, List
from core.runtime.objects.kernel import IbObject
from core.kernel.issue import InterpreterError


def _iter_elements(obj: IbObject) -> List[IbObject]:
    """提取可迭代对象的元素列表（与 VM for 循环同一协议：__iter__/to_list）。"""
    from core.runtime.objects.primitives import IbList, IbTuple

    if isinstance(obj, (IbList, IbTuple)):
        return list(obj.elements)
    if obj.ib_class.lookup_method("__iter__") is not None:
        r = obj.receive("__iter__", [])
        if isinstance(r, (IbList, IbTuple)):
            return list(r.elements)
    if obj.ib_class.lookup_method("to_list") is not None:
        r = obj.receive("to_list", [])
        if isinstance(r, (IbList, IbTuple)):
            return list(r.elements)
    raise InterpreterError(
        f"Object of type '{obj.ib_class.name}' is not iterable"
    )


def _sort_key(elem: IbObject) -> Any:
    """排序键：原生值；非标量值退化为字符串表示（保持可比较）。"""
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

    manager.register("enumerate", _enumerate, unbox=False)
    manager.register("zip", _zip, unbox=False)
    manager.register("sorted", _sorted, unbox=False)
