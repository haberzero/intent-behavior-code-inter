from typing import Dict, Any, List, Optional, Callable, TYPE_CHECKING
from core.support.diagnostics.core_debugger import CoreModule, DebugLevel, core_debugger
from dataclasses import dataclass

if TYPE_CHECKING:
    from core.domain import ast as ast

@dataclass
class Type:
    """
    Unified Type Metadata.
    Base class for both compile-time type descriptions and runtime IbClass.
    """
    name: str

    def is_assignable_to(self, other: 'Type') -> bool:
        """
        Check if this type can be assigned to 'other' type.
        Implements the core type compatibility logic.
        """
        # UTS 核心逻辑：
        # 1. 引用相等
        if self is other:
            return True
            
        # 2. 名字匹配 (兼容占位符与正式 IbClass)
        if self.name == other.name:
            return True

        # 3. 动态类型兼容性
        if other.name in ("Any", "var"):
            return True
            
        # 4. 模块兼容性 (Any 可以赋值给 Module)
        if self.name == "Any" or self.name == "var":
            return True
            
        return False
        
    def resolve_member(self, name: str) -> Optional[Any]:
        """Resolve a member (attribute/method) by name."""
        return None

    def __str__(self):
        return self.name

@dataclass
class CallableType(Type):
    """Any callable object."""
    def __init__(self, name: str = "callable"):
        super().__init__(name)

    def is_assignable_to(self, other: 'Type') -> bool:
        if super().is_assignable_to(other):
            return True
        return other.name == "callable"

@dataclass
class ListType(Type):
    """Generic list type: list[T]"""
    element_type: Type
    def __init__(self, element_type: Type):
        # 注意：这里我们故意不使用 IbClass，因为 list[T] 是复合类型
        super().__init__(f"list[{element_type}]")
        self.element_type = element_type

    def is_assignable_to(self, other: Type) -> bool:
        if super().is_assignable_to(other):
            return True
        if other.name == "list": # 协变：list[int] 可以赋值给 list
             return True
        if isinstance(other, ListType):
            return self.element_type.is_assignable_to(other.element_type)
        return False

@dataclass
class DictType(Type):
    """Generic dict type: dict[K, V]"""
    key_type: Type
    value_type: Type
    def __init__(self, key_type: Type, value_type: Type):
        super().__init__(f"dict[{key_type}, {value_type}]")
        self.key_type = key_type
        self.value_type = value_type

    def is_assignable_to(self, other: Type) -> bool:
        if super().is_assignable_to(other):
            return True
        if other.name == "dict":
             return True
        if isinstance(other, DictType):
            return self.key_type.is_assignable_to(other.key_type) and \
                   self.value_type.is_assignable_to(other.value_type)
        return False

@dataclass
class FunctionType(Type):
    """A specific function signature."""
    param_types: List[Type]
    return_type: Type
    def __init__(self, param_types: List[Type], return_type: Type):
        super().__init__("function")
        self.param_types = param_types
        self.return_type = return_type

    def is_assignable_to(self, other: Type) -> bool:
        if super().is_assignable_to(other):
            return True
        if other.name == "callable":
            return True
        if isinstance(other, FunctionType):
            if not self.return_type.is_assignable_to(other.return_type):
                return False
            if len(self.param_types) != len(other.param_types):
                return False
            for p1, p2 in zip(self.param_types, other.param_types):
                if not p2.is_assignable_to(p1): 
                    return False
            return True
        return False

@dataclass
class ModuleType(Type):
    """A compiled IBCI module/package."""
    scope: Any 
    def __init__(self, scope: Any):
        super().__init__("module")
        self.scope = scope

    def resolve_member(self, name: str) -> Optional[Type]:
        if self.scope:
            symbol = self.scope.resolve(name)
            if symbol and symbol.type_info:
                return symbol.type_info
        return None

# UTS Singleton Instances / Type Placeholders
# 引导程序 initialize_builtin_classes 会用真正的 IbClass 覆盖这些
ANY_TYPE = Type("Any")
VOID_TYPE = Type("void")
INT_TYPE = Type("int")
FLOAT_TYPE = Type("float")
STR_TYPE = Type("str")
BOOL_TYPE = Type("bool")
VAR_TYPE = Type("var")

