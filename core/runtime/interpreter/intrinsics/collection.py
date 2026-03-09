from typing import List, Any
from core.runtime.objects.kernel import IbObject
from core.foundation.registry import Registry

def register_collection(manager, interpreter):
    """注册集合相关内置函数"""
    
    def _len(obj: IbObject):
        """全局 len() 函数"""
        if hasattr(obj, 'elements'):
            return Registry.box(len(obj.elements))
        if hasattr(obj, 'fields'):
            return Registry.box(len(obj.fields))
        # 尝试消息发送 (UTS 协议)
        return obj.receive('len', [])

    def _range(*args):
        """全局 range() 函数"""
        native_args = [a.to_native() if hasattr(a, 'to_native') else a for a in args]
        return Registry.box(list(range(*native_args)))

    manager.register('len', _len, unbox=False)
    manager.register('range', _range, unbox=False)
