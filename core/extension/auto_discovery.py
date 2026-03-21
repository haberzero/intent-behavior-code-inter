"""
[IES 2.2] 自动插件发现服务

实现零侵入自动嗅探机制，插件不再需要 import 任何核心代码。

核心功能：
- 自动扫描 ibc_modules/ 和 plugins/ 目录
- 通过 importlib 动态加载 _spec.py
- 检测 __ibcext_metadata__() 和 __ibcext_vtable__() 固定命名方法
- 构建 PluginSpec 对象返回

IES 2.2 固定命名方法协议：
- __ibcext_metadata__() -> Dict[str, Any]  返回插件元数据
- __ibcext_vtable__() -> Dict[str, Callable]  返回方法映射表
- create_implementation() -> Any  可选工厂函数
"""
import os
import importlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field


@dataclass
class PluginSpec:
    """
    插件规范对象

    包含插件的完整元信息。
    """
    name: str
    version: str = "1.0.0"
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    module_path: str = ""
    vtable: Optional[Dict[str, Callable]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    factory: Optional[Callable] = None

    def has_vtable(self) -> bool:
        """检查是否提供了虚表"""
        return self.vtable is not None and len(self.vtable) > 0


class AutoDiscoveryService:
    """
    [IES 2.2] 自动插件发现服务

    支持：
    - IES 2.2 新协议：__ibcext_metadata__() 和 __ibcext_vtable__()
    - IES 2.0/2.1 兼容：SpecBuilder 格式的 metadata 变量
    """
    def __init__(self, search_paths: Optional[List[str]] = None):
        self.search_paths = search_paths or self._get_default_paths()
        self._discovered: Dict[str, PluginSpec] = {}
        self._scan_paths()

    def _get_default_paths(self) -> List[str]:
        """获取默认搜索路径"""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        return [
            os.path.join(base_dir, "ibc_modules"),
            os.path.join(base_dir, "plugins"),
        ]

    def _scan_paths(self):
        """扫描所有搜索路径"""
        for search_path in self.search_paths:
            if not os.path.isdir(search_path):
                continue
            self._scan_directory(search_path)

    def _scan_directory(self, directory: str):
        """扫描单个目录下的所有插件"""
        try:
            entries = os.listdir(directory)
        except (OSError, PermissionError):
            return

        for entry in entries:
            module_dir = os.path.join(directory, entry)
            if not os.path.isdir(module_dir):
                continue

            spec_path = os.path.join(module_dir, "_spec.py")
            if os.path.exists(spec_path):
                try:
                    spec = self._load_plugin_spec(entry, spec_path)
                    if spec:
                        self._discovered[entry] = spec
                except Exception as e:
                    pass

    def _load_plugin_spec(self, module_name: str, spec_path: str) -> Optional[PluginSpec]:
        """加载单个插件的规范"""
        internal_name = f"ibc_autodiscovery_{module_name}"
        spec_loader = importlib.util.spec_from_file_location(internal_name, spec_path)
        if not spec_loader or not spec_loader.loader:
            return None

        mod = importlib.util.module_from_spec(spec_loader)

        try:
            spec_loader.loader.exec_module(mod)
        except Exception:
            return None

        spec = PluginSpec(
            name=module_name,
            module_path=spec_path,
        )

        if hasattr(mod, '__ibcext_metadata__') and callable(mod.__ibcext_metadata__):
            try:
                metadata = mod.__ibcext_metadata__()
                spec.metadata = metadata
                spec.name = metadata.get("name", module_name)
                spec.version = metadata.get("version", "1.0.0")
                spec.description = metadata.get("description", "")
                spec.dependencies = metadata.get("dependencies", [])
            except Exception:
                pass

        if hasattr(mod, '__ibcext_vtable__') and callable(mod.__ibcext_vtable__):
            try:
                spec.vtable = mod.__ibcext_vtable__()
            except Exception:
                pass

        if hasattr(mod, 'create_implementation') and callable(mod.create_implementation):
            spec.factory = mod.create_implementation

        if hasattr(mod, 'metadata') and not spec.metadata:
            spec.metadata = self._extract_legacy_metadata(mod.metadata)

        if hasattr(mod, 'spec') and not spec.metadata:
            spec.metadata = self._extract_legacy_metadata(mod.spec)

        return spec

    def _extract_legacy_metadata(self, metadata_obj: Any) -> Dict[str, Any]:
        """提取旧版 metadata 对象的元数据"""
        result = {}
        if hasattr(metadata_obj, 'name'):
            result['name'] = metadata_obj.name
        if hasattr(metadata_obj, 'members'):
            members = {}
            for name, member in metadata_obj.members.items():
                if hasattr(member, 'name'):
                    members[name] = member.name
                else:
                    members[name] = str(type(member).__name__)
            result['members'] = members
        return result

    def discover_plugins(self) -> Dict[str, PluginSpec]:
        """
        获取所有发现的插件规范

        返回：
            Dict[str, PluginSpec]：插件名称到规范的映射
        """
        return dict(self._discovered)

    def get_plugin(self, name: str) -> Optional[PluginSpec]:
        """获取指定名称的插件规范"""
        return self._discovered.get(name)

    def has_plugin(self, name: str) -> bool:
        """检查指定名称的插件是否存在"""
        return name in self._discovered

    def get_plugin_names(self) -> List[str]:
        """获取所有已发现插件的名称列表"""
        return list(self._discovered.keys())

    def create_plugin(self, name: str) -> Optional[Any]:
        """
        创建指定插件的实例

        使用插件的工厂函数（如果有）创建实例。
        """
        spec = self._discovered.get(name)
        if not spec:
            return None
        if spec.factory:
            try:
                return spec.factory()
            except Exception:
                return None
        return None


def create_auto_discovery_service(search_paths: Optional[List[str]] = None) -> AutoDiscoveryService:
    """工厂函数：创建自动发现服务"""
    return AutoDiscoveryService(search_paths=search_paths)
