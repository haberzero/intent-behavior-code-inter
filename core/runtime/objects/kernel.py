from typing import Dict, Any, List, Optional, Callable, TYPE_CHECKING, Mapping, Tuple
from core.kernel.registry import KernelRegistry
from core.base.enums import RegistrationState
from core.kernel.issue import InterpreterError
from core.base.source_atomic import Location
from core.runtime.exceptions import ReturnException, BreakException, ContinueException, RegistryIsolationError
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger
from core.kernel.intent_logic import IntentRole
from core.kernel.spec import IbSpec, FuncSpec, ClassSpec, ANY_SPEC

if TYPE_CHECKING:
    from core.kernel import ast as ast
    from core.runtime.interfaces import IExecutionContext
    from core.runtime.interpreter.interpreter import Interpreter

from .ib_type_mapping import register_ib_type

@register_ib_type("any")
@register_ib_type("auto")
@register_ib_type("callable")
@register_ib_type("void")
@register_ib_type("bound_method")
class IbObject:
    """
    IBC-Inter 对象基类 (一切皆对象)。
    模拟汇编层面的内存布局：持有一个指向 IbClass 的引用 (vptr) 和一个存储实例属性的字典。
    """
    __slots__ = ('ib_class', 'fields')

    def __init__(self, ib_class: 'IbClass'):
        self.ib_class = ib_class
        self.fields: Mapping[str, Any] = {}

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        """
        统一消息传递接口。
        所有属性访问和方法调用都通过此入口分发。
        """
        core_debugger.trace(CoreModule.INTERPRETER, DebugLevel.DATA, f"[MSG] {self} received '{message}' with {args}")
        
        # 下沉至公理层能力探测
        # 针对 __call__ 消息，检查类型公理是否声明了调用能力
        if message == '__call__':
            spec_reg = self.ib_class.registry.get_metadata_registry()
            if spec_reg and self.ib_class.spec:
                call_cap = spec_reg.get_call_cap(self.ib_class.spec)
                if call_cap and hasattr(self, 'call'):
                    return self.call(self.ib_class.registry.get_none(), args)
            
        if message == '__getattr__' and len(args) > 0:
            attr_name = args[0].to_native()
            # 优先查找实例字段
            if attr_name in self.fields:
                return self.fields[attr_name]
            # 降级查找类方法
            method = self.ib_class.lookup_method(attr_name)
            if method:
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

        # [cast_to Hook] 处理类型转换消息
        if message == 'cast_to':
            if not args:
                raise InterpreterError("cast_to requires exactly one argument: target class")

            target_class = args[0]
            target_name = getattr(target_class, 'name', None)
            if not target_name:
                raise InterpreterError("cast_to argument must be an IbClass")

            # 同一类型转换：直接返回自身
            if self.ib_class.name == target_name:
                return self

            # 向上转型（upcast）：目标类型是当前类的祖先，直接返回自身（安全且语义正确）
            if isinstance(target_class, IbClass) and self.ib_class.is_assignable_to(target_class):
                return self

            # 如果对象自身有 cast_to 方法（特殊类型包装器），优先调用
            if hasattr(self, 'cast_to'):
                return self.cast_to(target_class)

            # 尝试使用 __to_prompt__ 进行字符串转换
            if target_name in ("str", "any"):
                try:
                    prompt_result = self.__to_prompt__()
                    return self.ib_class.registry.box(prompt_result)
                except Exception:
                    pass

            # 无法执行类型转换，抛出明确错误
            raise InterpreterError(
                f"TypeError: Cannot cast '{self.ib_class.name}' to '{target_name}'. "
                f"Type '{self.ib_class.name}' does not implement type conversion."
            )

        raise AttributeError(f"Object of type '{self.ib_class.name}' has no method '{message}'")

    def __to_prompt__(self) -> str:
        """
        响应 Spec 协议：定义对象在 LLM 视角下的表现形式。
        """
        try:
            res = self.receive('__to_prompt__', [])
            return str(res.value) if hasattr(res, 'value') else str(res)
        except (AttributeError, InterpreterError):
            return f"<Instance of {self.ib_class.name}>"

    def __from_prompt__(self, raw_response: str) -> Tuple[bool, Any]:
        """
        Parse a value from raw LLM output text.
        Delegates to the spec's axiom from_prompt capability.
        """
        try:
            spec_reg = self.ib_class.registry.get_metadata_registry()
            if spec_reg and self.ib_class.spec:
                cap = spec_reg.get_from_prompt_cap(self.ib_class.spec)
                if cap:
                    return cap.from_prompt(raw_response, self.ib_class.spec)
        except Exception:
            pass
        return (False, f"无法将 '{raw_response}' 解析为 {self.ib_class.name} 类型")

    def __outputhint_prompt__(self) -> str:
        """
        返回期望的 LLM 输出格式描述。
        优先尝试通过 vtable 调用用户定义的 __outputhint_prompt__ 方法，
        没有时退回到默认描述。
        """
        try:
            res = self.receive('__outputhint_prompt__', [])
            return str(res.to_native()) if hasattr(res, 'to_native') else str(res)
        except (AttributeError, InterpreterError):
            pass
        return f"请返回一个 {self.ib_class.name} 类型的值"

    # ---  基础协议实现 ---
    def __not__(self) -> 'IbObject':
        """逻辑非运算协议"""
        # 使用 vtable to_bool 判定并取反，返回 bool 类型
        bool_val = self.receive('to_bool', []).to_native()
        return self.ib_class.registry.box(False if bool_val else True)

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
        # 显式持有虚表，消除对 py_obj 的动态属性依赖
        self.vtable = vtable if vtable is not None else getattr(py_obj, '_ibci_vtable', {})
        # [SECURITY] 属性访问白名单
        self.whitelist = whitelist if whitelist is not None else getattr(py_obj, '_ibci_whitelist', [])

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        """
         Native 消息分发核心。
        强制通过虚表映射，禁止任何非预期的 Python 属性穿透。
        """
        # [Registry Isolation] 校验对象所属 Registry 身份
        if hasattr(self.py_obj, '_ibci_registry_id'):
            if self.py_obj._ibci_registry_id != id(self.ib_class.registry):
                raise RegistryIsolationError(f"Security Violation: Native object from another engine instance detected. ")

        # 1. 如果消息本身就在虚表中 (方法直接调用)
        if message in self.vtable:
            attr = self.vtable[message]
            # 所有的 Proxy VTable 都已经由 ModuleLoader 完成了自动装箱转换
            # 直接调用并返回 IbObject
            return attr(*args)

        # 2. 处理 __getattr__ 协议 (属性/方法获取)
        if message == '__getattr__' and len(args) > 0:
            target_name = args[0].to_native()
            
            # 如果是虚表方法，包装为 IbNativeFunction 导出
            if target_name in self.vtable:
                reg = self.ib_class.registry
                # 强制通过 Gatekeeper 获取协议类
                reg.verify_level_at_least(RegistrationState.STAGE_2_CORE_TYPES.value)
                
                callable_cls = reg.get_class("callable")
                if not callable_cls:
                    # 如果进入了插件加载阶段（STAGE 4+），callable 缺失属于严重初始化错误
                    reg.verify_level_at_least(RegistrationState.STAGE_4_PLUGIN_IMPL.value)
                    raise InterpreterError("Core Error: 'callable' class not found in registry. Builtins initialization failed? ")
                    
                return IbNativeFunction(
                    self.vtable[target_name], 
                    ib_class=callable_cls, 
                    name=target_name
                )
            
            # [SECURITY] 仅允许访问白名单属性
            if target_name in self.whitelist:
                if hasattr(self.py_obj, target_name):
                    return self.ib_class.registry.box(getattr(self.py_obj, target_name))
            
            # 未在契约或白名单声明的成员，坚决抛出异常
            raise AttributeError(f"Plugin Error: '{target_name}' is not defined in module contract (_spec.py)")

        # 3. 降级到基类公理 (如 __to_prompt__ 等)
        return super().receive(message, args)

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        return self.py_obj

    def __repr__(self):
        return f"<NativeObject {self.py_obj}>"

