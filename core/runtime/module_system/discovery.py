import os
import sys
import json
import inspect
import importlib.util
from typing import Dict, List, Optional, Any
from core.runtime.host.host_interface import HostInterface
from core.kernel.spec import ModuleSpec, MethodMemberSpec, MemberSpec
from core.base.enums import RegistrationState


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
                            # 注册时同时提供逻辑名称（ai）和物理发现名称（ibci_ai）
                            host.register_module(spec_metadata.name, None, spec_metadata, discovery_name=entry)
                            discovered_modules.add(entry)
                    except Exception as e:
                        raise RuntimeError(f"Fatal Error: Failed to load spec for module '{entry}': {e}") from e

        return host

    def export_metadata(self, host: HostInterface, output_path: str) -> None:
        """
        将发现的元数据导出为 .ibc_meta 文件。

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

    def _load_spec(self, module_name: str, spec_path: str) -> Optional[ModuleSpec]:
        """
        动态加载 _spec.py，完整实现协议。

        支持两种协议：
        1. 标准组件（字典格式）：__ibcext_vtable__() 返回 {"functions": {...}, "variables": {...}}
           - 纯字典，不导入内核代码
           - discovery 内部将字典转换为 ModuleSpec
        2. 深度嵌入模块：__ibcext_vtable__() 直接返回 ModuleSpec 实例

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

        raw_name = module_name

        if mod and hasattr(mod, '__ibcext_metadata__'):
            metadata_dict = mod.__ibcext_metadata__()
            if metadata_dict and isinstance(metadata_dict, dict):
                raw_name = metadata_dict.get("name", module_name)

        if mod and hasattr(mod, '__ibcext_vtable__'):
            try:
                vtable = mod.__ibcext_vtable__()

                # 协议2：深度嵌入模块直接返回 ModuleSpec
                if isinstance(vtable, ModuleSpec):
                    vtable.name = raw_name
                    return vtable

                # 协议1：标准插件（字典格式，零侵入）
                if vtable and isinstance(vtable, dict):
                    return self._build_spec_from_dict(raw_name, vtable)

            except ImportError:
                pass

        return None

    def _build_spec_from_dict(self, raw_name: str, vtable: Dict[str, Any]) -> ModuleSpec:
        """
        从字典格式元数据构建 ModuleSpec。

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
        """
        if "." in raw_name:
            parts = raw_name.split(".", 1)
            module_path_val = parts[0]
            name_val = parts[1]
        else:
            module_path_val = None
            name_val = raw_name

        spec = ModuleSpec(name=name_val, module_path=module_path_val)

        functions = vtable.get("functions", {})
        for func_name, func_sig in functions.items():
            param_types = func_sig.get("param_types", [])
            return_type = func_sig.get("return_type", "void")
            member = MethodMemberSpec(
                name=func_name,
                kind="method",
                type_name=return_type,
                param_type_names=list(param_types),
                param_type_modules=[None] * len(param_types),
                return_type_name=return_type,
            )
            spec.members[func_name] = member

        variables = vtable.get("variables", {})
        for var_name, var_type in variables.items():
            type_name = var_type if isinstance(var_type, str) else "any"
            spec.members[var_name] = MemberSpec(name=var_name, kind="field", type_name=type_name)

        return spec