class IbObject:
    """
    IBC-Inter 对象基类 (一切皆对象)。
    模拟汇编层面的内存布局：持有一个指向 IbClass 的引用 (vptr) 和一个存储实例属性的字典。
    """
    __slots__ = ('ib_class', 'fields')

    def __init__(self, ib_class: 'IbClass'):
        self.ib_class = ib_class
        self.fields: Dict[str, Any] = {}

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        """
        消息分发核心 (模拟 jalr 指令)。
        集成 CoreDebugger 以记录全链路消息流。
        """
        core_debugger.trace(
            CoreModule.INTERPRETER, 
            DebugLevel.DATA, 
            f"[MSG] {self} received '{message}' with {args}"
        )

        method = self.ib_class.lookup_method(message)
        if method:
            return method.call(self, args)
        
        # 特殊内置协议：如果 message 是 __getattr__ 或 __setattr__ 且没有显式重写
        if message == '__getattr__':
            from core.foundation.builtins import IbNone, IbString # 假设已存在
            name = args[0].to_native()
            
            # 1. 优先查字段
            if name in self.fields:
                return self.fields[name]
                
            # 2. 其次查方法并返回绑定方法 (Bound Method)
            method = self.ib_class.lookup_method(name)
            if method:
                return IbBoundMethod(self, method)
                
            return IbNone()

        if message == '__setattr__':
            from core.foundation.builtins import IbNone
            name = args[0].to_native()
            self.fields[name] = args[1]
            return IbNone()

        # 消息未找到，尝试调用 method_missing 协议 (Spec 扩展支持)
        method_missing = self.ib_class.lookup_method('method_missing')
        if method_missing:
            # 包装原始消息名作为第一个参数
            from core.foundation.builtins import IbString # 假设已存在
            return method_missing.call(self, [IbString(message)] + args)

        raise AttributeError(f"Object of type '{self.ib_class.name}' has no method '{message}'")

    def __to_prompt__(self) -> str:
        """
        响应 Spec 协议：定义对象在 LLM 视角下的表现形式。
        """
        # 1. 优先尝试调用 IBC 层面定义的 __to_prompt__
        # 我们使用 receive 消息传递，这本身就是 OO 的体现
        try:
            res = self.receive('__to_prompt__', [])
            return str(res.value) if hasattr(res, 'value') else str(res)
        except:
            # 2. 默认实现 (对齐 Spec)
            return f"<Instance of {self.ib_class.name}>"

    def serialize_for_debug(self) -> Dict[str, Any]:
        """
        为 IDBG 等调试组件提供的序列化方法。
        将 IbObject 转换为 Python 原生字典。
        """
        res = {k: (v.serialize_for_debug() if isinstance(v, IbObject) else v) 
                   for k, v in self.fields.items()}
        # 附加元数据 (以 __ 开头以免与字段冲突)
        res["__type__"] = self.ib_class.name
        res["__repr__"] = self.__repr__()
        return res

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        """UTS 协议：将对象转为 Python 原生对象。默认返回自身。"""
        return self

    def __repr__(self):
        return f"<{self.ib_class.name} object at {hex(id(self))}>"

class IbNativeObject(IbObject):
    """
    包装 Python 原生对象的 IBC 对象。
    用于桥接 Python 扩展和标准库。
    """
    def __init__(self, py_obj: Any):
        from core.foundation.bootstrapper import Bootstrapper
        super().__init__(Bootstrapper.get_class("Object"))
        self.py_obj = py_obj

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        from core.foundation.bootstrapper import Bootstrapper
        from core.foundation.builtins import IbNone
        
        if message == '__getattr__':
            name = args[0].to_native()
            if hasattr(self.py_obj, name):
                return Bootstrapper.box(getattr(self.py_obj, name))
            return IbNone()
            
        if message == '__call__':
            if callable(self.py_obj):
                native_args = [arg.to_native() for arg in args]
                return Bootstrapper.box(self.py_obj(*native_args))
        
        return super().receive(message, args)

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        return self.py_obj

    def __repr__(self):
        return f"<NativeObject {self.py_obj}>"

class IbModule(IbObject):
    """
    IBC-Inter 模块对象。
    持有一个作用域 (Scope)，并根据 UTS 协议通过消息传递暴露成员。
    """
    def __init__(self, name: str, scope: Any):
        from core.foundation.bootstrapper import Bootstrapper
        # 模块类在引导阶段由 Bootstrapper 绑定
        super().__init__(Bootstrapper.get_class("Module") or Bootstrapper.ObjectClass)
        self.name = name
        self.scope = scope

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        if message == '__getattr__':
            from core.foundation.builtins import IbNone
            name = args[0].to_native()
            try:
                # 从模块作用域中查找变量
                return self.scope.get(name)
            except (KeyError, AttributeError):
                return IbNone()
        
        return super().receive(message, args)

    def __repr__(self):
        return f"<Module '{self.name}'>"