@register_ib_type("module")
class IbModule(IbObject):
    """
    IBC-Inter 模块对象。
    持有一个作用域 (Scope)，并根据 UTS 协议通过消息传递暴露成员。
    """
    def __init__(self, name: str, scope: Any, registry: KernelRegistry):
        super().__init__(registry.get_class("module") or registry.get_class("Object"))
        self.name = name
        self.scope = scope

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        """
         模块级消息传递核心。
        """
        # 1. 处理 __getattr__ 协议
        if message == '__getattr__' and len(args) > 0:
            target_name = args[0].to_native()
            
            # 优先从 Native 虚表或实现中查找
            if hasattr(self.scope, 'receive'):
                try:
                    return self.scope.receive('__getattr__', args)
                except AttributeError:
                    pass
            
            # 其次查找模块级定义的变量/函数 (Scope 模式)
            if hasattr(self.scope, 'get'):
                try:
                    return self.scope.get(target_name)
                except (KeyError, AttributeError):
                    pass

        # 2. 尝试通过 IbNativeObject 的虚表直接执行 (如果是 Native 模块)
        if hasattr(self.scope, 'receive'):
            try:
                return self.scope.receive(message, args)
            except AttributeError:
                pass

        # 3. 查找模块级定义的变量/函数 (Scope 模式)
        if hasattr(self.scope, 'get'):
            try:
                return self.scope.get(message)
            except (KeyError, AttributeError):
                pass
            
        # 4. 后备：降级到基类公理 (如 __to_prompt__ 等)
        return super().receive(message, args)

    def __repr__(self):
        return f"<Module '{self.name}'>"

