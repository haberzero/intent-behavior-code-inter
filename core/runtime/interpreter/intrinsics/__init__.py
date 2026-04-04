from typing import Dict, Any, Callable, List, Optional
from core.runtime.objects.kernel import IbNativeFunction, IbObject
from core.kernel.registry import KernelRegistry
from core.runtime.interpreter.intrinsics.io import register_io
from core.runtime.interpreter.intrinsics.collection import register_collection
from core.runtime.interpreter.intrinsics.meta import register_meta

class IntrinsicManager:
    """
    内置函数 (Intrinsics) 管理器。
    采用“特权插件”模式，解耦解释器内核与标准库逻辑。
    """
    def __init__(self, registry: KernelRegistry):
        self.registry = registry
        self._intrinsics: Dict[str, IbNativeFunction] = {}

    def register(self, name: str, py_func: Callable, unbox: bool = True):
        """注册一个内置函数"""
        # 获取 callable 类
        callable_class = self.registry.get_class("callable")
        logic_id = f"intrinsic:{name}"
        self._intrinsics[name] = IbNativeFunction(
            py_func, 
            unbox_args=unbox, 
            is_method=False, 
            name=f"builtin.{name}", 
            ib_class=callable_class,
            logic_id=logic_id
        )

    def rebind(self, interpreter: Any, context: Any, deserializer: Optional[Any] = None):
        """
        环境重绑定协议：将逻辑上的内置函数符号链接到当前物理环境的实现。
        """
        # 直接通过 context.define_variable 进行注入，保持单向依赖
        for name, func in self._intrinsics.items():
            # 注入时带上稳定的内置符号 UID，与编译器对齐
            context.define_variable(name, func, is_const=True, force=True, uid=f"builtin:{name}")
        
        # 2. 扫描池中已加载的对象 (用于处理那些被赋值给其他变量的函数)
        if deserializer:
            logic_id_map = {f.logic_id: f.py_func for f in self._intrinsics.values() if f.logic_id}
            deserializer.on_rebind(logic_id_map)
        
        # [IES 2.0 Meta-API] 特权：为每个内置函数显式设置逻辑标识
        for name, func in self._intrinsics.items():
            func.logic_id = f"intrinsic:{name}"

    def get_all(self) -> Dict[str, IbNativeFunction]:
        return self._intrinsics

    def load_defaults(self, execution_context: Any, service_context: Any):
        """加载标准内置函数"""

        register_io(self, execution_context, service_context)
        register_collection(self, execution_context, service_context)
        register_meta(self, execution_context, service_context)
