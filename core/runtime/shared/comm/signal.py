"""
core.runtime.shared.comm.signal — Signal 控制流核心。

抢占式、一次性控制信号。``target`` 为 None 表示广播，非 None 表示定向
（寻址到指定 handle / Channel / Slot / VM 实例）。投递语义：一次性、抢占式
（投递即生效，由接收方决定如何响应）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# Signal 支持的类型（kind 字符串白名单，非过程式硬编码分发——kind 是数据，
# 接收方按自身协议决定响应；此处仅约束合法取值）。
SIGNAL_KINDS = ("cancel", "pause", "resume", "config_change")


@dataclass(frozen=True)
class SignalCore:
    """Signal 控制流核心（不可变值对象）。

    - ``kind``: cancel / pause / resume / config_change
    - ``target``: None = 广播；具体句柄/名称 = 定向
    - ``payload``: 附加数据（如 config_change 的 diff）
    """

    kind: str
    target: Optional[Any] = None
    payload: Optional[Any] = None

    def __post_init__(self) -> None:
        if self.kind not in SIGNAL_KINDS:
            raise ValueError(
                f"Invalid signal kind: {self.kind!r} (expect {list(SIGNAL_KINDS)})"
            )

    def to_dict(self) -> dict:
        return {"kind": self.kind, "target": self.target, "payload": self.payload}
