"""
core.runtime.shared.comm.slot — Slot 共享状态核心。

具名、可反复读写、原子读改写。``update(fn)`` 的原子读改写采用"锁外计算 +
CAS 回写"策略：读当前值 → 锁外执行 fn 计算新值 → 持锁比较当前值并回写
（若被并发修改则重试）。避免在锁内执行用户回调（防死锁）。
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Optional


class SlotCore:
    """Slot 共享状态核心（具名、可反复读写、原子读改写）。

    - ``name``: 具名标识
    - ``get``: 读当前值（持锁）
    - ``set``: 写新值（持锁）
    - ``update(fn)``: 原子读改写——读当前值，锁外计算，CAS 回写（冲突重试）。
      文档约束：``fn`` 不应内嵌通信操作（若 fn 内部再进通信可能死锁）。
    """

    def __init__(self, name: str, initial_value: Any = None):
        self._name = name
        self._value: Any = initial_value
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return self._name

    def get(self) -> Any:
        with self._lock:
            return self._value

    def set(self, value: Any) -> None:
        with self._lock:
            self._value = value

    def update(self, fn: Callable[[Any], Any]) -> Any:
        """原子读改写：读 → 锁外计算 → CAS 回写（冲突重试）。

        返回最终写回的值。若 ``fn`` 抛异常则原样传播（不写回）。
        """
        # 1. 读当前值
        with self._lock:
            current = self._value
        # 2. 锁外计算
        new_value = fn(current)
        # 3. CAS 回写：若期间被并发修改则基于最新值重算
        while True:
            with self._lock:
                if self._value is current:
                    self._value = new_value
                    return new_value
                current = self._value
            new_value = fn(current)

    def cas(self, expected: Any, new_value: Any) -> bool:
        """单次 CAS 写回：仅当前值仍为 ``expected`` 时写 ``new_value``。

        返回是否写回成功（False 表示期间被并发修改，调用方应基于最新值重算重试）。
        供 CPS 驱动的原子读改写（``_SlotUpdateWaitable``）在锁外求值新值后使用。
        """
        with self._lock:
            if self._value is expected:
                self._value = new_value
                return True
            return False

    def snapshot(self) -> dict:
        with self._lock:
            return {"name": self._name, "value": self._value}
