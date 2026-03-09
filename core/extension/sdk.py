from typing import Any, Callable, Optional, List, Dict
from dataclasses import dataclass

@dataclass
class MethodBinding:
    """存储方法绑定元数据"""
    spec_name: str
    raw: bool = False  # 如果为 True，跳过自动解箱，直接接收 IbObject

def method(spec_name: str, raw: bool = False):
    """
    [IES 2.0 SDK] 装饰器：将 Python 函数绑定到 IBCI 插件契约。
    
    Args:
        spec_name: 契约中对应的函数名 (e.g. "fields")
        raw: 是否禁用自动解箱逻辑。若为 True，函数将直接接收 IbObject 参数。
    """
    def decorator(func: Callable):
        # 将绑定信息附加到函数对象上，供 Loader 扫描
        func._ibci_binding = MethodBinding(spec_name=spec_name, raw=raw)
        return func
    return decorator

def module(name: str):
    """
    [IES 2.0 SDK] 装饰器：标记一个类为 IBCI 模块实现。
    目前主要用于增强代码可读性和潜在的自动注册。
    """
    def decorator(cls: type):
        cls._ibci_module_name = name
        return cls
    return decorator
