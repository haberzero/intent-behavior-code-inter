import os
import importlib.util
from typing import Dict, List, Optional, Any
from core.foundation.host_interface import HostInterface
from core.domain.types.descriptors import ModuleMetadata as ModuleType, TypeDescriptor
from core.domain.symbols import SymbolFactory
from core.runtime.enums import RegistrationState

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
            
        host = HostInterface()
        discovered_modules = set()
        
        for path in self.search_paths:
            if not os.path.isdir(path):
                continue
                
            for entry in os.listdir(path):
                # 避免重复加载（比如 plugins 中覆盖了内置模块）
                if entry in discovered_modules:
                    continue
                    
                module_dir = os.path.join(path, entry)
                if not os.path.isdir(module_dir):
                    continue
                    
                # [IES 2.0] 强制使用 _spec.py (静态契约)
                spec_path = os.path.join(module_dir, "_spec.py")
                
                if os.path.exists(spec_path):
                    try:
                        spec_metadata = self._load_spec(entry, spec_path)
                        if spec_metadata:
                            host.register_module(entry, None, spec_metadata)
                            discovered_modules.add(entry)
                    except Exception as e:
                        # [IES 2.0 Fail-fast] 契约加载失败属于致命错误
                        raise RuntimeError(f"Fatal Error: Failed to load spec for module '{entry}': {e}") from e
        
        return host

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
