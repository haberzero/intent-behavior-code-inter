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
        # 读取插件种类声明：
        #   "method_module" — 工具/方法插件（math, ai, json 等），必须显式 import 后才可用。
        #   "type_module"   — 内置类型扩展，可由 Prelude 预注入为全局符号。
        # 缺省值为 "method_module"，以确保向前兼容（所有未声明 kind 的旧插件
        # 均被视为 method_module，不会意外成为预注入全局符号）。
        plugin_kind = "method_module"

        if mod and hasattr(mod, '__ibcext_metadata__'):
            metadata_dict = mod.__ibcext_metadata__()
            if metadata_dict and isinstance(metadata_dict, dict):
                raw_name = metadata_dict.get("name", module_name)
                plugin_kind = metadata_dict.get("kind", "method_module")

        if mod and hasattr(mod, '__ibcext_vtable__'):
            try:
                vtable = mod.__ibcext_vtable__()

                # 协议2：深度嵌入模块直接返回 ModuleSpec
                if isinstance(vtable, ModuleSpec):
                    vtable.name = raw_name
                    # 方法插件必须显式 import 才可用，不预注入为全局内置符号
                    if plugin_kind == "method_module":
                        vtable.is_user_defined = True
                    return vtable

                # 协议1：标准插件（字典格式，零侵入）
                if vtable and isinstance(vtable, dict):
                    spec = self._build_spec_from_dict(raw_name, vtable)
                    # 方法插件必须显式 import 才可用，不预注入为全局内置符号
                    if plugin_kind == "method_module":
                        spec.is_user_defined = True
                    return spec

            except ImportError:
                pass

        return None

    def _build_spec_from_dict(self, raw_name: str, vtable: Dict[str, Any]) -> ModuleSpec:
        """
        从字典格式元数据构建 ModuleSpec。

        支持两种函数描述格式：
        1. 显式字典：{"param_types": ["str", "int"], "return_type": "float"}
        2. 可调用对象：直接传入 Python 函数/方法，自动通过 inspect.signature() 提取参数类型注解

        字典格式：
        {
            "functions": {
                "parse": {
                    "param_types": ["str"],
                    "return_type": "dict"
                },
                "auto_sig_func": some_python_callable,  # 自动推导签名
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
            if callable(func_sig):
                # 自动从 Python 函数签名提取参数类型名
                param_types, return_type = self._extract_signature(func_sig)
            elif isinstance(func_sig, dict):
                param_types = func_sig.get("param_types", [])
                return_type = func_sig.get("return_type", "void")
            else:
                param_types = []
                return_type = "void"

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

    # Python type annotation → IBCI type name mapping
    _PY_TYPE_TO_IBCI: Dict[str, str] = {
        "int": "int",
        "float": "float",
        "str": "str",
        "bool": "bool",
        "list": "list",
        "dict": "dict",
        "tuple": "tuple",
        "NoneType": "void",
        "None": "void",
    }

    def _extract_signature(self, func: Any) -> tuple:
        """
        通过 inspect.signature() 从 Python 函数自动提取参数类型名和返回类型名。

        - 跳过第一个参数（约定为 self）
        - 有注解则映射为 IBCI 类型名，无注解默认为 "any"
        - 返回类型无注解时默认为 "any"

        返回:
            (param_type_names: List[str], return_type_name: str)
        """
        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.values())
            # 跳过约定为 self 的首个参数
            if params and params[0].name in ("self", "cls"):
                params = params[1:]

            param_types = []
            for p in params:
                if p.annotation is inspect.Parameter.empty:
                    param_types.append("any")
                else:
                    ann_name = getattr(p.annotation, "__name__", str(p.annotation))
                    param_types.append(self._PY_TYPE_TO_IBCI.get(ann_name, "any"))

            ret_ann = sig.return_annotation
            if ret_ann is inspect.Signature.empty:
                return_type = "any"
            else:
                ret_name = getattr(ret_ann, "__name__", str(ret_ann))
                return_type = self._PY_TYPE_TO_IBCI.get(ret_name, "any")

            return param_types, return_type
        except (ValueError, TypeError):
            return [], "any"