class IbClass(IbObject, Type):
    """
    IBC-Inter 类对象 (元对象)。
    同时继承自 IbObject (一切皆对象) 和 Type (统一类型元数据)。
    模拟虚表 (vtable)：存储方法名到 IbFunction 的映射。
    """
    __slots__ = ('name', 'methods', 'parent', 'default_fields', 'member_types')

    def __init__(self, name: str, parent: Optional['IbClass'] = None):
        # 类的元类在引导阶段由 Bootstrapper 绑定 (TypeClass)
        # 这里暂时初始化为 None，由引导程序修正
        IbObject.__init__(self, None) 
        Type.__init__(self, name)
        self.methods: Dict[str, 'IbFunction'] = {}
        self.parent = parent
        self.default_fields: Dict[str, Any] = {}
        # UTS: 存储成员的类型信息 (用于编译期检查)
        self.member_types: Dict[str, Type] = {}

    def resolve_member(self, name: str) -> Optional[Any]:
        """
        UTS 协议：统一成员解析。
        1. 优先查找成员类型信息 (编译期路径)。
        2. 如果没有，查找实际方法 (运行期路径)。
        """
        # 编译期：查找类型定义
        if name in self.member_types:
            return self.member_types[name]
            
        # 向上查找
        if self.parent:
            res = self.parent.resolve_member(name)
            if res: return res
            
        # 运行期兜底：返回 IbFunction
        return self.lookup_method(name)

    def define_member(self, name: str, member_type: Type):
        """UTS: 定义类成员的类型元数据"""
        self.member_types[name] = member_type

    def is_assignable_to(self, other: Type) -> bool:
        """
        UTS 协议实现：检查当前类是否可以赋值给目标类型。
        取代了旧的 can_assign_to。
        """
        # 1. 基础规则 (引用相等、名字相等、Any 兼容性)
        if super().is_assignable_to(other):
            return True
            
        # 2. 继承关系检查
        if self.parent and self.parent.is_assignable_to(other):
            return True
            
        # 3. [SPECIAL] 增加内置类型的兼容性规则
        if self.name == "int" and other.name == "bool":
            return True
        if self.name in ("Function", "NativeFunction", "AnonymousLLMFunction", "behavior") and other.name == "callable":
            return True
            
        return False

    def lookup_method(self, name: str) -> Optional['IbFunction']:
        """沿继承链查找方法 (模拟虚表查找逻辑)"""
        if name in self.methods:
            return self.methods[name]
        if self.parent:
            return self.parent.lookup_method(name)
        return None

    def can_assign_to(self, other: 'IbClass') -> bool:
        """向后兼容接口，内部调用 UTS 协议"""
        return self.is_assignable_to(other)

    def register_method(self, name: str, method: 'IbFunction'):
        """向虚表中注册方法"""
        self.methods[name] = method

    def instantiate(self, args: List[IbObject]) -> IbObject:
        """实例化类对象"""
        instance = IbObject(self)
        # 初始化默认字段
        instance.fields = self.default_fields.copy()
        
        # 调用构造函数 (如果存在)
        init_method = self.lookup_method('__init__')
        if init_method:
            init_method.call(instance, args)
            
        return instance

    def __repr__(self):
        return f"<Class '{self.name}'>"

class IbFunction(IbObject):
    """可调用对象基类"""
    def __init__(self, ib_class: 'IbClass'):
        super().__init__(ib_class)

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        raise NotImplementedError()

