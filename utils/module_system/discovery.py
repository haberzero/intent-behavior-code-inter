import os
import importlib.util
from typing import Dict, List, Optional
from utils.host_interface import HostInterface
from utils.semantic.types import ModuleType

class ModuleDiscoveryService:
    """
    IBC-Inter 模块发现服务。
    负责在多个搜索路径（如 ibc_modules/ 和 plugins/）中发现并加载模块元数据。
    """
    def __init__(self, search_paths: List[str]):
        self.search_paths = [os.path.abspath(p) for p in search_paths]

    def discover_all(self) -> HostInterface:
        """
        扫描所有搜索路径，加载所有发现的模块 spec。
        """
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
                    
                spec_path = os.path.join(module_dir, "spec.py")
                if os.path.exists(spec_path):
                    try:
                        spec_metadata = self._load_spec(entry, spec_path)
                        if spec_metadata:
                            host.register_module(entry, None, spec_metadata)
                            discovered_modules.add(entry)
                    except Exception as e:
                        print(f"Warning: Failed to load spec for module '{entry}': {e}")
                else:
                    # 如果没有 spec.py，尝试使用反射发现（兼容模式）
                    # 注意：这需要加载 __init__.py，通常在 check 阶段应尽量避免
                    pass
        
        return host

    def _load_spec(self, module_name: str, spec_path: str) -> Optional[ModuleType]:
        """动态加载 spec.py"""
        internal_name = f"ibc_spec_{module_name}"
        spec = importlib.util.spec_from_file_location(internal_name, spec_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        
        if hasattr(mod, 'spec') and isinstance(mod.spec, ModuleType):
            return mod.spec
        return None
