from typing import Any, List, Dict, Optional, Callable
from core.runtime.interfaces import IIbBehavior
from .kernel import IbObject, IbClass, IbNativeFunction, IbNone
from core.foundation.registry import Registry
from core.runtime.support.converters import _cast_numeric_to_native, _cast_string_to_native
from core.domain.issue import InterpreterError

from core.domain.types import descriptors as uts

from .type_registry import register_ib_type

@register_ib_type("int")
class IbInteger(IbObject):
    """
    包装 Python 原生 int 的 IBC 对象。
    实现小整数驻留 (Interning) 以优化性能。
    现在驻留缓存已移动到 Registry 实例中，实现引擎隔离。
    """
    __slots__ = ('value',)
    
    def __init__(self, value: int, ib_class: IbClass):
        super().__init__(ib_class)
        self.value = value

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
        return self.ib_class.registry.box(1 if self.value != 0 else 0)

    def to_list(self) -> IbObject:
        return self.ib_class.registry.box(list(range(self.value)))

    def cast_to(self, target_class: Any) -> IbObject:
        target_desc = target_class.descriptor if hasattr(target_class, 'descriptor') else None
        res_val = _cast_numeric_to_native(self.value, target_desc)
        return self.ib_class.registry.box(res_val)

    def serialize_for_debug(self) -> Dict[str, Any]:
        # [IES 2.1 Refactor] 强制从 ib_class.name 获取类型标签，消除硬编码
        return {"type": self.ib_class.name, "value": self.value}

    def __repr__(self):
        return f"Integer({self.value})"

    # --- [IES 2.1] 自动化运算符绑定支持 ---
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

    def __ne__(self, other):
        return not self.__eq__(other)

@register_ib_type("float")
class IbFloat(IbObject):
    """
    包装 Python 原生 float 的 IBC 对象。
    """
    __slots__ = ('value',)

    def __init__(self, value: float, ib_class: IbClass):
        super().__init__(ib_class)
        self.value = value

    def to_native(self, memo=None) -> float:
        return self.value

    def to_bool(self) -> IbObject:
        return self.ib_class.registry.box(1 if self.value != 0.0 else 0)

    def cast_to(self, target_class: Any) -> IbObject:
        target_desc = target_class.descriptor if hasattr(target_class, 'descriptor') else None
        res_val = _cast_numeric_to_native(self.value, target_desc)
        return self.ib_class.registry.box(res_val)

    def serialize_for_debug(self) -> Dict[str, Any]:
        return {"type": self.ib_class.name, "value": self.value}

    def __repr__(self):
        return f"Float({self.value})"

    # --- [IES 2.1] 自动化运算符绑定支持 ---
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

@register_ib_type("str")
class IbString(IbObject):
    """
    包装 Python 原生 str 的 IBC 对象。
    """
    __slots__ = ('value',)

    def __init__(self, value: str, ib_class: IbClass):
        super().__init__(ib_class)
        self.value = value

    def to_native(self, memo=None) -> str:
        return self.value

    def len(self) -> IbObject:
        return self.ib_class.registry.box(len(self.value))

    def to_bool(self) -> IbObject:
        return self.ib_class.registry.box(1 if self.value.strip() else 0)

    def cast_to(self, target_class: Any) -> IbObject:
        target_desc = target_class.descriptor if hasattr(target_class, 'descriptor') else None
        res_val = _cast_string_to_native(self.value, target_desc)
        return self.ib_class.registry.box(res_val)

    def serialize_for_debug(self) -> Dict[str, Any]:
        return {"type": self.ib_class.name, "value": self.value}

    def __repr__(self):
        return f"String('{self.value}')"

    # --- [IES 2.1] 自动化运算符绑定支持 ---
    def __add__(self, other: IbObject) -> Any:
        if other.ib_class.name != "str":
             raise InterpreterError(f"TypeError: Cannot concatenate 'str' and '{other.ib_class.name}'")
        return self.value + other.to_native()
    
    def __eq__(self, other: IbObject) -> bool: return self.value == other.to_native()
    def __ne__(self, other: IbObject) -> bool: return self.value != other.to_native()

@register_ib_type("list")
class IbList(IbObject):
    """
    包装 Python 原生 list 的 IBC 对象。
    """
    __slots__ = ('elements',)

    def __init__(self, elements: List[IbObject], ib_class: IbClass):
        super().__init__(ib_class)
        self.elements = elements

    def to_native(self, memo=None) -> List[Any]:
        if memo is None: memo = {}
        if id(self) in memo: return memo[id(self)]
        
        res = []
        memo[id(self)] = res
        for e in self.elements:
            res.append(e.to_native(memo) if isinstance(e, IbObject) else e)
        return res

    def serialize_for_debug(self) -> Dict[str, Any]:
        return {
            "type": self.ib_class.name, 
            "value": [e.serialize_for_debug() for e in self.elements]
        }

    def __repr__(self):
        return f"List({self.elements})"

    def pop(self) -> IbObject:
        if not self.elements:
            raise InterpreterError("IndexError: pop from empty list")
        return self.elements.pop()

    def clear(self) -> IbObject:
        self.elements.clear()
        return self.ib_class.registry.get_none()

    def append(self, item: IbObject) -> IbObject:
        self.elements.append(item)
        return self.ib_class.registry.get_none()

    def len(self) -> IbObject:
        return self.ib_class.registry.box(len(self.elements))

    def __getitem__(self, key: Any) -> IbObject:
        idx = key.to_native() if hasattr(key, 'to_native') else key
        return self.elements[idx]

    def __setitem__(self, key: Any, val: IbObject) -> None:
        idx = key.to_native() if hasattr(key, 'to_native') else key
        self.elements[idx] = val

    def sort(self) -> IbObject:
        self.elements.sort(key=lambda x: x.to_native())
        return self.ib_class.registry.get_none()

