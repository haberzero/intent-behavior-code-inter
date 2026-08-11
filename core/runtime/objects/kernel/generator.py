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
from ...shared.waitable import Waitable
from .base import IbValue
from ..ib_type_mapping import register_ib_type


@register_ib_type("generator")
class IbGenerator(IbValue):
    """惰性生成器值对象（可迭代序列）。

    含 ``yield`` 的函数调用产出本对象（不执行函数体）。迭代经内嵌单可恢复
    驱动推进函数体：``yield x`` 暂停并交付 ``x``，`next`/`for` 恢复。

    迭代方法（``to_list``/``generic_next``）经 GeneratorAxiom 声明并由
    primitive_initializer 注册到专门 "generator" IbClass 的 vtable
    （axiom 驱动自动化），用户 ``gen.to_list()`` / ``gen.generic_next()``
    走标准协议分发（``__getattr__`` + vtable），不设 receive 特判。
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
        """推进生成器到下一个产出值，返回该值；耗尽抛 StopIteration。

        驱动循环（``_drive_loop_gen``，``yield_generator_values=True``）向外
        yield 的只有两类：``GeneratorYield``（语言产出）与 ``Waitable``（宿主
        等待）。本方法作为迭代方：遇 ``GeneratorYield`` 直接取值返回；遇
        ``Waitable``（如生成器体内 ``@~`` 行为的 LLMFuture）阻塞等待其完成并把
        结果 ``send`` 注回驱动循环后继续推进——维持生成器体内 LLM 调用的同步
        解析语义（KNOWN_LIMITS §二十四），驱动契约两侧完备。
        """
        if self._exhausted:
            raise StopIteration
        try:
            event = next(self._driver)
        except StopIteration:
            self._exhausted = True
            raise
        while isinstance(event, Waitable):
            event = self._driver.send(event.result())
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