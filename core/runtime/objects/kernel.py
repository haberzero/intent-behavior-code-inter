from typing import Dict, Any, List, Optional, Callable, TYPE_CHECKING, Mapping
from core.foundation.registry import Registry
from core.domain.issue import InterpreterError
from core.runtime.exceptions import ReturnException
from core.foundation.diagnostics.core_debugger import CoreModule, DebugLevel, core_debugger
from core.domain.types.descriptors import TypeDescriptor, ANY_DESCRIPTOR as ANY_TYPE

if TYPE_CHECKING:
    from core.domain import ast as ast

class IbObject:
    """
    IBC-Inter 对象基类 (一切皆对象)。
    模拟汇编层面的内存布局：持有一个指向 IbClass 的引用 (vptr) 和一个存储实例属性的字典。
    """
    __slots__ = ('ib_class', 'fields')

    def __init__(self, ib_class: 'IbClass'):
        self.ib_class = ib_class
        self.fields: Mapping[str, Any] = {}

    @property
    def descriptor(self) -> TypeDescriptor:
        """获取对象的运行时类型描述符"""
        return self.ib_class.descriptor

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        """
        统一消息传递接口。
        所有属性访问和方法调用都通过此入口分发。
        """
        core_debugger.trace(CoreModule.INTERPRETER, DebugLevel.DATA, f"[MSG] {self} received '{message}' with {args}")
        
        # [IES 2.0] 内置系统消息拦截
        if message == '__call__' and hasattr(self, 'call'):
            return self.call(self.ib_class.registry.get_none(), args)
            
        if message == '__getattr__' and len(args) > 0:
            attr_name = args[0].to_native()
            # 优先查找实例字段
            if attr_name in self.fields:
                return self.fields[attr_name]
            # 降级查找类方法
            method = self.ib_class.lookup_method(attr_name)
            if method:
                # [FIX] 如果是方法，我们需要返回一个 BoundMethod 以便后续调用能正确传入 receiver
                return IbBoundMethod(self, method)

        # 2. 正常消息路由：查找类方法
        method = self.ib_class.lookup_method(message)
        if method:
            return method.call(self, args)
        
        # 消息未找到，尝试调用 method_missing 协议 (Spec 扩展支持)
        method_missing = self.ib_class.lookup_method('method_missing')
        if method_missing:
            # 包装原始消息名作为第一个参数
            return method_missing.call(self, [self.ib_class.registry.box(message)] + args)

        raise AttributeError(f"Object of type '{self.ib_class.name}' has no method '{message}'")

    def __to_prompt__(self) -> str:
        """
        响应 Spec 协议：定义对象在 LLM 视角下的表现形式。
        """
        try:
            res = self.receive('__to_prompt__', [])
            return str(res.value) if hasattr(res, 'value') else str(res)
        except:
            return f"<Instance of {self.ib_class.name}>"

    def serialize_for_debug(self) -> Mapping[str, Any]:
        """
        为 IDBG 等调试组件提供的序列化方法。
        将 IbObject 转换为 Python 原生字典。
        """
        res = {k: (v.serialize_for_debug() if isinstance(v, IbObject) else v) 
                   for k, v in self.fields.items()}
        res["__type__"] = self.ib_class.name
        res["__repr__"] = self.__repr__()
        return res

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        return self

    def __repr__(self):
        return f"<{self.ib_class.name} object at {hex(id(self))}>"

