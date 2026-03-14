from typing import Any, List, Dict, Optional, Callable
from .kernel import IbObject, IbClass, IbNativeFunction, IbNone
from core.foundation.registry import Registry
from core.runtime.support.converters import _cast_numeric_to_native, _cast_string_to_native
from core.domain.issue import InterpreterError

from core.domain.types import descriptors as uts

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
        return {"type": "Integer", "value": self.value}

    def __repr__(self):
        return f"Integer({self.value})"

    def __eq__(self, other):
        if isinstance(other, IbInteger):
            return self.value == other.value
        if isinstance(other, int):
            return self.value == other
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

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
        return {"type": "Float", "value": self.value}

    def __repr__(self):
        return f"Float({self.value})"

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
        return {"type": "String", "value": self.value}

    def __repr__(self):
        return f"String('{self.value}')"

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
            "type": "List", 
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
            "type": "IbDict",
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

class IbBehavior(IbObject):
    """
    延迟执行的行为对象 (~...~)。
    """
    def __init__(self, node_uid: str, interpreter: Any, captured_intents: List[Any], expected_type: Optional[str] = None):
        super().__init__(interpreter.registry.get_class("behavior"))
        self.node = node_uid
        self.interpreter = interpreter
        self.captured_intents = captured_intents
        self.expected_type = expected_type
        self._cache: Optional[IbObject] = None

    def _execute(self) -> IbObject:
        if self._cache is not None:
            return self._cache
            
        # 恢复捕获的意图栈和预期类型
        # [IES 2.0 Optimization] 支持 IntentNode 结构共享恢复
        old_intents = self.interpreter.context.intent_stack
        self.interpreter.context.intent_stack = self.captured_intents
        
        type_pushed = False
        if self.expected_type:
            self.interpreter.service_context.llm_executor.push_expected_type(self.expected_type)
            type_pushed = True
            
        try:
            res = self.interpreter.service_context.llm_executor.execute_behavior_expression(
                self.node, self.interpreter.context, captured_intents=self.captured_intents
            )
            self._cache = self.ib_class.registry.box(res)
            return self._cache
        finally:
            self.interpreter.context.intent_stack = old_intents
            if type_pushed:
                self.interpreter.service_context.llm_executor.pop_expected_type()

    @property
    def value(self):
        res = self._execute()
        return res.to_native()

    def to_native(self) -> Any:
        return self._execute().to_native()

    def __to_prompt__(self) -> str:
        return self._execute().__to_prompt__()

    def __repr__(self):
        desc = "".join([str(s) for s in self.node.segments])
        return f"<Behavior @~{desc[:20]}...~>"

    def serialize_for_debug(self) -> Dict[str, Any]:
        return {
            "__type__": "Behavior",
            "__repr__": str(self),
            "captured_intents": [str(i) for i in self.captured_intents],
            "expected_type": self.expected_type
        }

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """支持函数调用协议 ()"""
        return self._execute()

    def receive(self, message: str, args: List[IbObject]) -> IbObject:
        # 如果是调用消息，执行行为
        if message == "__call__":
            return self._execute()
        # 其他消息（如 __add__）转发给执行后的结果
        return self._execute().receive(message, args)