class IbNativeFunction(IbFunction):
    """
    包装 Python 原生函数的 IBC 函数。
    用于引导阶段注入基础运算（如 int.__add__）。
    """
    def __init__(self, py_func: Callable, unbox_args: bool = False, is_method: bool = False, ib_class: Optional['IbClass'] = None):
        # 默认使用 Function 类，由 Bootstrapper 绑定
        from core.foundation.bootstrapper import Bootstrapper
        super().__init__(ib_class or Bootstrapper.get_class("Function"))
        self.py_func = py_func
        self.unbox_args = unbox_args
        self.is_method = is_method

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        # 处理参数解包
        final_args = args
        if self.unbox_args:
            final_args = [arg.to_native() if hasattr(arg, 'to_native') else arg for arg in args]

        # 如果是方法，总是注入 receiver 作为 self
        from core.foundation.bootstrapper import Bootstrapper
        if self.is_method:
             res = self.py_func(receiver, *final_args)
        else:
             res = self.py_func(*final_args)
             
        # 统一装箱返回结果
        return Bootstrapper.box(res)

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        # 允许访问底层 Python 对象的属性 (支持模块/扩展能力的混合调用)
        if message == '__getattr__':
            name = args[0].to_native()
            if hasattr(self.py_func, name):
                from core.foundation.bootstrapper import Bootstrapper
                return Bootstrapper.box(getattr(self.py_func, name))

        return super().receive(message, args)

    def __getattr__(self, name):
        """允许访问底层 Python 对象的属性 (支持模块/扩展能力的混合调用)"""
        return getattr(self.py_func, name)

class IbBoundMethod(IbFunction):
    """绑定了接收者的函数 (模拟 C++ 虚表调用的 this 绑定)"""
    def __init__(self, receiver: IbObject, method: IbFunction):
        from core.foundation.bootstrapper import Bootstrapper
        super().__init__(Bootstrapper.get_class("Function"))
        self.receiver = receiver
        self.method = method

    def call(self, _receiver: IbObject, args: List[IbObject]) -> IbObject:
        # 忽略传入的 _receiver，使用绑定的 receiver
        return self.method.call(self.receiver, args)

    def __repr__(self):
        return f"<BoundMethod {self.method} bound to {self.receiver}>"

class IbNone(IbObject):
    """
    IBC-Inter 的空对象 (None)。
    单例模式。
    """
    _instance: Optional['IbNone'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IbNone, cls).__new__(cls)
            from core.foundation.bootstrapper import Bootstrapper
            cls._instance.ib_class = Bootstrapper.get_class("None")
            cls._instance.fields = {}
        return cls._instance

    def __init__(self):
        # 已经在 __new__ 中初始化
        pass

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        return None

    def __to_prompt__(self) -> str:
        return "null"

    def __repr__(self):
        return "null"

class IbUserFunction(IbFunction):
    """
    用户定义的 IBC 函数。
    """
    def __init__(self, node: 'ast.FunctionDef', interpreter: Any):
        from core.foundation.bootstrapper import Bootstrapper
        super().__init__(Bootstrapper.get_class("Function"))
        self.node = node
        self.interpreter = interpreter

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """执行用户定义的函数"""
        from .builtins import IbNone
        from .kernel import IbObject
        
        context = self.interpreter.context
        context.enter_scope()
        try:
            # 1. 绑定 self (如果是方法调用)
            if not isinstance(receiver, IbNone):
                context.define_variable("self", receiver)
            
            # 2. 绑定参数
            formal_params = self.node.args
            # 如果第一个形参是 explicit 'self'，跳过它，因为上面已经绑定了 receiver
            if formal_params and formal_params[0].arg == "self":
                formal_params = formal_params[1:]
            
            for i, arg_def in enumerate(formal_params):
                if i < len(args):
                    context.define_variable(arg_def.arg, args[i])
            
            # 3. 执行主体
            result = IbNone()
            from core.runtime.interpreter.interpreter import ReturnException
            try:
                for stmt in self.node.body:
                    result = self.interpreter.visit(stmt)
            except ReturnException as e:
                return e.value
                
            return result
        finally:
            context.exit_scope()

    def __repr__(self):
        return f"<Function '{self.node.name}'>"

class IbLLMFunction(IbFunction):
    """
    LLM 驱动的函数。
    其执行逻辑委托给 LLMExecutor。
    """
    def __init__(self, node: 'ast.LLMFunctionDef', executor: Any, interpreter: Any):
        from core.foundation.bootstrapper import Bootstrapper
        super().__init__(Bootstrapper.get_class("Function"))
        self.node = node
        self.executor = executor
        self.interpreter = interpreter

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        res = self.executor.execute_llm_function(self.node, receiver, args, self.interpreter.context)
        from core.foundation.bootstrapper import Bootstrapper
        return Bootstrapper.box(res)

    def __repr__(self):
        return f"<LLMFunction '{self.node.name}'>"
