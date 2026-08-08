"""
core.runtime.objects.kernel.comm — IBCI 语言层通信值对象。

包装 ``core.runtime.shared.comm`` 线程安全原语，作为一等公民 IbObject
暴露给 IBCI 代码：

- ``IbChannel``（chan）—— 数据流通道（send / recv / recv_nowait / close / subscribe）
- ``IbSlot``（slot）—— 共享状态槽（get / set / update）

通信 Signal 抽象已移除（零投递机制 + 与 VM 控制流 Signal 撞名）。

经 ``@register_ib_type`` 注册，由 primitive_initializer 的 axiom 驱动自动化
绑定方法（见 ChannelAxiom / SlotAxiom 的 get_method_specs）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.kernel.issue import InterpreterError

from ..ib_type_mapping import register_ib_type
from .base import IbObject, unbox
from .ib_class import IbClass
from core.runtime.shared.comm.channel import ChannelCore
from core.runtime.shared.comm.slot import SlotCore


class _BoxingWaitable:
    """把底层 Waitable 的取回值经 ``box`` 映射为语言层值（Waitable 协议）。

    供阻塞语言方法（``recv``）返回——底层通道存原生值（send 时 unbox），
    取回时装箱为 IbObject，与旧阻塞 recv 的装箱语义一致。
    """

    def __init__(self, inner: Any, box):
        self._inner = inner
        self._box = box

    @property
    def is_done(self) -> bool:
        return self._inner.is_done

    def try_result(self):
        ok, val = self._inner.try_result()
        if ok:
            return (True, self._box(val))
        return (False, None)

    def result(self):
        return self._box(self._inner.result())

    def register_wake(self, event) -> None:
        self._inner.register_wake(event)


@register_ib_type("chan")
class IbChannel(IbObject):
    """IBCI 语言层的 Channel 值对象（包装 ``ChannelCore``）。"""

    __slots__ = ("core",)

    @classmethod
    def _create_blank(cls, ib_class: IbClass) -> "IbChannel":
        """类型化空实例（统一构造协议）：经该入口创建，handler/instantiate 同构。"""
        return cls(ib_class)

    def __init__(self, ib_class: IbClass, core: Optional[ChannelCore] = None):
        super().__init__(ib_class)
        self.core = core if core is not None else ChannelCore(mode="message")

    # -- 生产者 ------------------------------------------------ #

    def send(self, value) -> Any:
        """向 Channel 发送数据。

        **B1（PT-DEBT-13）阻塞即挂起**：非满立即投递返回 ``None``；有界满通道
        返回发送 Waitable（与 ``recv`` 返回接收 Waitable 对称）——VM 经既有
        Waitable 挂起路径等待腾出空间，宿主经 ``.result()`` 阻塞投递。消除
        满通道真阻塞（唯一消费者同调度器时死锁）。
        """
        item = unbox(value)
        core = self.core
        if core.mode != "pubsub":
            if core.send_nowait(item):
                return None  # 非满，立即投递完成
            return core.send_waitable(item)  # 满 → 发送 Waitable（已关闭在 core 内抛）
        # pubsub：优先立即全量投递（send_nowait 已投递部分时返回 False，但
        # 直接丢弃会丢消息）——经 fanout waitable 统一定义投递进度：先尝试
        # 立即投递，全部到位返回 None；部分未到位返回 waitable 供挂起续投。
        w = core.send_waitable(item)
        ok, _ = w.try_result()
        if ok:
            return None
        return w

    def send_nowait(self, value) -> "IbObject":
        """非阻塞发送；返回 bool 指示是否投递成功。"""
        return self.ib_class.registry.box(self.core.send_nowait(unbox(value)))

    # -- 消费者 ------------------------------------------------ #

    def recv(self) -> "_BoxingWaitable":
        """返回接收 Waitable（统一执行地基 · 阻塞即挂起）。

        VM 经既有 Waitable 挂起路径等待，恢复后得装箱 T；宿主经 ``.result()``
        阻塞取回装箱 T。与 ``collect``/``run_isolated`` 返回 HostAwaitable 同构。
        """
        return _BoxingWaitable(self.core.recv_waitable(), self.ib_class.registry.box)

    def recv_nowait(self) -> "IbObject":
        """非阻塞接收；无数据时返回 None。"""
        ok, val = self.core.recv_nowait()
        if not ok:
            return self.ib_class.registry.get_none()
        return self.ib_class.registry.box(val)

    def subscribe(self, size=0) -> "IbObject":
        """pubsub 模式订阅：返回订阅者消费者端点（IbSubscriber）。

        ``size``：订阅者队列容量（0=无界默认，>0 有界）。
        非 pubsub 通道调用抛 ``ValueError``。
        """
        view = self.core.subscribe(unbox(size))
        cls = self.ib_class.registry.get_class("subscriber")
        obj = IbSubscriber._create_blank(cls)
        obj.view = view
        return obj

    # -- 生命周期 / 内省 ---------------------------------------- #

    def close(self) -> None:
        """关闭 Channel。幂等。"""
        self.core.close()

    def __to_prompt__(self) -> str:
        return f"<chan {self.core.mode}>"

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        return self.core.snapshot()

    def __transient_state__(self) -> Dict[str, Any]:
        """瞬态序列化协议：纯状态存根（mode/name/closed/队列信息），不递归 core。"""
        return self.core.snapshot()

    def snapshot(self) -> "IbObject":
        return self.ib_class.registry.box(self.core.snapshot())

    def __repr__(self):
        return f"<Channel mode={self.core.mode} name={self.core.name}>"


@register_ib_type("subscriber")
class IbSubscriber(IbObject):
    """IBCI 语言层的 pubsub 订阅者值对象（包装 ``_SubscriberView``）。

    ``chan(T, "pubsub")`` 是广播器；``c.subscribe()`` 返回本订阅者端点，
    提供独立消费队列（recv / recv_nowait / close）。
    """

    __slots__ = ("view",)

    @classmethod
    def _create_blank(cls, ib_class: IbClass) -> "IbSubscriber":
        """类型化空实例（统一构造协议）：经该入口创建，调用方随后填充 view。"""
        return cls(ib_class, view=None)

    def __init__(self, ib_class: IbClass, view: Any):
        super().__init__(ib_class)
        self.view = view

    def recv(self) -> "_BoxingWaitable":
        """返回接收 Waitable（阻塞即挂起；宿主 ``.result()`` 阻塞取回装箱 T）。"""
        return _BoxingWaitable(self.view.recv_waitable(), self.ib_class.registry.box)

    def recv_nowait(self) -> "IbObject":
        """非阻塞接收；无数据时返回 None。"""
        ok, val = self.view.recv_nowait()
        if not ok:
            return self.ib_class.registry.get_none()
        return self.ib_class.registry.box(val)

    def close(self) -> None:
        """关闭订阅者端点（并注销于通道）。幂等。"""
        self.view.close()

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        return self.view.snapshot()

    def __transient_state__(self) -> Dict[str, Any]:
        """瞬态序列化协议：纯状态存根（队列信息），不递归订阅视图。"""
        return self.view.snapshot()

    def __to_prompt__(self) -> str:
        return "<subscriber>"

    def __repr__(self):
        return f"<Subscriber channel_closed={self.view.closed}>"


@register_ib_type("slot")
class IbSlot(IbObject):
    """IBCI 语言层的 Slot 值对象（包装 ``SlotCore``，具名原子读写）。"""

    __slots__ = ("core",)

    @classmethod
    def _create_blank(cls, ib_class: IbClass) -> "IbSlot":
        """类型化空实例（统一构造协议）：经该入口创建，handler/instantiate 同构。"""
        return cls(ib_class)

    def __init__(self, ib_class: IbClass, core: Optional[SlotCore] = None):
        super().__init__(ib_class)
        self.core = core if core is not None else SlotCore("anonymous")

    def get(self):
        """读当前值。"""
        return self.ib_class.registry.box(self.core.get())

    def set(self, value) -> None:
        """写新值。"""
        self.core.set(unbox(value))

    def update(self, value) -> Any:
        """原子读改写：以 value 覆盖，或对可调用对象执行 fn(当前值) → 新值。

        语言层 update 接受：
        - 普通值：原子 set（覆盖）；
        - 可调用对象（fn_callable / behavior）：走 SlotCore 的 CAS 读改写，
          锁外执行 fn，冲突时基于最新值重试。

        约束：fn 在锁外执行、应无副作用且不内嵌通信操作（否则可能死锁）；
        CAS 重试会重复调用 fn，故 fn 须是确定性函数。

        **F2（PT-DEBT-14）阻塞即挂起**：fn 为可调用对象时，本方法返回一个
        Waitable（不再经同步 ``.call`` 驱动——那会嵌套调度器或阻塞 LLM）。
        VM 经既有 Waitable 挂起路径驱动本 Waitable，在 **当前帧** 内经 CPS
        驱动 fn 求值并完成 CAS 读改写；宿主经 ``.result()`` 阻塞完成。
        """
        if value.ib_class.name in ("fn_callable", "behavior"):
            return _SlotUpdateWaitable(self, value)
        self.core.set(unbox(value))
        return None

    def __to_prompt__(self) -> str:
        return f"<slot {self.core.name}>"

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        return self.core.snapshot()

    def __transient_state__(self) -> Dict[str, Any]:
        """瞬态序列化协议：纯状态存根（name/value），不递归 core。"""
        return self.core.snapshot()

    def snapshot(self) -> "IbObject":
        return self.ib_class.registry.box(self.core.snapshot())

    def __repr__(self):
        return f"<Slot name={self.core.name}>"


class _SlotUpdateWaitable:
    """``slot.update(fn)`` 的 CAS 读改写 Waitable（F2：当前帧 CPS 驱动 fn）。

    当 ``update`` 的可调用分支返回本对象时，VM 经既有 Waitable 挂起路径驱动它：
    ``try_result()`` 在挂起恢复后读取当前值，经 ``_vm_call_fn_callable``
    （fn_callable）或 ``_vm_invoke_behavior``（behavior）在**当前 VM 帧** CPS 驱动
    fn 求值得到新值，CAS 写回（冲突则基于最新值重试），完成。消除了经同步 ``.call``
    驱动（lambda → 嵌套调度器 / behavior → 阻塞 LLM）的遗留妥协。
    """

    def __init__(self, slot: "IbSlot", fn):
        self._slot = slot
        self._fn = fn
        self._done = False

    @property
    def is_done(self) -> bool:
        return self._done

    def _drive(self) -> None:
        from core.runtime.frame import get_current_execution_context
        from core.runtime.coordinator import _drive_generator
        from core.runtime.vm.handlers._shared import _vm_call_fn_callable, _vm_invoke_behavior

        core = self._slot.core
        registry = self._slot.ib_class.registry
        fn = self._fn
        executor = get_current_execution_context()
        vm = executor.vm_executor if executor is not None else None
        if vm is None:
            # 宿主 / 线程体上下文：无当前 VM，回退到同步 .call（非调度路径，无嵌套调度器）。
            while not self._done:
                current = core.get()
                boxed_old = registry.box(current)
                new_ib = fn.call(registry.get_none(), [boxed_old])
                new_val = unbox(new_ib)
                if core.cas(current, new_val):
                    self._done = True
            return
        while not self._done:
            current = core.get()
            boxed_old = registry.box(current)
            if fn.ib_class.name == "fn_callable":
                gen = _vm_call_fn_callable(vm, fn, [boxed_old])
            else:
                gen = _vm_invoke_behavior(vm, fn, [boxed_old])
            new_ib = _drive_generator(vm, gen)
            new_val = unbox(new_ib)
            if core.cas(current, new_val):
                self._done = True

    def try_result(self):
        if self._done:
            return (True, None)
        self._drive()
        return (True, None)

    def result(self):
        self._drive()
        return None

    def register_wake(self, event) -> None:
        event.set()
