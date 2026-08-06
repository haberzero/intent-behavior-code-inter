from typing import Any, Callable, Dict, List, Optional, Tuple
from core.kernel.issue import InterpreterError
from core.runtime.objects.kernel import IbObject, IbNativeFunction
from core.kernel.host_interface import HostInterface


class BoundPlugin:
    """绑定到特定引擎 registry 的插件实现容器。

    承载 ``(implementation, registry_id)``。registry_id 用于跨引擎隔离校验
    （原生模块对象只能在其绑定引擎内被访问）。替代向实现对象注入
    ``_ibci_registry_id`` 私有属性的做法——不再污染三方实现对象命名空间，
    隔离身份随容器流动（单一权威源，无硬编码字符串）。
    """

    __slots__ = ("implementation", "registry_id")

    def __init__(self, implementation: Any, registry_id: int):
        self.implementation = implementation
        self.registry_id = registry_id


class InterOpImpl:
    def __init__(self, host_interface: Optional[HostInterface] = None):
        self.host_interface = host_interface or HostInterface()
        # 原生模块契约：module_name -> (vtable, whitelist)
        self._native_contracts: Dict[str, Tuple[Dict[str, Any], List[str]]] = {}
        # 插件实现对象绑定的引擎 registry 身份：module_name -> id(registry)
        self._registry_ids: Dict[str, int] = {}

    @property
    def metadata(self) -> Any:
        return self.host_interface.metadata

    def register_package(self, name: str, obj: Any, metadata: Optional[Any] = None, discovery_name: Optional[str] = None) -> None:
        """
        注册一个 Python 对象（模块、类或实例）作为包。

        ``obj`` 可为 ``BoundPlugin``（承载实现 + 绑定 registry 身份）；裸对象
        视为无跨引擎约束（registry_id 不记录）。
        """
        registry_id: Optional[int] = None
        implementation = obj
        if isinstance(obj, BoundPlugin):
            implementation = obj.implementation
            registry_id = obj.registry_id
        if registry_id is not None:
            self._registry_ids[name] = registry_id
        self.host_interface.register_module(name, implementation, metadata=metadata, discovery_name=discovery_name)

    def get_registry_id(self, name: str) -> Optional[int]:
        """插件实现对象绑定的引擎 registry 身份（未记录则 None，表示无约束）。"""
        return self._registry_ids.get(name)

    def bind_native_contract(self, module_name: str, vtable: Dict[str, Any], whitelist: List[str]) -> None:
        """绑定原生模块的 vtable 与属性白名单（显式承载，替代私有属性注入）。"""
        self._native_contracts[module_name] = (vtable, whitelist)

    def get_native_contract(self, module_name: str) -> Optional[Tuple[Dict[str, Any], List[str]]]:
        """获取原生模块的 vtable 与白名单。"""
        return self._native_contracts.get(module_name)

    def get_package(self, name: str) -> Optional[Any]:
        return self.host_interface.get_module_implementation(name)

    def get_discovery_name(self, module_name: str) -> Optional[str]:
        return self.host_interface.get_discovery_name_by_module(module_name)

    def get_module_name_by_discovery(self, discovery_name: str) -> Optional[str]:
        return self.host_interface.get_module_by_discovery_name(discovery_name)

    def get_all_package_names(self) -> List[str]:
        return list(self.host_interface.metadata.get_all_modules().keys())

    def wrap_python_function(self, func: Callable) -> Callable:
        """
        将 Python 函数包装，未来可以在此处增加基于 Python 类型提示的参数校验。
        """
        def wrapped(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                raise InterpreterError(f"Error in external function: {str(e)}") from e
        return wrapped
