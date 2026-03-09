from typing import Dict, Any, Callable, List, Optional
from core.runtime.objects.kernel import IbNativeFunction, IbObject
from core.foundation.registry import Registry

class IntrinsicManager:
    """
    内置函数 (Intrinsics) 管理器。
    采用“特权插件”模式，解耦解释器内核与标准库逻辑。
    """
    _intrinsics: Dict[str, IbNativeFunction] = {}

    @classmethod
    def register(cls, name: str, py_func: Callable, unbox: bool = True):
        """注册一个内置函数"""
        cls._intrinsics[name] = IbNativeFunction(py_func, unbox_args=unbox, is_method=False, name=f"builtin.{name}")

    @classmethod
    def get_all(cls) -> Dict[str, IbNativeFunction]:
        return cls._intrinsics

    @classmethod
    def load_defaults(cls, interpreter: Any):
        """加载标准内置函数"""
        from .io import register_io
        from .collection import register_collection
        from .conversion import register_conversion
        
        register_io(cls, interpreter)
        register_collection(cls, interpreter)
        register_conversion(cls, interpreter)
