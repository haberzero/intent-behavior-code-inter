from typing import Dict, Any, Type

_IB_TYPE_TO_CLASS: Dict[str, Type] = {}

def register_ib_type(name: str):
    """装饰器：注册 IBC-Inter 类型的 Python 实现类"""
    def decorator(cls: Type):
        _IB_TYPE_TO_CLASS[name] = cls
        return cls
    return decorator

def get_ib_implementation(name: str) -> Any:
    """获取指定类型名称对应的 Python 实现类"""
    return _IB_TYPE_TO_CLASS.get(name)

def get_all_registered_types() -> Dict[str, Type]:
    """获取所有已注册的类型映射"""
    return _IB_TYPE_TO_CLASS.copy()
