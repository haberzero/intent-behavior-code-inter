from typing import Dict, Any, List, Optional, Callable, TYPE_CHECKING, Mapping
from core.foundation.registry import Registry
from core.runtime.enums import RegistrationState
from core.domain.issue import InterpreterError
from core.domain.issue_atomic import Location
from core.runtime.exceptions import ReturnException, RegistryIsolationError
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
        except (AttributeError, InterpreterError):
            # 仅在方法缺失或解释器主动报错时回退
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
        """
        [IES 2.0] Native 消息分发核心。
        强制通过虚表映射，禁止任何非预期的 Python 属性穿透。
        """
        # [Registry Isolation] 校验对象所属 Registry 身份
        if hasattr(self.py_obj, '_ibci_registry_id'):
            if self.py_obj._ibci_registry_id != id(self.ib_class.registry):
                raise RegistryIsolationError(f"Security Violation: Native object from another engine instance detected. [IES 2.0 Isolation Rule]")

        print(f"DEBUG: NativeObject receive '{message}' vtable keys: {list(self.vtable.keys())}")
        
        # 1. 如果消息本身就在虚表中 (方法直接调用)
        if message in self.vtable:
            attr = self.vtable[message]
            # [IES 2.0 Proxy] 所有的 Proxy VTable 都已经由 ModuleLoader 完成了自动装箱转换
            # 直接调用并返回 IbObject
            return attr(*args)

        # 2. 处理 __getattr__ 协议 (属性/方法获取)
        if message == '__getattr__' and len(args) > 0:
            target_name = args[0].to_native()
            
            # [IES 2.0 Proxy Binding] 如果是虚表方法，包装为 IbNativeFunction 导出
            if target_name in self.vtable:
                reg = self.ib_class.registry
                # [IES 2.0] 强制通过 Gatekeeper 获取协议类
                reg.verify_level_at_least(RegistrationState.STAGE_2_CORE_TYPES.value)
                
                callable_cls = reg.get_class("callable")
                if not callable_cls:
                    # 如果进入了插件加载阶段（STAGE 4+），callable 缺失属于严重初始化错误
                    reg.verify_level_at_least(RegistrationState.STAGE_4_PLUGIN_IMPL.value)
                    raise InterpreterError("Core Error: 'callable' class not found in registry. Builtins initialization failed? [IES 2.0 Fatal Assertion]")
                    
                return IbNativeFunction(
                    self.vtable[target_name], 
                    ib_class=callable_cls, 
                    name=target_name
                )
            
            # [SECURITY] 仅允许访问白名单属性
            if target_name in self.whitelist:
                if hasattr(self.py_obj, target_name):
                    return self.ib_class.registry.box(getattr(self.py_obj, target_name))
            
            # [IES 2.0 Strict] 未在契约或白名单声明的成员，坚决抛出异常
            raise AttributeError(f"Plugin Error: '{target_name}' is not defined in module contract (_spec.py)")

        # 3. 降级到基类公理 (如 __to_prompt__ 等)
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
        """
        [IES 2.0] 模块级消息传递核心。
        """
        # 1. 如果消息本身就是模块成员 (函数调用)，直接转发
        # 这里的 self.scope 是 IbNativeObject
        if hasattr(self.scope, 'receive'):
            try:
                # 尝试通过 IbNativeObject 的虚表直接执行
                return self.scope.receive(message, args)
            except AttributeError:
                pass

        # 2. 如果是属性获取 (__getattr__)，转发给 scope 以获取 IbNativeFunction
        if message == '__getattr__':
            if hasattr(self.scope, 'receive'):
                try:
                    return self.scope.receive('__getattr__', args)
                except AttributeError:
                    pass

        # 3. 备选：查找模块级定义的变量/函数 (Scope 模式，用于兼容非 Native 模块)
        try:
            return self.scope.get(message)
        except (KeyError, AttributeError):
            pass
            
        # 4. 后备：降级到基类公理 (如 __to_prompt__ 等)
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

    def instantiate(self, args: List[IbObject], interpreter: Optional['Interpreter'] = None) -> IbObject:
        instance = IbObject(self)
        
        # [IES 2.0] 延迟执行字段初始化 (Item 2.1 Audit)
        # 如果字段是复杂表达式（存储为 (uid, static_val) 元组），在实例化时求值
        for name, val_info in self.default_fields.items():
            if isinstance(val_info, tuple) and len(val_info) == 2:
                val_uid, static_val = val_info
                if static_val is not None:
                    # 简单常量快照直接复用
                    instance.fields[name] = static_val
                elif val_uid and interpreter:
                    # 复杂表达式通过解释器即时求值
                    try:
                        instance.fields[name] = interpreter.visit(val_uid)
                    except Exception:
                        # 如果求值失败，回退到 None
                        instance.fields[name] = self.registry.get_none()
                else:
                    instance.fields[name] = self.registry.get_none()
            else:
                # 兼容旧逻辑或已求值的对象
                instance.fields[name] = val_info
        
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
            
            # [IES 2.1 Audit] 实例化时传入解释器上下文以支持复杂字段初始化
            # 这里涉及对解释器的反射访问（如果有的话）
            interpreter = None
            if hasattr(self.registry, '_interpreter'):
                interpreter = self.registry._interpreter
            
            return self.instantiate(args, interpreter=interpreter)
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
        # [IES 2.0 FIX] 强制绑定到协议类，移除静默兜底
        reg = ib_class.registry if ib_class else None
        target_class = ib_class
        
        if not target_class and reg:
            # 在核心类型注入后 (STAGE 2+)，callable 应该是存在的
            if reg.state.value >= RegistrationState.STAGE_2_CORE_TYPES.value:
                target_class = reg.get_class("callable")
                if not target_class and reg.state.value >= RegistrationState.STAGE_4_PLUGIN_IMPL.value:
                    raise InterpreterError(f"Core Error: 'callable' class missing during STAGE {reg.state.name}. [IES 2.0 Fatal Assertion]")
        
        super().__init__(target_class)
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
        # [IES 2.0 Proxy Support] 如果 py_func 本身就是 IbObject (例如是一个 Proxy)，直接转发消息
        if isinstance(self.py_func, IbObject):
            return self.py_func.receive('__call__', args)

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
        
        # [NEW] Logical CallStack 追踪
        loc_data = self.interpreter.get_side_table("node_to_loc", self.node_uid)
        loc = None
        if loc_data:
            loc = Location(
                file_path=loc_data.get("file_path"),
                line=loc_data.get("line", 0),
                column=loc_data.get("column", 0)
            )
        
        self.interpreter.logical_stack.push(
            name=node_data.get("name", "anonymous"),
            local_vars={}, # 暂时不快照变量，性能考虑
            location=loc,
            intent_stack=[i.content for i in self.interpreter.context.get_active_intents()],
            is_user_function=True
        )
        
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
            self.interpreter.logical_stack.pop()
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
        
        # [NEW] Logical CallStack 追踪
        loc_data = self.interpreter.get_side_table("node_to_loc", self.node_uid)
        loc = None
        if loc_data:
            loc = Location(
                file_path=loc_data.get("file_path"),
                line=loc_data.get("line", 0),
                column=loc_data.get("column", 0)
            )
        
        self.interpreter.logical_stack.push(
            name=f"llm:{node_data.get('name', 'anonymous')}",
            local_vars={}, # 暂时不快照变量，性能考虑
            location=loc,
            intent_stack=[i.content for i in self.interpreter.context.get_active_intents()],
            is_user_function=True
        )
        
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
            self.interpreter.logical_stack.pop()
            context.exit_scope()

    def __repr__(self):
        node_data = self.interpreter.get_node_data(self.node_uid)
        name = node_data.get("name", "unknown")
        return f"<LLMFunction '{name}'>"
