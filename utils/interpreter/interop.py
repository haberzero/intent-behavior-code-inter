from typing import Any, Callable, Dict, Optional
from .interfaces import InterOp

class InterOpImpl:
    def __init__(self):
        self._packages: Dict[str, Any] = {}

    def register_package(self, name: str, obj: Any) -> None:
        """
        注册一个 Python 对象（模块、类或实例）作为包，供 IBC 代码显式导入。
        """
        self._packages[name] = obj

    def get_package(self, name: str) -> Optional[Any]:
        return self._packages.get(name)

    def wrap_python_function(self, func: Callable) -> Callable:
        """
        将 Python 函数包装，未来可以在此处增加基于 Python 类型提示的参数校验。
        """
        def wrapped(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                from typedef.exception_types import InterpreterError
                raise InterpreterError(f"Error in external function: {str(e)}")
        return wrapped
