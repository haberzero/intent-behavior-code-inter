"""
core.runtime.objects.kernel.comm — IBCI 语言层通信值对象。

包装 ``core.runtime.shared.comm`` 线程安全原语，作为一等公民 IbObject
暴露给 IBCI 代码：

- ``IbChannel``（chan）—— 数据流通道（send / recv / recv_nonblocking / close / subscribe）
- ``IbSlot``（slot）—— 共享状态槽（get / set / update）

（通信 Signal 抽象已于阶段 3 移除：零投递机制 + 与 VM 控制流 Signal 撞名，
见 WORKLOG 会话 8。）

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


@register_ib_type("chan")
class IbChannel(IbObject):
    """IBCI 语言层的 Channel 值对象（包装 ``ChannelCore``）。"""

    __slots__ = ("core",)

    def __init__(self, ib_class: IbClass, core: Optional[ChannelCore] = None):
        super().__init__(ib_class)
        self.core = core if core is not None else ChannelCore(mode="message")

    # -- 生产者 ------------------------------------------------ #

    def send(self, value) -> None:
        """向 Channel 发送数据（阻塞；有界缓冲满时等待）。"""
        self.core.send(unbox(value))

    def send_nowait(self, value) -> "IbObject":
        """非阻塞发送；返回 bool 指示是否投递成功。"""
        return self.ib_class.registry.box(self.core.send_nowait(unbox(value)))

    # -- 消费者 ------------------------------------------------ #

    def recv(self):
        """阻塞接收数据。"""
        val = self.core.recv()
        return self.ib_class.registry.box(val)

    def recv_nonblocking(self) -> "IbObject":
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
        return IbSubscriber(ib_class=cls, view=view)

    # -- 生命周期 / 内省 ---------------------------------------- #

    def close(self) -> None:
        """关闭 Channel。幂等。"""
        self.core.close()

    def __to_prompt__(self) -> str:
        return f"<chan {self.core.mode}>"

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        return self.core.snapshot()

    def snapshot(self) -> "IbObject":
        return self.ib_class.registry.box(self.core.snapshot())

    def __repr__(self):
        return f"<Channel mode={self.core.mode} name={self.core.name}>"


@register_ib_type("subscriber")
class IbSubscriber(IbObject):
    """IBCI 语言层的 pubsub 订阅者值对象（包装 ``_SubscriberView``）。

    ``chan(T, "pubsub")`` 是广播器；``c.subscribe()`` 返回本订阅者端点，
    提供独立消费队列（recv / recv_nonblocking / close）。
    """

    __slots__ = ("view",)

    def __init__(self, ib_class: IbClass, view: Any):
        super().__init__(ib_class)
        self.view = view

    def recv(self):
        """阻塞接收订阅队列数据。"""
        return self.ib_class.registry.box(self.view.recv())

    def recv_nonblocking(self) -> "IbObject":
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

    def __to_prompt__(self) -> str:
        return "<subscriber>"

    def __repr__(self):
        return f"<Subscriber channel_closed={self.view.closed}>"


@register_ib_type("slot")
class IbSlot(IbObject):
    """IBCI 语言层的 Slot 值对象（包装 ``SlotCore``，具名原子读写）。"""

    __slots__ = ("core",)

    def __init__(self, ib_class: IbClass, core: Optional[SlotCore] = None):
        super().__init__(ib_class)
        self.core = core if core is not None else SlotCore("anonymous")

    def get(self):
        """读当前值。"""
        return self.ib_class.registry.box(self.core.get())

    def set(self, value) -> None:
        """写新值。"""
        self.core.set(unbox(value))

    def update(self, value) -> None:
        """以 value 覆盖（兼容 update(fn) 的简化形态）。

        语言层 update 接受"新值"直接覆盖（原子 set），或可调用对象执行
        读改写（fn）。当前实现：若 value 可调用则走 CAS 读改写，否则 set。
        """
        if callable(value):
            self.core.update(lambda _old: unbox(value))
        else:
            self.core.set(unbox(value))

    def __to_prompt__(self) -> str:
        return f"<slot {self.core.name}>"

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        return self.core.snapshot()

    def snapshot(self) -> "IbObject":
        return self.ib_class.registry.box(self.core.snapshot())

    def __repr__(self):
        return f"<Slot name={self.core.name}>"