class IbDeferredField:
    """延迟字段描述符：存储 AST 节点 UID 及其可能的预评估快照。"""
    def __init__(self, val_uid: str, static_val: Optional[IbObject] = None, module_name: Optional[str] = None):
        self.val_uid = val_uid
        self.static_val = static_val
        self.module_name = module_name

    def __repr__(self):
        return f"<DeferredField {self.val_uid} (static={self.static_val})>"

@register_ib_type("Type")
@register_ib_type("Class")
class IbClass(IbObject):
    """
    IBC-Inter class object (meta-object).
    Everything is an object — classes themselves are objects.
    Holds the IbSpec (pure-data type description) and the runtime method vtable.
    """
    __slots__ = ('name', 'methods', 'parent', 'default_fields', 'member_types', 'registry', '_spec')

    def __init__(self, name: str, parent: Optional['IbClass'] = None, registry: Optional[KernelRegistry] = None):
        if not registry:
            raise ValueError("Registry is required for IbClass creation")
        self.registry = registry
        IbObject.__init__(self, self)
        self.name = name
        self.methods: Dict[str, 'IbFunction'] = {}
        self.parent = parent
        self.default_fields: Mapping[str, Any] = {}
        self.member_types: Dict[str, Any] = {}
        self._spec: Optional[IbSpec] = None

    @property
    def spec(self) -> Optional[IbSpec]:
        return self._spec

    @spec.setter
    def spec(self, value: Optional[IbSpec]) -> None:
        self._spec = value

    def lookup_method(self, name: str) -> Optional['IbFunction']:
        """在虚表中查找方法 (支持继承)"""
        if name in self.methods:
            return self.methods[name]
        if self.parent:
            return self.parent.lookup_method(name)
        return None

    def is_assignable_to(self, other: 'IbClass') -> bool:
        """Runtime type compatibility check (UTS protocol)."""
        if self is other:
            return True
        if other is None:
            return False
        spec_reg = self.registry.get_metadata_registry()
        if spec_reg and self._spec and other._spec:
            return spec_reg.is_assignable(self._spec, other._spec)
        return False

    def register_method(self, name: str, method: 'IIbFunction') -> None:
        # 封印校验：禁止在 Registry READY 状态下修改虚表
        if self.registry.is_sealed:
            raise PermissionError(f"Sealed Registry Violation: Cannot register method '{name}' to class '{self.name}' in READY state.")
        self.methods[name] = method

    def register_field(self, name: str, default_value: 'IbObject') -> None:
        # 封印校验
        if self.registry.is_sealed:
            raise PermissionError(f"Sealed Registry Violation: Cannot register field '{name}' to class '{self.name}' in READY state.")
        self.default_fields[name] = default_value

    def instantiate(self, args: List[IbObject], context: Optional['IExecutionContext'] = None) -> IbObject:
        instance = IbObject(self)
        
        # Bug D 修复：收集完整的字段继承链（父类字段 + 子类字段）
        # 父类字段先初始化，子类同名字段会覆盖父类字段
        all_default_fields = {}
        # 从继承链顶部开始收集（最远祖先优先）
        ancestors = []
        cls = self
        while cls is not None:
            ancestors.append(cls)
            cls = cls.parent
        for ancestor in reversed(ancestors):
            for name, val_info in ancestor.default_fields.items():
                all_default_fields[name] = val_info
        
        # 延迟执行字段初始化 (Item 2.1 Audit)
        for name, val_info in all_default_fields.items():
            if isinstance(val_info, IbDeferredField):
                if val_info.static_val is not None:
                    # 优先使用预评估好的快照，但可变容器（IbList/IbDict）必须每次创建新实例，
                    # 避免所有实例共享同一容器对象（浅拷贝快照，元素引用共享）。
                    from core.runtime.objects.builtins import IbList, IbDict
                    sv = val_info.static_val
                    if isinstance(sv, IbList):
                        instance.fields[name] = IbList(list(sv.elements), sv.ib_class)
                    elif isinstance(sv, IbDict):
                        instance.fields[name] = IbDict(dict(sv.fields), sv.ib_class)
                    else:
                        instance.fields[name] = sv
                elif val_info.val_uid and context:
                    # 动态求值并尝试更新描述符以供后续实例复用 (JIT caching)
                    try:
                        # 确保在定义该字段的模块上下文中进行求值
                        evaluated = context.visit(val_info.val_uid, module_name=val_info.module_name)
                        instance.fields[name] = evaluated
                        # 如果是简单的纯函数或常量表达式，可以缓存到类描述符中
                        # 这里我们激进一点，只要成功求值就缓存，除非用户显式要求 JIT
                        val_info.static_val = evaluated
                    except Exception:
                        instance.fields[name] = self.registry.get_none()
                else:
                    instance.fields[name] = self.registry.get_none()
            else:
                # [Active Defense] 仅支持 IbDeferredField，确保字段初始化的一致性
                instance.fields[name] = val_info
        
        init_method = self.lookup_method('__init__')
        if init_method:
            # 契约一致性校验：校验 __init__ 参数数量
            # 注意：描述符中的参数列表通常不包含 self (除非是特殊定义的)
            if init_method.spec and isinstance(init_method.spec, FuncSpec):
                expected_count = len(init_method.spec.param_type_names)
                if len(args) != expected_count:
                    raise InterpreterError(f"TypeError: {self.name}.__init__() expected {expected_count} arguments, but got {len(args)}")
            
            init_method.call(instance, args)
        elif args:
            # 如果没有定义 __init__ 但传了参数，也是一种契约违背
            raise InterpreterError(f"TypeError: {self.name}() takes no arguments, but {len(args)} were given")
            
        return instance

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        """
        类对象的特殊消息处理：
        1. __call__ -> 实例化 (Instantiate) 或 类级别的 __call__
        2. __getattr__ -> 访问类字段 (default_fields)
        3. 其他 -> 正常消息处理 (查找静态方法等)
        """
        if message == "__call__":
            # 类作为构造器调用时，始终使用 instantiate 创建新实例。
            # 用户定义的 __call__ 是实例方法（使实例可调用），不覆盖构造器。
            # 实例的 __call__ 通过 IbObject.receive 中的 vtable 查找分发。
            context = self.registry.get_execution_context()
            return self.instantiate(args, context=context)
        
        if message == "__getattr__" and len(args) > 0:
            attr_name = args[0].to_native()
            # 优先查找类字段 (default_fields)
            if attr_name in self.default_fields:
                val_info = self.default_fields[attr_name]
                if val_info is not None:
                    if hasattr(val_info, 'static_val') and val_info.static_val is not None:
                        return val_info.static_val
                    return self.registry.box(val_info)
            # 降级查找类方法
            method = self.lookup_method(attr_name)
            if method:
                return IbBoundMethod(self, method)
            raise AttributeError(f"Class '{self.name}' has no attribute '{attr_name}'")
        
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
    def __init__(self, py_func: Callable, unbox_args: bool = False, is_method: bool = False, ib_class: Optional['IbClass'] = None, name: Optional[str] = None, logic_id: Optional[str] = None, spec: Optional[IbSpec] = None):
        # 强制绑定到协议类，移除静默兜底
        reg = ib_class.registry if ib_class else None
        target_class = ib_class
        
        if not target_class and reg:
            if reg.state_level >= RegistrationState.STAGE_2_CORE_TYPES.value:
                target_class = reg.get_class("callable")
                if not target_class and reg.state_level >= RegistrationState.STAGE_4_PLUGIN_IMPL.value:
                    raise InterpreterError(f"Core Error: 'callable' class missing during STAGE {RegistrationState(reg.state_level).name}. ")
        
        super().__init__(target_class)
        self.py_func = py_func
        self.unbox_args = unbox_args
        self.is_method = is_method
        self.logic_id = logic_id
        self._name = name or (py_func.__name__ if hasattr(py_func, '__name__') else "anonymous")
        self._spec = spec

    @property
    def spec(self) -> Optional[IbSpec]:
        return self._spec if self._spec is not None else self.ib_class.spec

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        # 如果 py_func 本身就是 IbObject (例如是一个 Proxy)，直接转发消息
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
    def spec(self) -> Optional[IbSpec]:
        """Synthesise a BoundMethodSpec for this bound method."""
        spec_reg = self.ib_class.registry.get_metadata_registry()
        if spec_reg:
            r_name = self.receiver.ib_class.name if self.receiver else ""
            m_name = self.method.ib_class.name
            return spec_reg.factory.create_bound_method(r_name, m_name)
        return self.ib_class.spec

    def call(self, _receiver: IbObject, args: List[IbObject]) -> IbObject:
        if self.receiver is None:
            raise InterpreterError("BoundMethod has no receiver (initialization failed or corrupt snapshot)")
        return self.method.call(self.receiver, args)

    def __repr__(self):
        return f"<BoundMethod {self.method} bound to {self.receiver}>"


