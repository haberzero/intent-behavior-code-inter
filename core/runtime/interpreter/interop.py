from typing import Any, Callable, Dict, List, Optional, Tuple
from core.kernel.issue import InterpreterError
from core.runtime.objects.kernel import IbObject, IbNativeFunction
from core.kernel.host_interface import HostInterface

class InterOpImpl:
    def __init__(self, host_interface: Optional[HostInterface] = None):
        self.host_interface = host_interface or HostInterface()
        # 原生模块契约：module_name -> (vtable, whitelist)
        self._native_contracts: Dict[str, Tuple[Dict[str, Any], List[str]]] = {}

    @property
    def metadata(self) -> Any:
        return self.host_interface.metadata

    def register_package(self, name: str, obj: Any, metadata: Optional[Any] = None, discovery_name: Optional[str] = None) -> None:
        """
        注册一个 Python 对象（模块、类或实例）作为包。
        """
        self.host_interface.register_module(name, obj, metadata=metadata, discovery_name=discovery_name)

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
