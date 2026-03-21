import os
import json
import importlib.util
from typing import Dict, List, Optional, Any
from core.runtime.host.host_interface import HostInterface
from core.kernel.types.descriptors import ModuleMetadata as ModuleType, TypeDescriptor
from core.kernel.symbols import SymbolFactory
from core.base.enums import RegistrationState


class ModuleDiscoveryService:
    """
    IBC-Inter 模块发现服务。
    负责在多个搜索路径（如 ibc_modules/ 和 plugins/）中发现并加载模块元数据。
    """
    def __init__(self, search_paths: List[str]):
        self.search_paths = [os.path.abspath(p) for p in search_paths]

    def discover_all(self, registry: Optional[Any] = None) -> HostInterface:
        """
        扫描所有搜索路径，加载所有发现的模块 spec。
        """
        if registry:
            registry.verify_level(RegistrationState.STAGE_3_PLUGIN_METADATA.value)
            metadata_registry = registry.get_metadata_registry()
        else:
            metadata_registry = None
        host = HostInterface(external_registry=metadata_registry) if metadata_registry else HostInterface()
        discovered_modules = set()

        for path in self.search_paths:
            if not os.path.isdir(path):
                continue

            for entry in os.listdir(path):
                if entry in discovered_modules:
                    continue

                module_dir = os.path.join(path, entry)
                if not os.path.isdir(module_dir):
                    continue

                spec_path = os.path.join(module_dir, "_spec.py")

                if os.path.exists(spec_path):
                    try:
                        spec_metadata = self._load_spec(entry, spec_path)
                        if spec_metadata:
                            host.register_module(entry, None, spec_metadata)
                            discovered_modules.add(entry)
                    except Exception as e:
                        raise RuntimeError(f"Fatal Error: Failed to load spec for module '{entry}': {e}") from e

        return host

    def export_metadata(self, host: HostInterface, output_path: str) -> None:
        """
        [IES 2.2] 将发现的元数据导出为 .ibc_meta 文件

        实现构建时元数据快照，使编译器能在编译前获取插件类型签名。
        """
        metadata_snapshot = {
            "version": "1.0",
            "modules": {}
        }

        registry = host.metadata
        if hasattr(registry, 'to_dict'):
            snapshot = registry.to_dict()
            metadata_snapshot["modules"] = snapshot.get("modules", {})
            metadata_snapshot["classes"] = snapshot.get("classes", {})
            metadata_snapshot["functions"] = snapshot.get("functions", {})

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata_snapshot, f, indent=2, ensure_ascii=False)

    def _load_spec(self, module_name: str, spec_path: str) -> Optional[ModuleType]:
        """动态加载 spec.py 或 _spec.py"""
        internal_name = f"ibc_spec_{module_name}"
        spec = importlib.util.spec_from_file_location(internal_name, spec_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        
        # [IES 2.0 FIX] 更加鲁棒的元数据获取逻辑
        metadata = None
        if hasattr(mod, 'metadata'):
            metadata = mod.metadata
        elif hasattr(mod, 'spec'):
            metadata = mod.spec
            
        if metadata:
            # [IES 2.1 Regularization] 符号化正规化：将成员描述符转换为符号对象
            # 确保 Metadata.members 存储的是 Symbol 而非原始 Descriptor
            
            new_members = {}
            for name, member in metadata.members.items():
                if isinstance(member, TypeDescriptor):
                    new_members[name] = SymbolFactory.create_from_descriptor(name, member)
                else:
                    new_members[name] = member
            metadata.members = new_members
            return metadata
            
        return None
