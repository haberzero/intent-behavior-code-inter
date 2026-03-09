from typing import Dict, Any, Callable, List, Optional
from core.runtime.objects.kernel import IbNativeFunction, IbObject
from core.foundation.registry import Registry

class IntrinsicManager:
    """
    内置函数 (Intrinsics) 管理器。
    采用“特权插件”模式，解耦解释器内核与标准库逻辑。
    """
    def __init__(self, registry: Registry):
        self.registry = registry
        self._intrinsics: Dict[str, IbNativeFunction] = {}

    def register(self, name: str, py_func: Callable, unbox: bool = True):
        """注册一个内置函数"""
        # 获取 callable 类
        callable_class = self.registry.get_class("callable")
        self._intrinsics[name] = IbNativeFunction(py_func, unbox_args=unbox, is_method=False, name=f"builtin.{name}", ib_class=callable_class)

    def get_all(self) -> Dict[str, IbNativeFunction]:
        return self._intrinsics

    def load_defaults(self, interpreter: Any):
        """加载标准内置函数"""
        from .io import register_io
        from .collection import register_collection
        from .conversion import register_conversion
        
        register_io(self, interpreter)
        register_collection(self, interpreter)
        register_conversion(self, interpreter)
