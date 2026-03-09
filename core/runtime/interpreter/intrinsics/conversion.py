from typing import Any
from core.runtime.objects.kernel import IbObject
from core.foundation.registry import Registry

def register_conversion(manager, interpreter):
    """注册类型转换相关内置函数"""
    
    def _str(obj: IbObject):
        """全局 str() 函数 -> __to_prompt__ 协议"""
        return obj.receive('__to_prompt__', [])

    def _int(obj: IbObject):
        """全局 int() 函数 -> cast_to 协议"""
        return obj.receive('cast_to', [Registry.get_class("int")])

    def _float(obj: IbObject):
        """全局 float() 函数 -> cast_to 协议"""
        return obj.receive('cast_to', [Registry.get_class("float")])

    manager.register('str', _str, unbox=False)
    manager.register('int', _int, unbox=False)
    manager.register('float', _float, unbox=False)
