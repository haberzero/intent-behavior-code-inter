from typing import Optional, Dict, Any

class IbEnum:
    """
    枚举值的运行时表示。
    
    IbEnum 存储枚举值的名称，并提供与 IBCI 对象系统的交互接口。
    """
    
    def __init__(self, enum_name: str):
        self._enum_name = enum_name
    
    @property
    def enum_name(self) -> str:
        return self._enum_name
    
    def __repr__(self) -> str:
        return self._enum_name
    
    def __str__(self) -> str:
        return self._enum_name
    
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, IbEnum):
            return self._enum_name == other._enum_name
        if isinstance(other, str):
            return self._enum_name == other
        return False
    
    def __hash__(self) -> int:
        return hash(self._enum_name)


class IbEnumAdapter:
    """
    IBCI 对象适配器：将 IbEnum 适配为 IbObject 接口。
    
    这个类允许 IbEnum 在 IBCI 运行时系统中使用。
    """
    
    def __init__(self, enum_instance: IbEnum, ib_class: 'IbClass'):
        self._enum = enum_instance
        self._ib_class = ib_class
    
    @property
    def ib_class(self) -> 'IbClass':
        return self._ib_class
    
    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        return self._enum.enum_name
    
    def to_bool(self) -> 'IbObject':
        return self._ib_class.registry.box(1)
    
    def cast_to(self, target_class: 'IbClass') -> 'IbObject':
        if target_class.name == "str":
            return self._ib_class.registry.box(self._enum.enum_name)
        if target_class.name == "int":
            return self._ib_class.registry.box(0)
        if target_class.name == "bool":
            return self._ib_class.registry.box(1)
        return self
    
    def __to_prompt__(self) -> str:
        return self._enum.enum_name
    
    def receive(self, message: str, args: list) -> 'IbObject':
        return self._ib_class.registry.box(self._enum.enum_name)
    
    def __repr__(self) -> str:
        return f"IbEnumAdapter({self._enum.enum_name})"