class IbSuperProxy(IbObject):
    """
    super() 代理对象。

    在 IBCI 方法体内调用 super() 时创建此对象。
    - receiver：当前 self（方法接收者）
    - owner_class：定义当前方法的类（编译期/hydration 期绑定）
    - parent_class：owner_class 的父类，方法查找从此处开始

    使用方式：
        super().method_name(args)  ← super() 返回此代理；.method_name 通过 __getattr__ 返回绑定了 receiver 的父类方法
    """
    def __init__(self, receiver: IbObject, parent_class: Optional['IbClass']):
        # 借用 callable class 作为宿主类型（super() 是纯运行时内核概念，无对应 axiom）
        ib_cls = receiver.ib_class.registry.get_class("callable") or receiver.ib_class
        super().__init__(ib_cls)
        self._receiver = receiver
        self._parent_class = parent_class

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        if message == '__getattr__' and args:
            attr_name = args[0].to_native()
            if self._parent_class:
                method = self._parent_class.lookup_method(attr_name)
                if method:
                    return IbBoundMethod(self._receiver, method)
            raise AttributeError(f"super(): parent class has no method '{attr_name}'")
        if message == '__call__':
            # super() called directly (not super().method()) — not meaningful; return self
            return self
        raise AttributeError(f"super() proxy does not support message '{message}'")

    def __repr__(self):
        parent_name = self._parent_class.name if self._parent_class else "<no parent>"
        return f"<super: <class '{parent_name}'>, <{self._receiver.ib_class.name} object>>"


