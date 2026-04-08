from typing import Optional, Dict, Any, Tuple

class IbEnumValue:
    """
    枚举值的包装对象。
    
    用于 LLM 返回枚举值时，封装枚举值名称，支持与字符串和枚举对象的比较。
    """
    
    def __init__(self, enum_name: str, enum_class_name: Optional[str] = None):
        self._enum_name = enum_name
        self._enum_class_name = enum_class_name
    
    @property
    def enum_name(self) -> str:
        return self._enum_name
    
    @property
    def enum_class_name(self) -> str:
        return self._enum_class_name or "Enum"
    
    def to_native(self) -> str:
        return self._enum_name
    
    def __repr__(self) -> str:
        if self._enum_class_name:
            return f"{self._enum_class_name}.{self._enum_name}"
        return self._enum_name
    
    def __str__(self) -> str:
        return self._enum_name
    
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, IbEnumValue):
            return self._enum_name == other._enum_name
        if isinstance(other, str):
            return self._enum_name.upper() == other.upper()
        return False
    
    def __hash__(self) -> int:
        return hash(self._enum_name)


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
    
    def to_native(self) -> str:
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
        if isinstance(other, IbEnumValue):
            return self._enum_name == other.enum_name
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
        if target_class.name in ("str", "any"):
            return self._ib_class.registry.box(self._enum.enum_name)
        if target_class.name == "int":
            member_names = list(self._ib_class.members.keys())
            builtin_names = {'to_bool', 'to_list', 'len', 'cast_to', '__getitem__', '__setitem__',
                           'sort', 'pop', 'append', 'clear', '__eq__', '__init__'}
            idx = 0
            for name in member_names:
                if name.startswith('_') or name in builtin_names:
                    continue
                if name == self._enum.enum_name:
                    return self._ib_class.registry.box(idx)
                idx += 1
            return self._ib_class.registry.box(0)
        if target_class.name == "bool":
            return self._ib_class.registry.box(1)
        return self
    
    def __to_prompt__(self) -> str:
        return self._enum.enum_name
    
    def receive(self, message: str, args: list) -> 'IbObject':
        if message == 'cast_to' and args:
            return self.cast_to(args[0])
        return self._ib_class.registry.box(self._enum.enum_name)
    
    def __repr__(self) -> str:
        return f"IbEnumAdapter({self._enum.enum_name})"
