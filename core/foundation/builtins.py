from typing import Any, List, Dict, Optional, Callable
from .kernel import IbObject, IbClass, IbNativeFunction, IbNone
from .bootstrapper import Bootstrapper

class IbInteger(IbObject):
    """
    包装 Python 原生 int 的 IBC 对象。
    实现小整数驻留 (Interning) 以优化性能。
    """
    __slots__ = ('value',)
    
    # 小整数缓存 (-5 到 256)
    _cache: Dict[int, 'IbInteger'] = {}

    def __init__(self, value: int, ib_class: Optional[IbClass] = None):
        super().__init__(ib_class or Bootstrapper.get_class("int"))
        self.value = value

    @classmethod
    def from_native(cls, value: int) -> 'IbInteger':
        """小整数驻留工厂方法"""
        if -5 <= value <= 256:
            if value not in cls._cache:
                cls._cache[value] = cls(value)
            return cls._cache[value]
        return cls(value)

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
        super().__init__(ib_class or Bootstrapper.get_class("float"))
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
        super().__init__(ib_class or Bootstrapper.get_class("str"))
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
        super().__init__(ib_class or Bootstrapper.get_class("list"))
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
    def __init__(self, data: Dict[str, IbObject], ib_class: Optional[IbClass] = None):
        super().__init__(ib_class or Bootstrapper.get_class("dict"))
        self.fields = data

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
            "type": "Dict",
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
    def __init__(self, node: 'ast.BehaviorExpr', interpreter: Any, captured_intents: List['ast.IntentInfo'], expected_type: Optional[str] = None):
        super().__init__(Bootstrapper.get_class("behavior"))
        self.node = node
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
            self._cache = Bootstrapper.box(res)
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

