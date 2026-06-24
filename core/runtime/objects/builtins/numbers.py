from typing import Any, Dict
from ..kernel import IbObject, IbValue, IbClass
from core.runtime.support.converters import _cast_numeric_to_native
from ..ib_type_mapping import register_ib_type

@register_ib_type("int")
class IbInteger(IbValue):
    """
    包装 Python 原生 int 的 IBC 对象。
    实现小整数驻留 (Interning) 以优化性能。
    现在驻留缓存已移动到 Registry 实例中，实现引擎隔离。
    """
    __slots__ = ()

    def __init__(self, value: int, ib_class: IbClass):
        super().__init__(ib_class, payload=value)

    @classmethod
    def from_native(cls, value: int, ib_class: IbClass) -> 'IbInteger':
        """小整数驻留工厂方法"""
        cache = ib_class.registry.get_int_cache()
        
        if -5 <= value <= 256:
            if value not in cache:
                cache[value] = cls(value, ib_class=ib_class)
            return cache[value]
        return cls(value, ib_class=ib_class)

    def to_native(self, memo=None) -> int:
        return self.value

    def to_bool(self) -> IbObject:
        return self.ib_class.registry.box(self.value != 0)

    def to_list(self) -> IbObject:
        return self.ib_class.registry.box(list(range(self.value)))

    def cast_to(self, target_class: Any) -> IbObject:
        target_desc = target_class.spec if hasattr(target_class, 'spec') else None
        res_val = _cast_numeric_to_native(self.value, target_desc)
        return self.ib_class.registry.box(res_val)

    def serialize_for_debug(self) -> Dict[str, Any]:
        # 强制从 ib_class.name 获取类型标签，消除硬编码
        return {"type": self.ib_class.name, "value": self.value}

    def __repr__(self):
        return f"Integer({self.value})"

    # ---  自动化运算符绑定支持 ---
    def __add__(self, other: IbObject) -> Any: return self.value + other.to_native()
    def __sub__(self, other: IbObject) -> Any: return self.value - other.to_native()
    def __mul__(self, other: IbObject) -> Any: return self.value * other.to_native()
    def __truediv__(self, other: IbObject) -> Any: 
        b = other.to_native()
        return self.value // b if isinstance(b, int) else self.value / b
    def __floordiv__(self, other: IbObject) -> Any: return self.value // other.to_native()
    def __mod__(self, other: IbObject) -> Any: return self.value % other.to_native()
    def __pow__(self, other: IbObject) -> Any: return self.value ** other.to_native()
    def __and__(self, other: IbObject) -> Any: return self.value & other.to_native()
    def __or__(self, other: IbObject) -> Any: return self.value | other.to_native()
    def __xor__(self, other: IbObject) -> Any: return self.value ^ other.to_native()
    def __lshift__(self, other: IbObject) -> Any: return self.value << other.to_native()
    def __rshift__(self, other: IbObject) -> Any: return self.value >> other.to_native()
    def __invert__(self) -> Any: return ~self.value
    def __neg__(self) -> Any: return -self.value
    def __pos__(self) -> Any: return +self.value

    def __lt__(self, other: IbObject) -> bool: return self.value < other.to_native()
    def __le__(self, other: IbObject) -> bool: return self.value <= other.to_native()
    def __gt__(self, other: IbObject) -> bool: return self.value > other.to_native()
    def __ge__(self, other: IbObject) -> bool: return self.value >= other.to_native()
    
    def __eq__(self, other):
        if isinstance(other, IbInteger):
            return self.value == other.value
        if isinstance(other, (int, bool)):
            return self.value == int(other)
        if isinstance(other, IbObject):
            return self.value == other.to_native()
        return False

    def __hash__(self):
        return hash(self.value)

    def __ne__(self, other):
        return not self.__eq__(other)

@register_ib_type("bool")
class IbBool(IbValue):
    """
    包装 Python 原生 bool 的 IBC 对象。
    """
    __slots__ = ()

    def __init__(self, value: bool, ib_class: IbClass):
        super().__init__(ib_class, payload=value)

    def to_native(self, memo=None) -> bool:
        return self.value

    def to_int(self) -> int:
        return 1 if self.value else 0

    def __eq__(self, other):
        if isinstance(other, IbBool):
            return self.value == other.value
        if hasattr(other, 'to_native'):
            return self.value == other.to_native()
        return False

    def __hash__(self):
        return hash(self.value)

    def __bool__(self):
        return self.value

@register_ib_type("float")
class IbFloat(IbValue):
    """
    包装 Python 原生 float 的 IBC 对象。
    """
    __slots__ = ()

    def __init__(self, value: float, ib_class: IbClass):
        super().__init__(ib_class, payload=value)

    def to_native(self, memo=None) -> float:
        return self.value

    def to_bool(self) -> IbObject:
        return self.ib_class.registry.box(self.value != 0.0)

    def cast_to(self, target_class: Any) -> IbObject:
        target_desc = target_class.spec if hasattr(target_class, 'spec') else None
        res_val = _cast_numeric_to_native(self.value, target_desc)
        return self.ib_class.registry.box(res_val)

    def serialize_for_debug(self) -> Dict[str, Any]:
        return {"type": self.ib_class.name, "value": self.value}

    def __repr__(self):
        return f"Float({self.value})"

    # ---  自动化运算符绑定支持 ---
    def __add__(self, other: IbObject) -> Any: return self.value + other.to_native()
    def __sub__(self, other: IbObject) -> Any: return self.value - other.to_native()
    def __mul__(self, other: IbObject) -> Any: return self.value * other.to_native()
    def __truediv__(self, other: IbObject) -> Any: return self.value / other.to_native()
    def __floordiv__(self, other: IbObject) -> Any: return self.value // other.to_native()
    def __mod__(self, other: IbObject) -> Any: return self.value % other.to_native()
    def __pow__(self, other: IbObject) -> Any: return self.value ** other.to_native()
    def __neg__(self) -> Any: return -self.value
    def __pos__(self) -> Any: return +self.value

    def __lt__(self, other: IbObject) -> bool: return self.value < other.to_native()
    def __le__(self, other: IbObject) -> bool: return self.value <= other.to_native()
    def __gt__(self, other: IbObject) -> bool: return self.value > other.to_native()
    def __ge__(self, other: IbObject) -> bool: return self.value >= other.to_native()
    def __eq__(self, other: IbObject) -> bool: return self.value == other.to_native()
    def __ne__(self, other: IbObject) -> bool: return self.value != other.to_native()