class IbNone(IbObject):
    """
    IBC-Inter 的空对象 (None)。
    现在通过 Registry 获取单例。
    """
    def __init__(self, ib_class: 'IbClass'):
        super().__init__(ib_class)

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        if message == '__eq__':
            right = args[0] if args else None
            return self.ib_class.registry.box(isinstance(right, IbNone))
        if message == '__ne__':
            right = args[0] if args else None
            return self.ib_class.registry.box(not isinstance(right, IbNone))
        return super().receive(message, args)

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        return None

    def __to_prompt__(self) -> str:
        return "null"

    def to_bool(self) -> IbObject:
        """ None 始终为 False"""
        return self.ib_class.registry.box(0)

    def cast_to(self, target_class: Any) -> IbObject:
        """ 支持 None 的强转逻辑"""
        if target_class.name == "str":
            return self.ib_class.registry.box("None")
        if target_class.name in ("int", "float"):
            return self.ib_class.registry.box(0)
        if target_class.name == "bool":
            return self.ib_class.registry.box(0)
        return self

    def __repr__(self):
        return "null"


@register_ib_type("llm_uncertain")
class IbLLMUncertain(IbObject):
    """
    表示 LLM 调用重试耗尽后仍无法得到确定结果的特殊值。

    公理类型：llm_uncertain（有独立 IbClass / AxiomSpec，不依附于 None 类型）

    语义：
    - 布尔上下文中为 False（if r: → 不进入分支）
    - to_native 返回 None
    - __to_prompt__ / (str) 强转返回 "uncertain"
    - 可以赋值给任何类型的变量（LLMUncertainAxiom.is_compatible 宽松策略）
    - 不进入异常体系——用户通过 if/while 逻辑主动检测
    """
    def __init__(self, ib_class: 'IbClass'):
        super().__init__(ib_class)

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        return None

    def __to_prompt__(self) -> str:
        return "uncertain"

    def to_bool(self) -> IbObject:
        """IbLLMUncertain 在布尔上下文中为 False"""
        return self.ib_class.registry.box(0)

    def cast_to(self, target_class: Any) -> IbObject:
        """支持 IbLLMUncertain 的强转逻辑"""
        if target_class.name == "str":
            return self.ib_class.registry.box("uncertain")
        if target_class.name in ("int", "float"):
            return self.ib_class.registry.box(0)
        if target_class.name == "bool":
            return self.ib_class.registry.box(0)
        return self

    def __repr__(self):
        return "uncertain"