@register_ib_type("dict")
class IbDict(IbObject):
    """
    包装 Python 原生 dict 的 IBC 对象。
    """
    def __init__(self, fields: Dict[str, IbObject], ib_class: IbClass):
        super().__init__(ib_class)
        self.fields = fields

    def to_native(self, memo=None) -> Dict[str, Any]:
        if memo is None: memo = {}
        if id(self) in memo: return memo[id(self)]
        
        res = {}
        memo[id(self)] = res
        for k, v in self.fields.items():
            res[k] = v.to_native(memo) if isinstance(v, IbObject) else v
        return res

    def serialize_for_debug(self) -> Dict[str, Any]:
        return {
            "type": self.ib_class.name,
            "value": {k: v.serialize_for_debug() if isinstance(v, IbObject) else v for k, v in self.fields.items()}
        }

    def __repr__(self):
        return f"Dict({self.fields})"

    def keys(self) -> IbObject:
        # 返回 IbList 包装的原生 key 列表
        # 注意：这里的 key 已经是原生类型（通常是 str）
        # 我们需要将其装箱
        native_keys = list(self.fields.keys())
        return self.ib_class.registry.box(native_keys)

    def values(self) -> IbObject:
        # 返回 IbList 包装的值列表
        return self.ib_class.registry.box(list(self.fields.values()))

    def len(self) -> IbObject:
        return self.ib_class.registry.box(len(self.fields))

    def __getitem__(self, key: Any) -> IbObject:
        k = key.to_native() if hasattr(key, 'to_native') else key
        return self.fields[k]

    def __setitem__(self, key: Any, val: IbObject) -> None:
        k = key.to_native() if hasattr(key, 'to_native') else key
        self.fields[k] = val

    def get(self, key: Any, default: Optional[IbObject] = None) -> IbObject:
        k = key.to_native() if hasattr(key, 'to_native') else key
        if k in self.fields:
            return self.fields[k]
        return default or self.ib_class.registry.get_none()

    def __iter__(self):
        return iter(self.fields)

    def __contains__(self, key):
        # 支持 IbString 或原生 string key
        native_key = key.to_native() if isinstance(key, IbObject) else key
        return native_key in self.fields

    def __getitem__(self, key):
        native_key = key.to_native() if isinstance(key, IbObject) else key
        return self.fields[native_key]

@register_ib_type("behavior")
class IbBehavior(IbObject, IIbBehavior):
    """
    延迟执行的行为对象 (~...~)。
    """
    def __init__(self, node_uid: str, captured_intents: List[Any], ib_class: IbClass, expected_type: Optional[str] = None):
        """
        [IES 2.0 Architectural Update] IbBehavior 现在是纯粹的数据描述符。
        不再持有 interpreter 引用，执行逻辑已剥离至 LLMExecutor。
        """
        super().__init__(ib_class)
        self.node = node_uid
        self.captured_intents = captured_intents
        self.expected_type = expected_type
        self._cache: Optional[IbObject] = None

    def value(self):
        # 此时必须由外部调用 LLMExecutor.execute_behavior_object 才能获取真实值
        # 这是一个被动描述符，不再支持主动 value 访问（除非已缓存）
        if self._cache: return self._cache.to_native()
        raise RuntimeError("Behavior is not executed. Please use LLMExecutor to run it.")

    def to_native(self) -> Any:
        if self._cache: return self._cache.to_native()
        return self

    def __to_prompt__(self) -> str:
        # 如果已执行则返回结果，否则返回节点描述
        if self._cache: return self._cache.__to_prompt__()
        return f"<Behavior {self.node}>"

    def __repr__(self):
        return f"<Behavior {self.node}>"

    def serialize_for_debug(self) -> Dict[str, Any]:
        return {
            "type": self.ib_class.name,
            "node_uid": self.node,
            "captured_intents": [str(i) for i in self.captured_intents],
            "expected_type": self.expected_type
        }

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """不再支持主动调用，必须由引擎调度"""
        raise RuntimeError("Behavior cannot execute itself. Use LLMExecutor.execute_behavior_object.")

    def receive(self, message: str, args: List[IbObject]) -> IbObject:
        """
        [IES 2.1 Resilience] 行为对象的消息处理。
        允许查询元数据，仅在尝试“执行行为本身”且无上下文时才抛出异常。
        """
        if self._cache: return self._cache.receive(message, args)
        
        # 允许查询元数据或基本属性，防止调试器崩溃
        if message in ("__get_metadata__", "__to_prompt__", "node_uid"):
            return self.ib_class.registry.box(str(self))
            
        raise RuntimeError(f"Behavior '{self.node}' is not executed. Cannot process message '{message}'.")
