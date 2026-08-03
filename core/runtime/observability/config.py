"""
core.runtime.observability.config — 控制层 ConfigStore（PT-MT-5）。

统一"启停"接口（设计 §五）：每个可控制能力有开启/关闭两侧，默认值不同。
``runtime.configure(...)`` 粒度链式覆盖：全局 → 单调用 → 单实例（后者优先）。

ConfigStore 为**单点真理**：只有一个 ConfigStore 承载全部配置；查询按
单实例 → 单调用 → 全局 顺序解析（读时解析，不缓存陈旧值）。

配置键（设计 §五.1）：
- parallel      并发 dispatch（默认开）
- stream        流式 LLM 增量（默认开；PT-MT-6 接入）
- observability 内省（snapshot/subscribe 记录，默认开）
- debug         调试细节（call_info 保留，默认关）
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

# 受控能力清单（默认值：parallel/stream/observability 开，debug 关）
DEFAULT_CONFIG: Dict[str, bool] = {
    "parallel": True,
    "stream": True,
    "observability": True,
    "debug": False,
}


class ConfigStore:
    """控制层配置存储（全局 → 单调用 → 单实例 链式覆盖，单点真理）。

    内部三张表（锁保护）：
    - ``_global``:  scope="global" 的默认配置
    - ``_call``:    scope="call:<key>" 的单调用配置
    - ``_instance``:scope="instance:<id>" 的单实例配置

    查询顺序：instance → call → global → DEFAULT_CONFIG。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._global: Dict[str, bool] = {}
        self._call: Dict[str, Dict[str, bool]] = {}
        self._instance: Dict[str, Dict[str, bool]] = {}

    # ------------------------------------------------------------------ #
    # 写（configure 入口）                                               #
    # ------------------------------------------------------------------ #

    def set_global(self, key: str, value: bool) -> None:
        with self._lock:
            self._global[key] = bool(value)

    def set_call(self, call_key: str, key: str, value: bool) -> None:
        """设置单调用配置（``call_key`` 为调用/任务标识）。"""
        with self._lock:
            self._call.setdefault(call_key, {})[key] = bool(value)

    def set_instance(self, instance_id: str, key: str, value: bool) -> None:
        """设置单实例配置。"""
        with self._lock:
            self._instance.setdefault(instance_id, {})[key] = bool(value)

    # ------------------------------------------------------------------ #
    # 读（读时解析，链式覆盖）                                            #
    # ------------------------------------------------------------------ #

    def get(self, key: str, instance_id: Optional[str] = None, call_key: Optional[str] = None) -> bool:
        """按 单实例 → 单调用 → 全局 → 默认 顺序解析配置值。"""
        with self._lock:
            if instance_id is not None:
                inst = self._instance.get(instance_id)
                if inst is not None and key in inst:
                    return inst[key]
            if call_key is not None:
                call = self._call.get(call_key)
                if call is not None and key in call:
                    return call[key]
            if key in self._global:
                return self._global[key]
        return DEFAULT_CONFIG.get(key, True)

    # ------------------------------------------------------------------ #
    # 内省                                                                #
    # ------------------------------------------------------------------ #

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "global": dict(self._global),
                "call": {k: dict(v) for k, v in self._call.items()},
                "instance": {k: dict(v) for k, v in self._instance.items()},
                "effective": {
                    k: self.get(k) for k in DEFAULT_CONFIG
                },
            }