@register_ib_type("llm_call_result")
class IbLLMCallResult(IbObject):
    """
    LLM 调用结果的结构化类型。

    替代 IbLLMUncertain 的"例外特殊对象"模式，使 LLM 调用结果成为
    公理体系中有完整语义的独立类型。

    字段：
    - is_certain: bool      结果是否确定（LLM 返回了可解析的有效值）
    - value: IbObject       确定时的值；不确定时为 IbNone
    - raw_response: str     LLM 原始响应（用于 retry_hint 生成）
    - retry_hint: str       不确定时的重试提示（传递给下一次 LLM 调用）

    语义：
    - is_certain=True  → 调用成功，value 包含有效 IbObject
    - is_certain=False → 调用不确定，retry_hint 描述问题，llmexcept 应处理此情况

    与 IbLLMUncertain 的关系：
    - IbLLMUncertain 仍是变量赋值"不确定值"的标记类型（保持不变）
    - IbLLMCallResult 是 llmexcept 保护块的"调用结果容器"（新增）
    - 未来 llmexcept 可改为接收 IbLLMCallResult 而非捕获异常
    """
    def __init__(self, ib_class: 'IbClass', is_certain: bool, value: Optional['IbObject'] = None,
                 raw_response: str = "", retry_hint: str = ""):
        super().__init__(ib_class)
        self.is_certain = is_certain
        self.result_value = value
        self.raw_response = raw_response
        self.retry_hint = retry_hint

    def to_native(self, memo=None) -> Any:
        if self.is_certain and self.result_value is not None:
            return self.result_value.to_native(memo) if hasattr(self.result_value, 'to_native') else self.result_value
        return None

    def __to_prompt__(self) -> str:
        if self.is_certain:
            return f"LLMCallResult(certain, value={self.result_value})"
        return f"LLMCallResult(uncertain, hint={self.retry_hint!r})"

    def __repr__(self) -> str:
        status = "certain" if self.is_certain else "uncertain"
        return f"<LLMCallResult {status}: {self.result_value if self.is_certain else self.retry_hint!r}>"