class IbNativeObject(IbObject):
    """
    包装 Python 原生对象的 IBC 对象。
    用于桥接 Python 扩展和标准库。
    """
    def __init__(self, py_obj: Any, ib_class: 'IbClass', vtable: Optional[Dict[str, Any]] = None, whitelist: Optional[List[str]] = None):
        super().__init__(ib_class)
        self.py_obj = py_obj
        # [IES 2.0] 显式持有虚表，消除对 py_obj 的动态属性依赖
        self.vtable = vtable if vtable is not None else getattr(py_obj, '_ibci_vtable', {})
        # [SECURITY] 属性访问白名单
        self.whitelist = whitelist if whitelist is not None else getattr(py_obj, '_ibci_whitelist', [])

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        # [IES 2.0 Native VTable] 优先从绑定的虚函数表中查找
        if message in self.vtable:
            attr = self.vtable[message]
            binding = getattr(attr, '_ibci_binding', None)
            if not binding and hasattr(attr, '__func__'):
                binding = getattr(attr.__func__, '_ibci_binding', None)
            
            # 执行调用
            if binding and getattr(binding, 'raw', False):
                return self.ib_class.registry.box(attr(*args))
            
            native_args = [a.to_native() if hasattr(a, 'to_native') else a for a in args]
            return self.ib_class.registry.box(attr(*native_args))

        # 2. 处理 __getattr__ 协议 (属性访问)
        if message == '__getattr__' and len(args) > 0:
            target_name = args[0].to_native()
            # 优先从 VTable 中查找 (例如将方法作为属性获取)
            if target_name in self.vtable:
                return self.ib_class.registry.box(self.vtable[target_name])
            
            # [SECURITY] 仅允许访问白名单中的属性，封死对 Python 私有属性的访问
            if target_name in self.whitelist:
                if hasattr(self.py_obj, target_name):
                    return self.ib_class.registry.box(getattr(self.py_obj, target_name))
            
            # [SECURITY] 如果是 __getattr__ 且白名单未通过，则明确拒绝访问
            raise AttributeError(f"NativeObject attribute '{target_name}' is not in whitelist or not found")

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
    def __init__(self, name: str, scope: Any, registry: Registry):
        super().__init__(registry.get_class("module") or registry.get_class("Object"))
        self.name = name
        self.scope = scope

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        # 1. 优先从模块作用域获取变量 (成员访问)
        try:
            return self.scope.get(message)
        except (KeyError, AttributeError):
            pass
            
        # 2. 特殊协议处理
        if message == '__getattr__':
            name = args[0].to_native()
            try:
                return self.scope.get(name)
            except (KeyError, AttributeError):
                return self.ib_class.registry.get_none()
        
        # 3. 后备：查 IbModule 类方法 (如 __to_prompt__ 等)
        return super().receive(message, args)

    def __repr__(self):
        return f"<Module '{self.name}'>"

class IbClass(IbObject):
    """
    IBC-Inter 类对象 (元对象)。
    贯彻“一切皆对象”思想：类本身也是一个对象。
    它持有该类的元数据 (TypeDescriptor) 和运行时方法表 (vtable)。
    """
    __slots__ = ('name', 'methods', 'parent', 'default_fields', 'member_types', 'registry', 'descriptor')

    def __init__(self, name: str, parent: Optional['IbClass'] = None, registry: Optional[Registry] = None):
        if not registry:
            raise ValueError("Registry is required for IbClass creation")
        self.registry = registry
        IbObject.__init__(self, self) # IbClass 的类是它自己
        self.name = name
        self.methods: Dict[str, 'IbFunction'] = {}
        self.parent = parent
        self.default_fields: Mapping[str, Any] = {}
        self.member_types: Dict[str, Any] = {}
        self.descriptor: Optional[TypeDescriptor] = None

    def lookup_method(self, name: str) -> Optional['IbFunction']:
        """在虚表中查找方法 (支持继承)"""
        if name in self.methods:
            return self.methods[name]
        if self.parent:
            return self.parent.lookup_method(name)
        return None

    def is_assignable_to(self, other: 'IbClass') -> bool:
        """运行时类型兼容性检查 (UTS 协议)"""
        if self is other: return True
        
        # [Active Defense] 强契约：唯一使用 UTS 描述符进行校验
        if self.descriptor and other.descriptor:
            return self.descriptor.is_assignable_to(other.descriptor)
            
        # 绝不回退到 Python 继承链，确保 UTS 语义的一致性
        return False

    def register_method(self, name: str, method: 'IbFunction'):
        self.methods[name] = method

    def instantiate(self, args: List[IbObject]) -> IbObject:
        instance = IbObject(self)
        instance.fields = self.default_fields.copy()
        init_method = self.lookup_method('__init__')
        if init_method:
            init_method.call(instance, args)
        return instance

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        """
        类对象的特殊消息处理：
        1. __call__ -> 实例化 (Instantiate) 或 类级别的 __call__
        2. 其他 -> 正常消息处理 (查找静态方法等)
        """
        if message == "__call__":
            # [IES 2.0 Meta-Model] 优先从自身的 methods 字典中查找 __call__
            # 注意：类作为对象时，其方法存在 self.methods 中
            if "__call__" in self.methods:
                method = self.methods["__call__"]
                # 绑定到类自身进行调用 (如果是 NativeFunction 会自动根据 is_method 注入 receiver)
                return IbBoundMethod(self, method).receive("__call__", args)
            return self.instantiate(args)
        return super().receive(message, args)

    def __repr__(self):
        return f"<Class '{self.name}'>"

