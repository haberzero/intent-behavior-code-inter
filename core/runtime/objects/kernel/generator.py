"""
core.runtime.objects.kernel.generator — 惰性生成器对象（阶段 5 yield）。

``IbGenerator`` 是含 ``yield`` 函数（D-08 自标记）调用产出的可迭代值对象：
持有单可恢复驱动（EXEC_FOUNDATION_DESIGN §5.2），迭代推进函数体、在
``yield`` 点暂停交付值、迭代恢复。驱动循环与 VM 主执行（``_drive_loop_gen``）
同构，但识别 ``GeneratorYield`` 语言级产出标记。
"""

from __future__ import annotations

from typing import Any, List

from ...shared.signals import GeneratorYield
from .base import IbValue


class IbGenerator(IbValue):
    """惰性生成器值对象（可迭代序列）。

    含 ``yield`` 的函数调用产出本对象（不执行函数体）。迭代经内嵌单可恢复
    驱动推进函数体：``yield x`` 暂停并交付 ``x``，`next`/`for` 恢复。
    """

    __slots__ = ("_driver", "_exhausted")

    def __init__(self, ib_class, driver: Any):
        super().__init__(ib_class)
        # 驱动对象：惰性构造（首次迭代时创建体驱动循环）。
        self._driver = driver
        self._exhausted = False

    # ------------------------------------------------------------------
    # 可迭代协议（语言级迭代经 __iter__/next）
    # ------------------------------------------------------------------

    def generic_next(self) -> Any:
        """推进生成器到下一个产出值，返回该值；耗尽抛 StopIteration。"""
        if self._exhausted:
            raise StopIteration
        try:
            event = next(self._driver)
        except StopIteration:
            self._exhausted = True
            raise
        if isinstance(event, GeneratorYield):
            return event.value
        raise RuntimeError(f"generator driver yielded unexpected event {event!r}")

    def to_list(self) -> Any:
        """把生成器推进到耗尽，返回全部产出值的装箱序列（IbList）。

        供 ``for`` 迭代 / ``list()`` 消费（惰性推进、一次性耗尽）。
        """
        out: List[Any] = []
        while not self._exhausted:
            try:
                out.append(self.generic_next())
            except StopIteration:
                break
        return self.ib_class.registry.box(out)