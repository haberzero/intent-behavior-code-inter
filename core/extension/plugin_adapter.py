"""
[IES 2.2] 插件适配器

提供 IES 2.0/2.1 旧版插件到 IES 2.2 的兼容支持。

向后兼容策略：
- 检测旧版 @ibcext.method 装饰器
- 自动提取 vtable 和 metadata
- 适配到 PluginSpec 格式
"""
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from core.extension.ibcext import IbPlugin, MethodBinding


@dataclass
class AdapterResult:
    """适配结果"""
    success: bool
    plugin_name: str
    vtable: Optional[Dict[str, Callable]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class LegacyPluginAdapter:
    """
    [IES 2.2] 旧版插件适配器

    将 IES 2.0/2.1 使用 @ibcext.method 装饰器的插件适配到 IES 2.2 格式。
    """
    def adapt(self, plugin: IbPlugin) -> AdapterResult:
        """
        将旧版插件适配到 IES 2.2

        Args:
            plugin: 实现了 IbPlugin 的旧版插件实例

        Returns:
            AdapterResult: 适配结果
        """
        try:
            plugin_name = getattr(plugin, 'plugin_id', None) or plugin.__class__.__name__

            vtable = self._extract_vtable(plugin)
            metadata = self._extract_metadata(plugin, plugin_name)

            return AdapterResult(
                success=True,
                plugin_name=plugin_name,
                vtable=vtable,
                metadata=metadata
            )
        except Exception as e:
            return AdapterResult(
                success=False,
                plugin_name=getattr(plugin, 'plugin_id', 'unknown'),
                error=str(e)
            )

    def _extract_vtable(self, plugin: IbPlugin) -> Dict[str, Callable]:
        """从插件实例提取虚表"""
        vtable = {}

        for attr_name in dir(plugin):
            if attr_name.startswith('_'):
                continue

            attr = getattr(plugin, attr_name)
            if callable(attr) and hasattr(attr, '_ibci_binding'):
                binding: MethodBinding = attr._ibci_binding
                vtable[binding.spec_name] = attr

        return vtable

    def _extract_metadata(self, plugin: IbPlugin, plugin_name: str) -> Dict[str, Any]:
        """从插件实例提取元数据"""
        metadata = {
            "name": plugin_name,
            "version": "legacy",
            "description": f"IES 2.0/2.1 legacy plugin: {plugin_name}",
            "adapter": "LegacyPluginAdapter",
        }

        vtable_methods = []
        for attr_name in dir(plugin):
            if attr_name.startswith('_'):
                continue
            attr = getattr(plugin, attr_name)
            if callable(attr) and hasattr(attr, '_ibci_binding'):
                binding: MethodBinding = attr._ibci_binding
                vtable_methods.append(binding.spec_name)

        if vtable_methods:
            metadata["methods"] = vtable_methods

        return metadata

    @staticmethod
    def is_legacy_plugin(obj: Any) -> bool:
        """
        检测是否为旧版插件

        判断依据：
        - 实现了 IbPlugin 接口
        - 没有 __ibcext_metadata__ 属性
        - 没有 __ibcext_vtable__ 属性
        """
        if not isinstance(obj, IbPlugin):
            return False

        has_new_protocol = (
            hasattr(obj, '__ibcext_metadata__') or
            hasattr(obj, '__ibcext_vtable__')
        )

        return not has_new_protocol


class PluginSpecAdapter:
    """
    [IES 2.2] PluginSpec 适配器

    将不同来源的插件规范统一转换为 PluginSpec 格式。
    """
    @staticmethod
    def from_legacy_metadata(
        module_name: str,
        metadata_obj: Any
    ) -> Dict[str, Any]:
        """
        从旧版 metadata 对象提取规范信息

        Args:
            module_name: 模块名称
            metadata_obj: 旧版 metadata 对象

        Returns:
            Dict[str, Any]: 规范字典
        """
        result = {
            "name": module_name,
            "version": "1.0.0",
            "description": "",
            "members": {}
        }

        if hasattr(metadata_obj, 'name'):
            result["name"] = metadata_obj.name

        if hasattr(metadata_obj, 'members'):
            for name, member in metadata_obj.members.items():
                if hasattr(member, 'name'):
                    result["members"][name] = member.name
                else:
                    result["members"][name] = str(type(member).__name__)

        return result


def adapt_legacy_plugin(plugin: IbPlugin) -> AdapterResult:
    """
    便捷函数：将旧版插件适配到 IES 2.2

    Args:
        plugin: 旧版插件实例

    Returns:
        AdapterResult: 适配结果
    """
    adapter = LegacyPluginAdapter()
    return adapter.adapt(plugin)


def is_legacy_plugin(obj: Any) -> bool:
    """便捷函数：检测是否为旧版插件"""
    return LegacyPluginAdapter.is_legacy_plugin(obj)
