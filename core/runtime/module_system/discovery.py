import os
import sys
import json
import inspect
import importlib.util
from typing import Dict, List, Optional, Any, Callable
from core.runtime.host.host_interface import HostInterface
from core.kernel.types.descriptors import ModuleMetadata as ModuleType, TypeDescriptor
from core.kernel.symbols import SymbolFactory
from core.base.enums import RegistrationState

from core.kernel.types.descriptors import ModuleMetadata
from core.kernel.types.descriptors import FunctionMetadata


class ModuleDiscoveryService:
    """
    IBC-Inter 模块发现服务。
    负责在多个搜索路径（如 ibci_modules/ 和 plugins/）中发现并加载模块元数据。
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

        支持三种协议：
        1. 新版第一方组件（字典格式）：__ibcext_vtable__() 返回 {"functions": {...}}
           - 纯字典，不导入内核代码
           - discovery 内部使用 SpecBuilder 转换为原生元数据
        2. 旧版第三方插件（Callable格式）：__ibcext_vtable__() 返回 Dict[str, Callable]
           - 通过 inspect.signature() 提取签名
        3. 深度嵌入模块：__ibcext_vtable__() 返回 ModuleMetadata
           - 直接使用，ai 等模块专用

        这确保 IBC-Inter 内核完全独立于 Python 反射机制。
        """

        ibci_modules_path = os.path.dirname(os.path.dirname(spec_path))
        if ibci_modules_path not in sys.path:
            sys.path.insert(0, ibci_modules_path)

        parent_dir = os.path.basename(os.path.dirname(spec_path))
        internal_name = f"ibci_{parent_dir}._spec"

        try:
            spec = importlib.util.spec_from_file_location(internal_name, spec_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except ImportError:
            mod = None

        metadata = None
        raw_name = module_name

        if mod and hasattr(mod, '__ibcext_metadata__'):
            metadata_dict = mod.__ibcext_metadata__()
            if metadata_dict and isinstance(metadata_dict, dict):
                raw_name = metadata_dict.get("name", module_name)

        if mod and hasattr(mod, '__ibcext_vtable__'):
            try:
                vtable = mod.__ibcext_vtable__()

                # 协议3：深度嵌入模块直接返回 ModuleMetadata
                if isinstance(vtable, ModuleMetadata):
                    vtable.name = raw_name
                    metadata = vtable

                # 协议1：新版第一方组件和标准插件（字典格式，零侵入）
                elif vtable and isinstance(vtable, dict):
                    metadata = self._build_metadata_from_dict(raw_name, module_name, vtable)

            except ImportError:
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

    def _build_metadata_from_dict(self, raw_name: str, module_name: str, vtable: Dict[str, Any]) -> ModuleMetadata:
        """
        [IES 2.2] 从字典格式元数据构建 ModuleMetadata

        字典格式：
        {
            "functions": {
                "parse": {
                    "param_types": ["str"],
                    "return_type": "dict"
                }
            },
            "variables": {
                "pi": "float"
            }
        }

        内部使用 SpecBuilder 将字典转换为原生 IBC-Inter 元数据。
        """
        from core.extension.spec_builder import SpecBuilder

        if "." in raw_name:
            parts = raw_name.split(".")
            module_path_val = parts[0]
            name_val = parts[1] if len(parts) > 1 else raw_name
        else:
            module_path_val = None
            name_val = raw_name

        builder = SpecBuilder(name_val)

        functions = vtable.get("functions", {})
        for func_name, func_sig in functions.items():
            param_types = func_sig.get("param_types", [])
            return_type = func_sig.get("return_type", "any")
            builder.func(func_name, params=param_types, returns=return_type)

        variables = vtable.get("variables", {})
        for var_name, var_type in variables.items():
            builder.exports[var_name] = builder._resolve_type(var_type)

        metadata = builder.build()
        metadata.module_path = module_path_val
        return metadata
