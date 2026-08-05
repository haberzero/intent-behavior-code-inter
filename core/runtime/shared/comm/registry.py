"""
core.runtime.shared.comm.registry — 通信对象可寻址注册表。

供广播枚举 + 定向查找 + 内省。``name → 对象`` 注册（Channel / Slot 可具名），
``handle → 任务句柄`` 注册。线程安全（锁保护）。
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional


class CommRegistry:
    """通信对象可寻址注册表（线程安全）。

    - ``register(name, obj)`` / ``unregister(name)``：具名注册（Channel/Slot）。
    - ``lookup(name)``：按名称查对象。
    - ``all(kind)``：枚举某类对象（kind 为 "chan"/"slot" 或 None=全部）。
    - ``snapshot()``：内省全部注册对象。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._objects: Dict[str, Any] = {}  # name -> object
        self._kinds: Dict[str, str] = {}    # name -> kind

    def register(self, name: str, obj: Any, kind: str) -> None:
        """具名注册对象。

        ``name`` 为空则自动生成唯一名（``kind@<id>``）。
        """
        with self._lock:
            if not name:
                name = f"{kind}@{id(obj):x}"
                while name in self._objects:
                    name = f"{kind}@{id(obj):x}_{len(self._objects)}"
            self._objects[name] = obj
            self._kinds[name] = kind

    def unregister(self, name: str) -> None:
        with self._lock:
            self._objects.pop(name, None)
            self._kinds.pop(name, None)

    def lookup(self, name: str) -> Optional[Any]:
        with self._lock:
            return self._objects.get(name)

    def kind_of(self, name: str) -> Optional[str]:
        with self._lock:
            return self._kinds.get(name)

    def all(self, kind: Optional[str] = None) -> List[Any]:
        with self._lock:
            if kind is None:
                return list(self._objects.values())
            return [obj for name, obj in self._objects.items() if self._kinds.get(name) == kind]

    def names(self, kind: Optional[str] = None) -> List[str]:
        with self._lock:
            if kind is None:
                return list(self._objects.keys())
            return [name for name, k in self._kinds.items() if k == kind]

    def snapshot(self) -> dict:
        with self._lock:
            out = {}
            for name, obj in self._objects.items():
                sn = getattr(obj, "snapshot", None)
                out[name] = sn() if callable(sn) else {"kind": self._kinds.get(name)}
            return out
