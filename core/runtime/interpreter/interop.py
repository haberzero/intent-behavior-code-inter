from typing import Any, Callable, Dict, Optional
from core.runtime.interfaces import InterOp
from core.kernel.issue import InterpreterError
from core.runtime.objects.kernel import IbObject, IbNativeFunction
from core.base.host_interface import HostInterface

class InterOpImpl:
    def __init__(self, host_interface: Optional[HostInterface] = None):
        self.host_interface = host_interface or HostInterface()

    def register_package(self, name: str, obj: Any) -> None:
        """
        注册一个 Python 对象（模块、类或实例）作为包。
        """
        self.host_interface.register_module(name, obj)

    def get_package(self, name: str) -> Optional[Any]:
        return self.host_interface.get_module_implementation(name)

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
