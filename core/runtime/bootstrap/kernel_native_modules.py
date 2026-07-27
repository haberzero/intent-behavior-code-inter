"""
内核原生模块预注册。

将 ai/ihost/idbg/isys 四个深度内核耦合的模块从插件发现流程提升为内核原生模块：
- 在 Engine 构造期即预注册到 HostInterface，不依赖磁盘发现；
- 标记 Provenance.KERNEL_NATIVE + Visibility.IMPORT_GATED；
- 通过 HostInterface 保护机制防止用户插件覆盖；
- 提供 late-hydrate 生命周期窗口。
"""
import importlib
import os
import sys
from typing import Any, Dict

from core.base.enums import Provenance, Visibility
from core.kernel.path import IbPath
from core.kernel.spec import TypeDef
from core.runtime.module_system.discovery import ModuleDiscoveryService
from core.runtime.path import InstallPaths


# logical_name -> package_name (物理目录名，位于 InstallPaths.modules_dir())
KERNEL_NATIVE_MODULES: Dict[str, str] = {
    "ai": "ibci_ai",
    "ihost": "ibci_ihost",
    "idbg": "ibci_idbg",
    "isys": "ibci_isys",
}


def _load_spec(package_name: str) -> TypeDef:
    """加载 kernel-native 模块的 _spec.py 并返回 TypeDef（已打 KERNEL_NATIVE 标记）。"""
    modules_dir = InstallPaths.modules_dir().to_native()
    spec_path = os.path.join(modules_dir, package_name, "_spec.py")
    if not os.path.isfile(spec_path):
        raise RuntimeError(f"Kernel-native spec missing: {spec_path}")

    # 复用 discovery 的 spec 加载与字典->TypeDef 转换逻辑
    type_def = ModuleDiscoveryService([])._load_spec(package_name, spec_path)
    if type_def is None:
        raise RuntimeError(f"Failed to load kernel-native spec: {spec_path}")

    type_def.provenance = Provenance.KERNEL_NATIVE
    type_def.visibility = Visibility.IMPORT_GATED
    return type_def


def _load_implementation(package_name: str) -> Any:
    """加载 kernel-native 模块的实现包并调用 create_implementation() 工厂。"""
    modules_dir = InstallPaths.modules_dir().to_native()
    parent_dir = IbPath.from_native(modules_dir).parent
    if parent_dir is None:
        raise RuntimeError(f"Cannot determine parent of modules_dir: {modules_dir}")
    parent_native = parent_dir.to_native()

    # 与 ModuleLoader 一致：将模块目录父路径加入 sys.path 以支持直接 import package_name
    if parent_native not in sys.path:
        sys.path.insert(0, parent_native)

    # 统一使用完整包名 ibci_modules.<package_name>，避免 namespace package
    # 在不同 import 路径下产生重复模块对象（如 ibci_ai vs ibci_modules.ibci_ai）。
    mod = importlib.import_module(f"ibci_modules.{package_name}")
    factory = getattr(mod, "create_implementation", None)
    if factory is None:
        raise RuntimeError(f"Kernel-native package {package_name} has no create_implementation")
    return factory()


def register_kernel_native_modules(host_interface: "HostInterface") -> None:
    """在 HostInterface 中预注册所有 kernel-native 模块。"""
    from core.kernel.host_interface import HostInterface

    for logical_name, package_name in KERNEL_NATIVE_MODULES.items():
        type_def = _load_spec(package_name)
        implementation = _load_implementation(package_name)

        host_interface.register_module(
            logical_name,
            implementation,
            metadata=type_def,
            discovery_name=package_name,
        )
        host_interface.reserve_kernel_native_name(logical_name)


def late_hydrate_kernel_native_modules(service_context: Any) -> None:
    """
    在 registry hooks（llm_executor / host_service / stack_inspector / state_reader）
    全部注入后，给 kernel-native 模块第二次水化窗口。
    """
    host = service_context.interop.host_interface
    for logical_name in KERNEL_NATIVE_MODULES:
        impl = host.get_module_implementation(logical_name)
        if impl is not None and hasattr(impl, "hydrate"):
            impl.hydrate(service_context)
