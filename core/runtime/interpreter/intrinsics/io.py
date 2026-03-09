from typing import Optional, Any
from core.runtime.objects.kernel import IbObject
from core.runtime.objects.builtins import IbNone
from core.foundation.registry import Registry

def register_io(manager, interpreter):
    """注册 I/O 相关内置函数"""
    
    def _print(*args):
        # 遵循 UTS: 使用 __to_prompt__ 协议
        texts = [str(arg.receive('__to_prompt__', []).to_native()) if hasattr(arg, 'receive') else str(arg) for arg in args]
        msg = " ".join(texts)
        if interpreter.output_callback:
            interpreter.output_callback(msg)
        else:
            print(msg)
        return manager.registry.get_none()

    def _input(prompt: Optional[IbObject] = None):
        p = prompt.to_native() if prompt else ""
        res = input(p)
        return manager.registry.box(res)

    manager.register('print', _print, unbox=False) # print 需要处理 IbObject 列表
    manager.register('input', _input, unbox=False)
