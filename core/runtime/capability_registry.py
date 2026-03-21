from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Set
import threading


class CapabilityPriority(IntEnum):
    LOWEST = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100
    SYSTEM = 200


class CapabilityProvider:
    def __init__(
        self,
        name: str,
        provider: Any,
        plugin_id: str,
        priority: CapabilityPriority = CapabilityPriority.NORMAL
    ):
        self.name = name
        self.provider = provider
        self.plugin_id = plugin_id
        self.priority = priority
        self.allowed_replacements: Set[str] = {plugin_id}

    def __repr__(self):
        return f"CapabilityProvider({self.name}, priority={self.priority}, plugin={self.plugin_id})"


class CapabilityRegistry:
    """
    [IES 2.1] 能力注册中心。
    统一管理内核能力的注册、获取和替换。
    """
    CAP_LLM_PROVIDER = "llm_provider"
    CAP_LLM_EXECUTOR = "llm_executor"
    CAP_INTENT_MANAGER = "intent_manager"
    CAP_STATE_MANAGER = "state_manager"
    CAP_STACK_INSPECTOR = "stack_inspector"
    CAP_SYMBOL_VIEW = "symbol_view"
    CAP_PERMISSION_MANAGER = "permission_manager"
    CAP_SERIALIZATION = "serialization"

    def __init__(self):
        self._lock = threading.RLock()
        self._providers: Dict[str, List[CapabilityProvider]] = {}
        self._primary_cache: Dict[str, CapabilityProvider] = {}

    def register(
        self,
        capability_name: str,
        provider: Any,
        plugin_id: str,
        priority: CapabilityPriority = CapabilityPriority.NORMAL,
        allow_replace: bool = False
    ) -> bool:
        """
        注册一个能力提供者。

        Args:
            capability_name: 能力名称
            provider: 提供者实例
            plugin_id: 插件标识符
            priority: 优先级
            allow_replace: 是否允许被更高优先级替换

        Returns:
            是否注册成功
        """
        with self._lock:
            if capability_name not in self._providers:
                self._providers[capability_name] = []

            for existing in self._providers[capability_name]:
                if existing.plugin_id == plugin_id:
                    existing.provider = provider
                    existing.priority = priority
                    self._rebuild_cache(capability_name)
                    return True

            cap_provider = CapabilityProvider(
                name=capability_name,
                provider=provider,
                plugin_id=plugin_id,
                priority=priority
            )

            if not allow_replace:
                cap_provider.allowed_replacements.add(plugin_id)

            self._providers[capability_name].append(cap_provider)
            self._rebuild_cache(capability_name)
            return True

    def get(self, capability_name: str) -> Optional[Any]:
        """
        获取指定能力的最高优先级提供者。
        """
        with self._lock:
            if capability_name in self._primary_cache:
                return self._primary_cache[capability_name].provider
            return None

    def get_with_info(self, capability_name: str) -> Optional[CapabilityProvider]:
        """获取能力提供者的完整信息"""
        with self._lock:
            return self._primary_cache.get(capability_name)

    def get_all(self, capability_name: str) -> List[CapabilityProvider]:
        """获取指定能力的所有提供者（按优先级排序）"""
        with self._lock:
            if capability_name not in self._providers:
                return []
            return sorted(
                self._providers[capability_name],
                key=lambda x: x.priority,
                reverse=True
            )

    def replace(
        self,
        capability_name: str,
        new_provider: Any,
        plugin_id: str,
        force: bool = False
    ) -> bool:
        """
        替换指定能力的当前提供者。
        """
        with self._lock:
            if capability_name not in self._primary_cache:
                return False

            current = self._primary_cache[capability_name]

            if not force:
                if plugin_id not in current.allowed_replacements:
                    if CapabilityPriority.NORMAL <= current.priority:
                        return False

            new_cap = CapabilityProvider(
                name=capability_name,
                provider=new_provider,
                plugin_id=plugin_id,
                priority=CapabilityPriority.NORMAL
            )

            self._providers[capability_name] = [
                p for p in self._providers[capability_name]
                if p.plugin_id != plugin_id
            ] + [new_cap]

            self._rebuild_cache(capability_name)
            return True

    def unregister(self, capability_name: str, plugin_id: str) -> bool:
        """注销指定插件提供的能力"""
        with self._lock:
            if capability_name not in self._providers:
                return False

            original_len = len(self._providers[capability_name])
            self._providers[capability_name] = [
                p for p in self._providers[capability_name]
                if p.plugin_id != plugin_id
            ]

            if len(self._providers[capability_name]) == original_len:
                return False

            self._rebuild_cache(capability_name)
            return True

    def unregister_all(self, plugin_id: str) -> List[str]:
        """注销指定插件提供的所有能力"""
        with self._lock:
            removed = []
            for cap_name in list(self._providers.keys()):
                if self.unregister(cap_name, plugin_id):
                    removed.append(cap_name)
            return removed

    def _rebuild_cache(self, capability_name: str):
        """重建指定能力的最高优先级缓存"""
        if capability_name not in self._providers or not self._providers[capability_name]:
            self._primary_cache.pop(capability_name, None)
            return

        providers = self._providers[capability_name]
        highest = max(providers, key=lambda x: x.priority)
        self._primary_cache[capability_name] = highest

    def list_capabilities(self) -> Dict[str, int]:
        """列出所有已注册的能力及其优先级"""
        with self._lock:
            return {
                name: self._primary_cache[name].priority
                for name in self._primary_cache
            }
