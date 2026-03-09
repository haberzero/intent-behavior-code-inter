from typing import Any, List, Dict, Optional, Callable
from .kernel import IbObject, IbClass, IbNativeFunction, IbNone
from core.foundation.registry import Registry
from core.domain.types import descriptors as uts

class IbInteger(IbObject):
    """
    包装 Python 原生 int 的 IBC 对象。
    实现小整数驻留 (Interning) 以优化性能。
    """
    __slots__ = ('value',)
    
    # 小整数缓存 (-5 到 256)
    _cache: Dict[int, 'IbInteger'] = {}

    def __init__(self, value: int, ib_class: Optional[IbClass] = None):
        reg = ib_class.registry if ib_class else get_default_registry()
        super().__init__(ib_class or reg.get_class("int"))
        self.value = value

    @classmethod
    def from_native(cls, value: int, ib_class: Optional[IbClass] = None) -> 'IbInteger':
        """小整数驻留工厂方法 (注意：目前 cache 仍是全局的，未来可考虑移动到 Registry)"""
        if -5 <= value <= 256:
            if value not in cls._cache:
                cls._cache[value] = cls(value, ib_class=ib_class)
            return cls._cache[value]
        return cls(value, ib_class=ib_class)

    def to_native(self, memo=None) -> int:
        return self.value

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

    def __init__(self, value: float, ib_class: Optional[IbClass] = None):
        reg = ib_class.registry if ib_class else get_default_registry()
        super().__init__(ib_class or reg.get_class("float"))
        self.value = value

    def to_native(self, memo=None) -> float:
        return self.value

    def serialize_for_debug(self) -> Dict[str, Any]:
        return {"type": "Float", "value": self.value}

    def __repr__(self):
        return f"Float({self.value})"

class IbString(IbObject):
    """
    包装 Python 原生 str 的 IBC 对象。
    """
    __slots__ = ('value',)

    def __init__(self, value: str, ib_class: Optional[IbClass] = None):
        reg = ib_class.registry if ib_class else get_default_registry()
        super().__init__(ib_class or reg.get_class("str"))
        self.value = value

    def to_native(self, memo=None) -> str:
        return self.value

    def serialize_for_debug(self) -> Dict[str, Any]:
        return {"type": "String", "value": self.value}

    def __repr__(self):
        return f"String('{self.value}')"

class IbList(IbObject):
    """
    包装 Python 原生 list 的 IBC 对象。
    """
    __slots__ = ('elements',)

    def __init__(self, elements: List[IbObject], ib_class: Optional[IbClass] = None):
        reg = ib_class.registry if ib_class else get_default_registry()
        super().__init__(ib_class or reg.get_class("list"))
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

class IbDict(IbObject):
    """
    包装 Python 原生 dict 的 IBC 对象。
    """
    def __init__(self, fields: Dict[str, IbObject], ib_class: Optional[IbClass] = None):
        reg = ib_class.registry if ib_class else get_default_registry()
        super().__init__(ib_class or reg.get_class("dict"))
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
        old_intents = list(self.interpreter.context.intent_stack)
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