class IbUserFunction(IbFunction):
    """
    用户定义的 IBC 函数。
    """
    def __init__(self, node_uid: str, context: 'IExecutionContext', ib_class: Optional['IbClass'] = None, spec: Optional[IbSpec] = None, module_name: Optional[str] = None, owner_class: Optional['IbClass'] = None):
        super().__init__(ib_class or context.registry.get_class("callable"))
        self.node_uid = node_uid
        self.context = context
        self._spec = spec
        self.module_name = module_name or context.current_module_name
        # 定义该方法的 IbClass（方法归属类）。用于 super() 支持。
        # 对于顶层函数，此字段为 None（不在类内）。
        self.owner_class: Optional['IbClass'] = owner_class

    @property
    def spec(self) -> Optional[IbSpec]:
        return self._spec if self._spec is not None else self.ib_class.spec

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """执行用户定义的函数"""
        # 切换到函数定义所在的模块上下文
        from core.runtime.frame import get_current_frame as _get_frame
        from core.runtime.objects.builtins import IbDeferred, IbBehavior
        from core.base.diagnostics.codes import RUN_CALL_ERROR
        _frame = _get_frame()
        rt_context = _frame if _frame is not None else self.context.runtime_context
        old_module = self.context.current_module_name
        old_scope = rt_context.current_scope

        # --- 意图栈作用域隔離（拷贝传递语义）---
        # 每次函数调用 fork 调用者的意图上下文，函数内的 @+/@- 不泄漏给调用者。
        # 若需在函数体内屏蔽继承自调用者的意图，请显式调用：
        #   intent_context.clear_inherited()  — 清空继承来的持久意图栈
        #   intent_context.use(ctx)           — 以自定义上下文替换当前作用域的意图上下文
        from core.runtime.objects.intent_context import IbIntentContext
        old_intent_ctx = rt_context._intent_ctx
        child_ctx = old_intent_ctx.fork()
        rt_context._intent_ctx = child_ctx

        if self.module_name and self.module_name != old_module:
            self.context.current_module_name = self.module_name
            # 获取目标模块的作用域
            try:
                mod_inst = self.context.module_manager.import_module(self.module_name, self.context)
                rt_context.current_scope = mod_inst.scope
            except:
                pass

        try:
            node_data = self.context.get_node_data(self.node_uid)
            params_uids = node_data.get("args", [])
            
            rt_context.enter_scope()
        
            loc_data = self.context.get_side_table("node_to_loc", self.node_uid)
            loc = None
            if loc_data:
                loc = Location(
                    file_path=loc_data.get("file_path"),
                    line=loc_data.get("line", 0),
                    column=loc_data.get("column", 0)
                )
            
            self.context.push_stack(
                name=node_data.get("name", "anonymous"),
                location=loc,
                is_user_function=True
            )
            
            ib_none = self.ib_class.registry.get_none()
            if receiver and receiver is not ib_none:
                # 查找 self 符号的 UID（语义分析阶段将函数定义节点映射到 self 符号）
                self_sym = self.context.get_side_table("node_to_symbol", self.node_uid)
                self_uid = self_sym if isinstance(self_sym, str) else (self_sym.uid if self_sym else None)
                rt_context.define_variable("self", receiver, uid=self_uid)
                
                # super() 支持：若该函数有归属类（owner_class）且归属类有父类，
                # 则在方法作用域内注入 super 代理对象。
                # super 使用固定 UID "builtin:super" 以避免符号查找冲突。
                if self.owner_class and self.owner_class.parent:
                    super_proxy = IbSuperProxy(receiver, self.owner_class.parent)
                    rt_context.define_variable("super", super_proxy, uid="builtin:super")
                
            for i, arg_uid in enumerate(params_uids):
                arg_data = self.context.get_node_data(arg_uid)
                actual_arg_uid = arg_uid
                actual_arg_data = arg_data
                if arg_data.get("_type") == "IbTypeAnnotatedExpr":
                    actual_arg_uid = arg_data.get("target")
                    actual_arg_data = self.context.get_node_data(actual_arg_uid)
                
                arg_name = actual_arg_data.get("arg")
                if i < len(args):
                    sym_uid = self.context.get_side_table("node_to_symbol", actual_arg_uid)
                    rt_context.define_variable(arg_name, args[i], uid=sym_uid)
            
            body = node_data.get("body", [])
            # M3d：通过 VMExecutor 驱动函数体语句，与 Interpreter.execute_module() 一致。
            # ControlSignalException（顶层未消费 RETURN）由本帧捕获并提取返回值；
            # BREAK/CONTINUE 在函数体外属于错误（既有 except ReturnException 路径
            # 已不接受其它控制流，由 VMExecutor 内部 IbWhile/IbFor 消费）。
            from core.runtime.vm.task import (
                ControlSignal as _CS, ControlSignalException as _CSE,
            )
            vm_getter = getattr(self.context, "vm_executor", None)
            if vm_getter is None:
                # 通过 interpreter 取得 VMExecutor（execution_context 不直接暴露）
                interp = getattr(self.context, "_interpreter", None) or getattr(
                    self.context, "interpreter", None
                )
                if interp is not None and hasattr(interp, "_get_vm_executor"):
                    vm = interp._get_vm_executor()
                else:
                    vm = None
            else:
                vm = vm_getter

            if vm is None:
                # 无 VMExecutor 可用：保留原有递归路径
                for stmt_uid in body:
                    self.context.visit(stmt_uid)
            else:
                # node_protection 重定向由 VMExecutor.run() 入口统一处理；
                # 函数体内只需跳过直接出现的 IbLLMExceptionalStmt 节点。
                for stmt_uid in body:
                    stmt_data = self.context.get_node_data(stmt_uid)
                    if stmt_data and stmt_data.get("_type") == "IbLLMExceptionalStmt":
                        continue
                    try:
                        vm.run(stmt_uid)
                    except _CSE as cse:
                        if cse.kind is _CS.RETURN:
                            raise ReturnException(cse.value)
                        if cse.kind is _CS.BREAK:
                            raise BreakException()
                        if cse.kind is _CS.CONTINUE:
                            raise ContinueException()
                        raise

            return ib_none
        except ReturnException as e:
            return e.value
        finally:
            self.context.pop_stack()
            rt_context.exit_scope()
            # 恢复调用者的意图上下文和模块上下文
            rt_context._intent_ctx = old_intent_ctx
            self.context.current_module_name = old_module
            rt_context.current_scope = old_scope

    def __repr__(self):
        node_data = self.context.get_node_data(self.node_uid)
        name = node_data.get("name", "unknown")
        return f"<Function '{name}'>"

