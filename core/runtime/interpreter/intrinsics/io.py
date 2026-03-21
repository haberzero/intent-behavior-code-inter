from typing import Optional, Any
from core.runtime.objects.kernel import IbObject, IbNativeFunction
from core.runtime.objects.builtins import IbNone
from core.base.registry import Registry

def register_io(manager: Any, execution_context: Any, service_context: Any):
    """注册 I/O 相关内置函数"""
    
    def _print(*args):
        # [IES 2.1 Decoupling] 
        # 核心：通过 service_context 获取输出回调，严禁直接访问 interpreter
        callback = service_context.output_callback
        
        # 遵循 UTS: 使用 __to_prompt__ 协议
        texts = [str(arg.receive('__to_prompt__', []).to_native()) if hasattr(arg, 'receive') else str(arg) for arg in args]
        msg = " ".join(texts)
        
        if callback:
            callback(msg)
        else:
            print(msg)
        return manager.registry.get_none()

    def _input(prompt: Optional[IbObject] = None):
        callback = service_context.input_callback
        p = prompt.to_native() if prompt else ""
        
        if callback:
            res = callback(p)
        else:
            res = input(p)
        return manager.registry.box(res)

    manager.register("print", _print, unbox=False)
    manager.register("input", _input, unbox=False)
