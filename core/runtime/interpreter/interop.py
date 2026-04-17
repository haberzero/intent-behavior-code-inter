from typing import Any, Callable, Dict, List, Optional
from core.runtime.interfaces import InterOp
from core.kernel.issue import InterpreterError
from core.runtime.objects.kernel import IbObject, IbNativeFunction
from core.runtime.host.host_interface import HostInterface

# InterOpImpl 继承自 Protocol 接口，确保所有接口方法被实现（类似 ABC）。
# Python 允许此用法，isinstance 检查需要 @runtime_checkable 装饰。
class InterOpImpl(InterOp):
    def __init__(self, host_interface: Optional[HostInterface] = None):
        self.host_interface = host_interface or HostInterface()

    @property
    def metadata(self) -> Any:
        return self.host_interface.metadata

    def register_package(self, name: str, obj: Any, metadata: Optional[Any] = None, discovery_name: Optional[str] = None) -> None:
        """
        注册一个 Python 对象（模块、类或实例）作为包。
        """
        self.host_interface.register_module(name, obj, metadata=metadata, discovery_name=discovery_name)

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
                raise InterpreterError(f"Error in external function: {str(e)}")
        return wrapped