class IbLLMFunction(IbFunction):
    """
    用户定义的 LLM 函数。

    公理化设计原则
    --------------
    IbLLMFunction 与 IbBehavior 同构：不再在构造时持有 llm_executor 引用。
    call() 通过 ib_class.registry.get_llm_executor().invoke_llm_function() 自主执行。
    """
    def __init__(self, node_uid: str, context: 'IExecutionContext', spec: Optional[IbSpec] = None, module_name: Optional[str] = None):
        super().__init__(context.registry.get_class("callable"))
        self.node_uid = node_uid
        self.context = context
        self._spec = spec
        self.module_name = module_name or context.current_module_name
        # 暂存由 call() 解析的呼叫级意图，供 invoke_llm_function 消费
        self._pending_call_intent: Optional[Any] = None

    @property
    def spec(self) -> Optional[IbSpec]:
        return self._spec if self._spec is not None else self.ib_class.spec

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """
        执行 LLM 函数：负责作用域管理和参数绑定，然后通过 KernelRegistry 分发给执行器。

        与 IbBehavior.call() 同构：通过 registry.get_llm_executor() 获取执行器，
        不再持有 llm_executor 直接引用。
        """
        executor = self.ib_class.registry.get_llm_executor()
        if executor is None:
            raise RuntimeError(
                f"IbLLMFunction '{self.node_uid}': LLM executor not registered in KernelRegistry. "
                "Ensure engine._prepare_interpreter() has completed before invoking an LLM function."
            )

        # 切换到函数定义所在的模块上下文
        rt_context = self.context.runtime_context
        old_module = self.context.current_module_name
        old_scope = rt_context.current_scope

        # --- 意图栈作用域隔离（拷贝传递语义）---
        # 与 IbUserFunction.call() 对称：fork 调用者意图上下文，函数内操作不泄漏。
        # 若需在函数体内屏蔽继承的意图，请在函数体内显式调用 intent_context.clear_inherited()。
        old_intent_ctx = rt_context._intent_ctx
        child_ctx = old_intent_ctx.fork()
        rt_context._intent_ctx = child_ctx

        if self.module_name and self.module_name != old_module:
            self.context.current_module_name = self.module_name
            # 获取目标模块的作用域
            try:
                mod_inst = self.context.module_manager.import_module(self.module_name, self.context)
                rt_context.current_scope = mod_inst.scope
            except:
                pass

        try:
            node_data = self.context.get_node_data(self.node_uid)
            rt_context.enter_scope()
            
            loc_data = self.context.get_side_table("node_to_loc", self.node_uid)
            loc = None
            if loc_data:
                loc = Location(
                    file_path=loc_data.get("file_path"),
                    line=loc_data.get("line", 0),
                    column=loc_data.get("column", 0)
                )
            
            self.context.push_stack(
                name=node_data.get("name", "llm_anonymous"),
                location=loc,
                is_user_function=True
            )
            
            params_uids = node_data.get("args", [])
            for i, arg_uid in enumerate(params_uids):
                arg_data = self.context.get_node_data(arg_uid)
                # 处理类型标注包装
                actual_arg_uid = arg_uid
                actual_arg_data = arg_data
                if arg_data.get("_type") == "IbTypeAnnotatedExpr":
                    actual_arg_uid = arg_data.get("target")
                    actual_arg_data = self.context.get_node_data(actual_arg_uid)
                
                arg_name = actual_arg_data.get("arg")
                if i < len(args):
                    sym_uid = self.context.get_side_table("node_to_symbol", actual_arg_uid)
                    rt_context.define_variable(arg_name, args[i], uid=sym_uid)
            
            # 解析呼叫级意图（函数头上的意图），暂存供 invoke_llm_function 消费
            intent_uid = node_data.get("intent")
            self._pending_call_intent = None
            if intent_uid:
                intent_data = self.context.get_node_data(intent_uid)
                self._pending_call_intent = self.context.factory.create_intent_from_node(
                    intent_uid,
                    intent_data,
                    role=IntentRole.SMEAR
                )
            
            # 公理化调用：通过 KernelRegistry 获取执行器，不再直接持有
            return executor.invoke_llm_function(self, self.context)
        finally:
            self._pending_call_intent = None
            self.context.pop_stack()
            rt_context.exit_scope()
            # 恢复调用者的意图上下文和模块上下文
            rt_context._intent_ctx = old_intent_ctx
            self.context.current_module_name = old_module
            rt_context.current_scope = old_scope


    def __repr__(self):
        node_data = self.context.get_node_data(self.node_uid)
        name = node_data.get("name", "unknown")
        return f"<LLMFunction '{name}'>"
