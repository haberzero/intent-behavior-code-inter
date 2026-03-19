from typing import Any, Callable, Optional, List, Dict
from dataclasses import dataclass
from abc import ABC, abstractmethod

from core.runtime.objects.kernel import IbObject
from core.foundation.source_atomic import Location, Severity
from core.domain.issue import InterpreterError as PluginError, CompilerError, InterpreterError

# [IES 2.1 SDK Isolation] 全量导出接口，插件不得直接 import core.* 内部细节
__all__ = [
    "IbPlugin",
    "method",
    "module",
    "PluginError",
    "CompilerError",
    "InterpreterError",
    "IbObject",
    "Location",
    "Severity",
    "ExtensionCapabilities"
]

@dataclass
class ExtensionCapabilities:
    """[IES 2.1 Security] 插件能力容器，仅暴露受限接口"""
    # 动态注入，此处仅作为类型提示占位符
    symbol_view: Any 
    permission_manager: Any
    intent_manager: Any

@dataclass
class MethodBinding:
    """存储方法绑定元数据"""
    spec_name: str
    raw: bool = False  # 如果为 True，跳过自动解箱，直接接收 IbObject

def method(spec_name: str, raw: bool = False):
    """
    [IES 2.0 SDK] 装饰器：将 Python 函数绑定到 IBCI 插件契约。
    """
    def decorator(func: Callable):
        func._ibci_binding = MethodBinding(spec_name=spec_name, raw=raw)
        return func
    return decorator

def module(name: str):
    """
    [IES 2.0 SDK] 装饰器：标记一个类为 IBCI 模块实现。
    """
    def decorator(cls: type):
        cls._ibci_module_name = name
        return cls
    return decorator

class IbPlugin(ABC):
    """
    [IES 2.1 SDK] 插件基类。
    提供自动化的虚表（VTable）生成和依赖注入契约支持。
    所有现代 IBCI 插件均应继承此类。
    """
    def __init__(self):
        self._capabilities = None

    def setup(self, capabilities: Any):
        """
        [IES 2.0 Contract] 插件初始化入口。
        子类若需重写，请务必调用 super().setup(capabilities) 或确保持有 capabilities 引用。
        """
        self._capabilities = capabilities

    def get_vtable(self) -> Dict[str, Callable]:
        """
        [IES 2.1 Automation] 自动化虚表生成。
        扫描类中所有带有 @method 装饰器的成员，构建符合内核要求的虚表。
        """
        vtable = {}
        # 扫描实例及父类的方法
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if hasattr(attr, '_ibci_binding'):
                binding: MethodBinding = attr._ibci_binding
                vtable[binding.spec_name] = attr
        return vtable