class IbFunction(IbObject):
    """
    可调用对象的基类 (语言层表现为 callable)。
    """
    def __init__(self, ib_class: 'IbClass'):
        super().__init__(ib_class)

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        raise NotImplementedError()

class IbNativeFunction(IbFunction):
    """
    包装 Python 原生函数的 IBC 函数。
    用于引导阶段注入基础运算（如 int.__add__）。
    """
    def __init__(self, py_func: Callable, unbox_args: bool = False, is_method: bool = False, ib_class: Optional['IbClass'] = None, name: Optional[str] = None, logic_id: Optional[str] = None, descriptor: Optional[TypeDescriptor] = None):
        if not ib_class:
            raise ValueError("ib_class is required for IbNativeFunction")
        super().__init__(ib_class)
        self.py_func = py_func
        self.unbox_args = unbox_args
        self.is_method = is_method
        self.logic_id = logic_id
        self._name = name or (py_func.__name__ if hasattr(py_func, '__name__') else "anonymous")
        self._descriptor = descriptor

    @property
    def descriptor(self) -> TypeDescriptor:
        return self._descriptor or super().descriptor

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        final_args = args
        if self.unbox_args:
            final_args = [arg.to_native() if hasattr(arg, 'to_native') else arg for arg in args]

        try:
            if self.is_method:
                res = self.py_func(receiver, *final_args)
            else:
                res = self.py_func(*final_args)
            return self.ib_class.registry.box(res)
        except Exception as e:
            if isinstance(e, InterpreterError):
                raise
            raise InterpreterError(f"Native function '{self._name}' failed: {e}")

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        if message == '__getattr__':
            # [SECURITY] 原生函数禁止泄露底层 Python 函数属性 (如 __class__, __subclasses__)
            pass
        return super().receive(message, args)

    def __getattr__(self, name):
        return getattr(self.py_func, name)

class IbBoundMethod(IbFunction):
    """绑定了接收者的函数 (模拟 C++ 虚表调用的 this 绑定)"""
    def __init__(self, receiver: Optional[IbObject], method: IbFunction):
        # 优先查找 bound_method 类，如果没注册（如引导期）则回退到 callable
        cls = method.ib_class.registry.get_class("bound_method") or method.ib_class.registry.get_class("callable")
        super().__init__(cls)
        self.receiver = receiver
        self.method = method

    @property
    def descriptor(self) -> TypeDescriptor:
        """合成绑定方法的描述符"""
        reg = self.ib_class.registry
        m_reg = reg.get_metadata_registry()
        # 如果有元数据注册表，则动态合成结构化描述符
        if m_reg:
            r_desc = self.receiver.descriptor if self.receiver else None
            m_desc = self.method.descriptor
            if m_desc and m_desc.get_call_trait():
                return m_reg.factory.create_bound_method(r_desc, m_desc)
        return super().descriptor

    def call(self, _receiver: IbObject, args: List[IbObject]) -> IbObject:
        if self.receiver is None:
            raise InterpreterError("BoundMethod has no receiver (initialization failed or corrupt snapshot)")
        return self.method.call(self.receiver, args)

    def __repr__(self):
        return f"<BoundMethod {self.method} bound to {self.receiver}>"

