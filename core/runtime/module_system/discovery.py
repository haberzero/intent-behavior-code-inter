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
        """
        [IES 2.2] 动态加载 _spec.py，完整实现协议。

        协议要求：
        1. __ibcext_metadata__() - 返回插件元数据 (name, version, description, dependencies)
        2. __ibcext_vtable__() - 返回方法虚表，将 Python callable 映射为 IBC-Inter 方法

        注意：vtable 加载是 IES 2.2 协议的核心部分，使插件方法在语义分析阶段可见。
        """
        import sys

        # 将 ibc_modules 添加到 sys.path 以支持相对导入
        # 这允许 _spec.py 中的 "from .core import AIPlugin" 等相对导入正常工作
        ibc_modules_path = os.path.dirname(os.path.dirname(spec_path))
        if ibc_modules_path not in sys.path:
            sys.path.insert(0, ibc_modules_path)

        # 构建模块名，使其成为 ibc_modules 的子模块
        # 例如：ibc_modules/ai/_spec.py -> 模块名 ibc_modules.ai._spec
        parent_dir = os.path.basename(os.path.dirname(spec_path))
        internal_name = f"{parent_dir}._spec"

        try:
            spec = importlib.util.spec_from_file_location(internal_name, spec_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except ImportError as e:
            # 如果相对导入失败（如 core.py 不存在），静默降级：只加载 metadata
            # 这允许 _spec.py 文件存在但 vtable 不完整的情况
            mod = None

        metadata = None

        # 1. 加载 __ibcext_metadata__() - 注册模块元数据
        if mod and hasattr(mod, '__ibcext_metadata__'):
            metadata_dict = mod.__ibcext_metadata__()
            if metadata_dict and isinstance(metadata_dict, dict):
                from core.kernel.types.descriptors import ModuleMetadata
                raw_name = metadata_dict.get("name", module_name)
                if "." in raw_name:
                    parts = raw_name.split(".")
                    module_path_val = parts[0]
                    name_val = parts[1] if len(parts) > 1 else raw_name
                else:
                    module_path_val = None
                    name_val = raw_name
                metadata = ModuleMetadata(
                    name=name_val,
                    module_path=module_path_val,
                    members={}
                )

        # 2. 加载 __ibcext_vtable__() - 将 Callable 转换为 FunctionMetadata
        # [IES 2.2 Protocol] vtable 是协议的核心部分，使插件方法在语义分析阶段可见
        # 注意：如果 vtable 加载失败（如缺少依赖模块），会静默降级，只注册 metadata
        if metadata and mod and hasattr(mod, '__ibcext_vtable__'):
            try:
                vtable = mod.__ibcext_vtable__()
                if vtable and isinstance(vtable, dict):
                    from core.kernel.types.descriptors import FunctionMetadata
                    for method_name, method_impl in vtable.items():
                        if callable(method_impl):
                            # 将 Python callable 转换为 FunctionMetadata
                            # 注意：此处创建的 FunctionMetadata 是简化的，用于语义分析阶段的方法解析
                            # 完整的函数签名解析在 LLMExecutor 或运行时进行
                            func_meta = FunctionMetadata(
                                name=method_name,
                                module_path=module_name,
                                members={}
                            )
                            metadata.members[method_name] = func_meta
            except ImportError:
                # vtable 加载失败（如 core.py 不存在），静默忽略
                pass

        if metadata:
            if hasattr(metadata, 'members'):
                new_members = {}
                for name, member in metadata.members.items():
                    if isinstance(member, TypeDescriptor):
                        new_members[name] = SymbolFactory.create_from_descriptor(name, member)
                    else:
                        new_members[name] = member
                metadata.members = new_members
            return metadata

        return None
