"""
core.runtime.objects.kernel.generator — 惰性生成器对象。

``IbGenerator`` 是含 ``yield`` 函数的调用产出的可迭代值对象：
持有单可恢复驱动，迭代推进函数体、在
``yield`` 点暂停交付值、迭代恢复。驱动循环与 VM 主执行（``_drive_loop_gen``）
同构，但识别 ``GeneratorYield`` 语言级产出标记。

消费模型（协作式）：生成器驱动向外 yield ``Waitable``（LLM ``@~`` 行为 /
``chan.recv()`` 等真异步句柄）时，消费方**让出**（yield 给 VM 调度器协作推进），
而非同步阻塞 ``event.result()``。用户面 ``to_list``/``generic_next`` 返回
``_GeneratorConsumeDrive``（Waitable + CPSDrivable）——VM 经 ``cps_drive`` 帧内
协作驱动，宿主/线程体经 ``try_result``/``result`` 同步阻塞兜底（与
``_ClassInstantiateDrive`` 同构）。内部消费（for/yield from/seq 内建）直接用
CPS 方法（``to_list_cps``/``generic_next_cps``）``yield from``。
"""

from __future__ import annotations

from typing import Any, List

from ...shared.signals import GeneratorYield
from ...shared.waitable import Waitable
from .base import IbValue
from ..ib_type_mapping import register_ib_type
from core.runtime.shared.cps_drive import BaseCPSDrive


class _GeneratorExhausted:
    """生成器耗尽信号（CPS 消费返回的哨兵，携带子生成器 return 值）。

    用哨兵而非抛 ``StopIteration`` 表达耗尽——PEP 479 禁止在生成器帧内显式抛
    ``StopIteration``（会被转成 ``RuntimeError``），哨兵使耗尽信号能跨
    ``yield from`` 边界可靠传递。
    """

    __slots__ = ("return_value",)

    def __init__(self, return_value: Any = None):
        self.return_value = return_value


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
    # CPS 协作消费（内部权威；for/yield from/seq 内建 yield from 使用）
    # ------------------------------------------------------------------

    def generic_next_cps(self) -> Any:
        """CPS 推进到下一个产出值，返回该值；耗尽返回 ``_GeneratorExhausted``。

        驱动循环（``_drive_loop_gen``，``yield_generator_values=True``）向外
        yield 的只有两类：``GeneratorYield``（语言产出）与 ``Waitable``（宿主
        等待）。本方法遇 ``GeneratorYield`` 直接 ``return`` 该值；遇 ``Waitable``
        （如生成器体内 ``@~`` 行为的 LLMFuture / ``chan.recv()``）**让出**——
        ``yield`` 交外层 CPS 驱动（VM 调度器协作推进，不阻塞 VM 线程），就绪后
        ``send`` 结果注回驱动循环继续推进。驱动耗尽（``StopIteration``）时返回
        ``_GeneratorExhausted``（携带子生成器 return 值）。
        """
        if self._exhausted:
            return _GeneratorExhausted(None)
        try:
            event = next(self._driver)
        except StopIteration as si:
            self._exhausted = True
            return _GeneratorExhausted(si.value)
        while isinstance(event, Waitable):
            # 让出等待其完成：把完成值 **send 回生成器驱动**（驱动把它路由回
            # yield 该 Waitable 的 handler 解析，如行为 executor 把原始 LLMResult
            # 解析为 IbObject），再推进到下一个事件。
            resolved = yield event
            event = self._driver.send(resolved)
        if isinstance(event, GeneratorYield):
            return event.value
        raise RuntimeError(f"generator driver yielded unexpected event {event!r}")

    def to_list_cps(self) -> Any:
        """CPS 物化：推进到耗尽，``yield from`` 协作让出，返回全部产出的装箱 IbList。

        供 ``for`` 迭代 / ``list()`` 消费（惰性推进、一次性耗尽）。
        """
        out: List[Any] = []
        while not self._exhausted:
            item = yield from self.generic_next_cps()
            if isinstance(item, _GeneratorExhausted):
                break
            out.append(item)
        return self.ib_class.registry.box(out)

    # ------------------------------------------------------------------
    # 同步阻塞兜底（宿主/线程体无活跃 VM 时经 drive 使用）
    # ------------------------------------------------------------------

    def _generic_next_blocking(self) -> Any:
        """同步阻塞推进（``Waitable.result()`` 直等）——非协作，仅宿主兜底。"""
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

    def _to_list_blocking(self) -> Any:
        """同步阻塞物化——非协作，仅宿主兜底。"""
        out: List[Any] = []
        while not self._exhausted:
            try:
                out.append(self._generic_next_blocking())
            except StopIteration:
                break
        return self.ib_class.registry.box(out)

    # ------------------------------------------------------------------
    # 用户面方法（vtable）：返回消费 drive（VM 协作驱动 / 宿主阻塞兜底）
    # ------------------------------------------------------------------

    def generic_next(self) -> "_GeneratorConsumeDrive":
        """用户面 ``gen.generic_next()``：返回单步消费 drive。"""
        return _GeneratorConsumeDrive(self, "next")

    def to_list(self) -> "_GeneratorConsumeDrive":
        """用户面 ``gen.to_list()``：返回物化消费 drive。"""
        return _GeneratorConsumeDrive(self, "to_list")


class _GeneratorConsumeDrive(BaseCPSDrive):
    """生成器消费的帧内 CPS 驱动 Waitable（Waitable + CPSDrivable）。

    由 :meth:`IbGenerator.generic_next` / ``to_list`` 返回（vtable 用户面方法）；
    VM ``vm_handle_IbCall`` 识别其为 ``Waitable`` + ``CPSDrivable`` 后 ``yield
    from cps_drive``——经 CPS 消费方法协作消费生成器（体内 Waitable 让出给调度器
    推进）。宿主/线程体无活跃 VM 时 ``try_result``/``result`` 走同步阻塞兜底
    （与 :class:`_ClassInstantiateDrive` 同构）。

    ``mode="next"`` 耗尽映射为 ``InterpreterError("next(): generator is
    exhausted")``（对齐 ``seq.py`` ``next()`` 既有语义）；``mode="to_list"``
    耗尽即正常物化结束（返回空列表）。
    """

    def __init__(self, gen: "IbGenerator", mode: str):
        self._gen = gen
        self._mode = mode  # "to_list" | "next"
        super().__init__()

    def cps_drive(self, executor):
        gen = self._gen
        if self._mode == "to_list":
            self._result = yield from gen.to_list_cps()
        else:
            result = yield from gen.generic_next_cps()
            if isinstance(result, _GeneratorExhausted):
                from core.kernel.issue import InterpreterError

                raise InterpreterError("next(): generator is exhausted")
            self._result = result
        self._done = True
        return self._result

    def _drive(self):
        gen = self._gen
        if self._mode == "to_list":
            self._result = gen._to_list_blocking()
        else:
            try:
                self._result = gen._generic_next_blocking()
            except StopIteration:
                from core.kernel.issue import InterpreterError

                raise InterpreterError("next(): generator is exhausted")
        self._done = True
        return self._result