class IbNone(IbObject):
    """
    IBC-Inter 的空对象 (None)。
    现在通过 Registry 获取单例。
    """
    def __init__(self, ib_class: 'IbClass'):
        super().__init__(ib_class)

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
    def __init__(self, node_uid: str, interpreter: 'Interpreter', ib_class: Optional['IbClass'] = None, descriptor: Optional[TypeDescriptor] = None):
        super().__init__(ib_class or interpreter.registry.get_class("callable"))
        self.node_uid = node_uid
        self.interpreter = interpreter
        self._descriptor = descriptor

    @property
    def descriptor(self) -> TypeDescriptor:
        return self._descriptor or super().descriptor

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """执行用户定义的函数"""
        node_data = self.interpreter.get_node_data(self.node_uid)
        params_uids = node_data.get("args", [])
        
        context = self.interpreter.context
        context.enter_scope()
        
        try:
            ib_none = self.ib_class.registry.get_none()
            if receiver and receiver is not ib_none:
                context.define_variable("self", receiver)
                
            for i, arg_uid in enumerate(params_uids):
                arg_data = self.interpreter.get_node_data(arg_uid)
                actual_arg_uid = arg_uid
                actual_arg_data = arg_data
                if arg_data.get("_type") == "IbTypeAnnotatedExpr":
                    actual_arg_uid = arg_data.get("target")
                    actual_arg_data = self.interpreter.get_node_data(actual_arg_uid)
                
                arg_name = actual_arg_data.get("arg")
                if i < len(args):
                    sym_uid = self.interpreter.get_side_table("node_to_symbol", actual_arg_uid)
                    context.define_variable(arg_name, args[i], uid=sym_uid)
            
            body = node_data.get("body", [])
            for stmt_uid in body:
                self.interpreter.visit(stmt_uid)
                
            return ib_none
        except ReturnException as e:
            return e.value
        finally:
            context.exit_scope()

    def __repr__(self):
        node_data = self.interpreter.get_node_data(self.node_uid)
        name = node_data.get("name", "unknown")
        return f"<Function '{name}'>"

class IbLLMFunction(IbFunction):
    """
    用户定义的 LLM 函数。
    """
    def __init__(self, node_uid: str, llm_executor: Any, interpreter: 'Interpreter', descriptor: Optional[TypeDescriptor] = None):
        super().__init__(interpreter.registry.get_class("callable"))
        self.node_uid = node_uid
        self.llm_executor = llm_executor
        self.interpreter = interpreter
        self._descriptor = descriptor

    @property
    def descriptor(self) -> TypeDescriptor:
        return self._descriptor or super().descriptor

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """执行 LLM 函数：负责作用域管理和参数绑定，然后分发给执行器"""
        node_data = self.interpreter.get_node_data(self.node_uid)
        context = self.interpreter.context
        
        context.enter_scope()
        try:
            ib_none = self.ib_class.registry.get_none()
            if receiver and receiver is not ib_none:
                context.define_variable("self", receiver)
                context.define_variable("__self", receiver)
                
            params_uids = node_data.get("args", [])
            for i, arg_uid in enumerate(params_uids):
                arg_data = self.interpreter.get_node_data(arg_uid)
                actual_arg_uid = arg_uid
                actual_arg_data = arg_data
                if arg_data.get("_type") == "IbTypeAnnotatedExpr":
                    actual_arg_uid = arg_data.get("target")
                    actual_arg_data = self.interpreter.get_node_data(actual_arg_uid)
                
                arg_name = actual_arg_data.get("arg")
                if i < len(args):
                    sym_uid = self.interpreter.get_side_table("node_to_symbol", actual_arg_uid)
                    context.define_variable(arg_name, args[i], uid=sym_uid)
                    if arg_name == 'text':
                        context.define_variable('__text', args[i])

            return self.llm_executor.execute_llm_function(self.node_uid, context)
            
        finally:
            context.exit_scope()

    def __repr__(self):
        node_data = self.interpreter.get_node_data(self.node_uid)
        name = node_data.get("name", "unknown")
        return f"<LLMFunction '{name}'>"