# 初始化内置类 (由 Bootstrapper 调用)
def initialize_builtin_classes():
    Bootstrapper.initialize()
    
    # 1. 创建核心内置类 (对齐 Spec 中的类型名称)
    # 这些类将自动被 Bootstrapper 缓存并提供给 get_class
    integer_class = Bootstrapper.create_subclass("int")
    float_class = Bootstrapper.create_subclass("float")
    string_class = Bootstrapper.create_subclass("str")
    list_class = Bootstrapper.create_subclass("list")
    dict_class = Bootstrapper.create_subclass("dict")
    none_class = Bootstrapper.create_subclass("None")
    behavior_class = Bootstrapper.create_subclass("behavior")
    bool_class = Bootstrapper.create_subclass("bool")
    callable_class = Bootstrapper.create_subclass("callable")
    var_class = Bootstrapper.create_subclass("var")
    
    # 2. 同步 UTS 类型到 kernel 常量，确保编译器与运行时共享同一套真理
    import core.foundation.kernel as kernel
    kernel.INT_TYPE = integer_class
    kernel.FLOAT_TYPE = float_class
    kernel.STR_TYPE = string_class
    kernel.BOOL_TYPE = bool_class
    kernel.VOID_TYPE = none_class
    kernel.VAR_TYPE = var_class
    # ANY_TYPE 保持其特殊地位，但 var_class 在分配时与 ANY_TYPE 兼容
    
    # 3. 注册原生方法代理 (原语层)
    
    # Integer 运算
    integer_class.register_method('__to_prompt__', IbNativeFunction(lambda self: str(self.to_native()), is_method=True))
    integer_class.register_method('to_bool', IbNativeFunction(lambda self: 1 if self.to_native() != 0 else 0, is_method=True))
    integer_class.register_method('to_list', IbNativeFunction(
        lambda self: IbList([IbInteger.from_native(i) for i in range(self.to_native())]), is_method=True
    ))
    integer_class.register_method('__add__', IbNativeFunction(
        lambda self, other: _numeric_op(self, other, lambda a, b: a + b), is_method=True
    ))
    integer_class.register_method('__sub__', IbNativeFunction(
        lambda self, other: _numeric_op(self, other, lambda a, b: a - b), is_method=True
    ))
    integer_class.register_method('__mul__', IbNativeFunction(
        lambda self, other: _numeric_op(self, other, lambda a, b: a * b), is_method=True
    ))
    integer_class.register_method('__div__', IbNativeFunction(
        lambda self, other: _numeric_op(self, other, lambda a, b: a // b if isinstance(a, int) and isinstance(b, int) else a / b), is_method=True
    ))
    integer_class.register_method('__mod__', IbNativeFunction(
        lambda self, other: _numeric_op(self, other, lambda a, b: a % b), is_method=True
    ))
    integer_class.register_method('__and__', IbNativeFunction(
        lambda self, other: IbInteger.from_native(self.to_native() & other.to_native()), is_method=True
    ))
    integer_class.register_method('__or__', IbNativeFunction(
        lambda self, other: IbInteger.from_native(self.to_native() | other.to_native()), is_method=True
    ))
    integer_class.register_method('__xor__', IbNativeFunction(
        lambda self, other: IbInteger.from_native(self.to_native() ^ other.to_native()), is_method=True
    ))
    integer_class.register_method('__lshift__', IbNativeFunction(
        lambda self, other: IbInteger.from_native(self.to_native() << other.to_native()), is_method=True
    ))
    integer_class.register_method('__rshift__', IbNativeFunction(
        lambda self, other: IbInteger.from_native(self.to_native() >> other.to_native()), is_method=True
    ))
    integer_class.register_method('__invert__', IbNativeFunction(
        lambda self: IbInteger.from_native(~self.to_native()), is_method=True
    ))
    integer_class.register_method('__lt__', IbNativeFunction(
        lambda self, other: IbInteger.from_native(1 if self.to_native() < other.to_native() else 0), is_method=True
    ))
    integer_class.register_method('__le__', IbNativeFunction(
        lambda self, other: IbInteger.from_native(1 if self.to_native() <= other.to_native() else 0), is_method=True
    ))
    integer_class.register_method('__gt__', IbNativeFunction(
        lambda self, other: IbInteger.from_native(1 if self.to_native() > other.to_native() else 0), is_method=True
    ))
    integer_class.register_method('__ge__', IbNativeFunction(
        lambda self, other: IbInteger.from_native(1 if self.to_native() >= other.to_native() else 0), is_method=True
    ))
    integer_class.register_method('__eq__', IbNativeFunction(
        lambda self, other: _compare_op(self, other, lambda a, b: a == b), is_method=True
    ))
    integer_class.register_method('__ne__', IbNativeFunction(
        lambda self, other: _compare_op(self, other, lambda a, b: a != b), is_method=True
    ))
    
    float_class.register_method('__to_prompt__', IbNativeFunction(lambda self: str(self.to_native()), is_method=True))
    float_class.register_method('__add__', IbNativeFunction(
        lambda self, other: _numeric_op(self, other, lambda a, b: a + b), is_method=True
    ))
    float_class.register_method('__sub__', IbNativeFunction(
        lambda self, other: _numeric_op(self, other, lambda a, b: a - b), is_method=True
    ))
    float_class.register_method('__mul__', IbNativeFunction(
        lambda self, other: _numeric_op(self, other, lambda a, b: a * b), is_method=True
    ))
    float_class.register_method('__div__', IbNativeFunction(
        lambda self, other: _numeric_op(self, other, lambda a, b: a / b), is_method=True
    ))
    float_class.register_method('__lt__', IbNativeFunction(
        lambda self, other: IbInteger.from_native(1 if self.to_native() < other.to_native() else 0), is_method=True
    ))
    float_class.register_method('__le__', IbNativeFunction(
        lambda self, other: IbInteger.from_native(1 if self.to_native() <= other.to_native() else 0), is_method=True
    ))
    float_class.register_method('__gt__', IbNativeFunction(
        lambda self, other: IbInteger.from_native(1 if self.to_native() > other.to_native() else 0), is_method=True
    ))
    float_class.register_method('__ge__', IbNativeFunction(
        lambda self, other: IbInteger.from_native(1 if self.to_native() >= other.to_native() else 0), is_method=True
    ))
    float_class.register_method('__eq__', IbNativeFunction(
        lambda self, other: _compare_op(self, other, lambda a, b: a == b), is_method=True
    ))
    float_class.register_method('__ne__', IbNativeFunction(
        lambda self, other: _compare_op(self, other, lambda a, b: a != b), is_method=True
    ))

    # String 运算
    string_class.register_method('__to_prompt__', IbNativeFunction(lambda self: self.to_native(), is_method=True))
    string_class.register_method('__add__', IbNativeFunction(
        lambda self, other: IbString(str(self.to_native()) + (other.to_native() if not isinstance(other, IbObject) else str(other.receive("__to_prompt__", []).to_native()))), is_method=True
    ))
    string_class.register_method('cast_to', IbNativeFunction(
        lambda self, target_class: _cast_string_to(self, target_class), is_method=True
    ))

    # List 运算
    list_class.register_method('__to_prompt__', IbNativeFunction(
        lambda self: "[" + ", ".join(e.receive('__to_prompt__', []).to_native() for e in self.elements) + "]", 
        is_method=True
    ))
    list_class.register_method('to_list', IbNativeFunction(lambda self: self, is_method=True))
    list_class.register_method('append', IbNativeFunction(
        lambda self, item: self.elements.append(item) or IbNone(), is_method=True
    ))
    list_class.register_method('len', IbNativeFunction(
        lambda self: IbInteger.from_native(len(self.elements)), is_method=True
    ))
    list_class.register_method('sort', IbNativeFunction(
        lambda self: self.elements.sort(key=lambda x: x.to_native()) or IbNone(), is_method=True
    ))
    list_class.register_method('__getitem__', IbNativeFunction(
        lambda self, key: self.elements[key.to_native()], is_method=True
    ))
    list_class.register_method('__setitem__', IbNativeFunction(
        lambda self, key, val: self.elements.__setitem__(key.to_native(), val) or IbNone(), is_method=True
    ))

    # Dict 运算
    dict_class.register_method('__to_prompt__', IbNativeFunction(
        lambda self: "{" + ", ".join(f'"{k}": {v.receive("__to_prompt__", []).to_native()}' for k, v in self.fields.items()) + "}",
        is_method=True
    ))
    dict_class.register_method('get', IbNativeFunction(
        lambda self, key: self.fields.get(key.to_native(), IbNone()), is_method=True
    ))
    dict_class.register_method('__getitem__', IbNativeFunction(
        lambda self, key: self.fields[key.to_native()], is_method=True
    ))
    dict_class.register_method('__setitem__', IbNativeFunction(
        lambda self, key, val: self.fields.update({key.to_native(): val}) or IbNone(), is_method=True
    ))

def _numeric_op(self: IbObject, other: IbObject, op_func: Callable) -> IbObject:
    """处理数值运算并支持 promotion"""
    a = self.to_native()
    b = other.to_native()
    res = op_func(a, b)
    if isinstance(res, int): return IbInteger.from_native(res)
    if isinstance(res, float): return IbFloat(res)
    return IbObject(Bootstrapper.get_class("Object")) # Fallback

def _compare_op(self: IbObject, other: IbObject, op_func: Callable) -> IbObject:
    """处理比较运算"""
    a = self.to_native()
    b = other.to_native()
    try:
        res = op_func(a, b)
        return IbInteger.from_native(1 if res else 0)
    except:
        # 如果比较失败 (例如类型不兼容)，则 __eq__ 返回 False, __ne__ 返回 True
        # 这是一个简化的处理逻辑
        is_eq = (op_func(1, 1) == True) # 探测是 eq 还是 ne
        return IbInteger.from_native(0 if is_eq else 1)

def _cast_string_to(ib_str: IbString, target_class: IbClass) -> IbObject:
    """实现 Spec 中的自动类型转换策略，桥接 AI 模块逻辑"""
    val = ib_str.to_native().strip()
    if target_class.name == "int":
        return IbInteger.from_native(int(val))
    # ... 其他转换逻辑
    return ib_str # Fallback
