from typing import Any
from core.runtime.objects.kernel import IbObject
from core.foundation.registry import Registry

def register_conversion(manager, interpreter):
    """
    注册类型转换相关内置函数。
    注意：在 IBCI 2.0 中，int, str, float 等已成为 Registry 中的类对象，
    它们本身通过 __call__ 协议支持类型转换，因此这里不再注册同名全局函数。
    """
    pass
