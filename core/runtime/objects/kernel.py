from typing import Dict, Any, List, Optional, Callable, TYPE_CHECKING, Mapping
from core.kernel.registry import KernelRegistry
from core.base.enums import RegistrationState
from core.kernel.issue import InterpreterError
from core.base.source_atomic import Location
from core.runtime.exceptions import ReturnException, RegistryIsolationError
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger
from core.kernel.intent_logic import IntentRole
from core.kernel.types.descriptors import TypeDescriptor, ANY_DESCRIPTOR as ANY_TYPE

if TYPE_CHECKING:
    from core.kernel import ast as ast
    from core.runtime.interfaces import IExecutionContext
    from core.runtime.interpreter.interpreter import Interpreter

from .ib_type_mapping import register_ib_type

@register_ib_type("Any")
@register_ib_type("var")
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
        
        # [IES 2.1 Refactor] 下沉至公理层能力探测
        # 针对 __call__ 消息，检查类型公理是否声明了调用能力
        if message == '__call__':
            call_trait = self.descriptor.get_call_trait()
            if call_trait and hasattr(self, 'call'):
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

    # --- [IES 2.1] 基础协议实现 ---
    def __not__(self) -> 'IbObject':
        """逻辑非运算协议"""
        # 使用 to_bool 判定并取反
        is_true = self.ib_class.registry.is_truthy(self)
        return self.ib_class.registry.box(0 if is_true else 1)

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
        [IES 2.0] 模块级消息传递核心。
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
    """[IES 2.1 Stage 5.5] 延迟字段描述符：存储 AST 节点 UID 及其可能的预评估快照。"""
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
    IBC-Inter 类对象 (元对象)。
    贯彻“一切皆对象”思想：类本身也是一个对象。
    它持有该类的元数据 (TypeDescriptor) 和运行时方法表 (vtable)。
    """
    __slots__ = ('name', 'methods', 'parent', 'default_fields', 'member_types', 'registry', 'descriptor')

    def __init__(self, name: str, parent: Optional['IbClass'] = None, registry: Optional[KernelRegistry] = None):
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

    def register_method(self, name: str, method: 'IIbFunction') -> None:
        # [IES 2.1 Security] 封印校验：禁止在 Registry READY 状态下修改虚表
        if self.registry.is_sealed:
            raise PermissionError(f"Sealed Registry Violation: Cannot register method '{name}' to class '{self.name}' in READY state.")
        self.methods[name] = method

    def register_field(self, name: str, default_value: 'IbObject') -> None:
        # [IES 2.1 Security] 封印校验
        if self.registry.is_sealed:
            raise PermissionError(f"Sealed Registry Violation: Cannot register field '{name}' to class '{self.name}' in READY state.")
        self.default_fields[name] = default_value

    def instantiate(self, args: List[IbObject], context: Optional['IExecutionContext'] = None) -> IbObject:
        instance = IbObject(self)
        
        # [IES 2.1 Refactor] 延迟执行字段初始化 (Item 2.1 Audit)
        for name, val_info in self.default_fields.items():
            if isinstance(val_info, IbDeferredField):
                if val_info.static_val is not None:
                    # 优先使用预评估好的快照
                    instance.fields[name] = val_info.static_val
                elif val_info.val_uid and context:
                    # 动态求值并尝试更新描述符以供后续实例复用 (JIT caching)
                    try:
                        # [IES 2.1 Lexical Scope] 确保在定义该字段的模块上下文中进行求值
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
                # [Active Defense] 仅支持 IbDeferredField，确保 IES 2.1 字段初始化的一致性
                instance.fields[name] = val_info
        
        init_method = self.lookup_method('__init__')
        if init_method:
            # [IES 2.1 Validation] 契约一致性校验：校验 __init__ 参数数量
            # 注意：描述符中的参数列表通常不包含 self (除非是特殊定义的)
            if init_method.descriptor:
                sig = init_method.descriptor.get_signature()
                if sig:
                    expected_params, _ = sig
                    if len(args) != len(expected_params):
                        raise InterpreterError(f"TypeError: {self.name}.__init__() expected {len(expected_params)} arguments, but got {len(args)}")
            
            init_method.call(instance, args)
        elif args:
            # 如果没有定义 __init__ 但传了参数，也是一种契约违背
            raise InterpreterError(f"TypeError: {self.name}() takes no arguments, but {len(args)} were given")
            
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
            
            # [IES 2.1 Decoupling] 实例化时传入执行上下文以支持复杂字段初始化
            # 通过 Registry 正式接口获取执行上下文
            context = self.registry.get_execution_context()
            
            return self.instantiate(args, context=context)
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
            if reg.state_level >= RegistrationState.STAGE_2_CORE_TYPES.value:
                target_class = reg.get_class("callable")
                if not target_class and reg.state_level >= RegistrationState.STAGE_4_PLUGIN_IMPL.value:
                    raise InterpreterError(f"Core Error: 'callable' class missing during STAGE {RegistrationState(reg.state_level).name}. [IES 2.0 Fatal Assertion]")
        
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

@register_ib_type("None")
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

    def to_bool(self) -> IbObject:
        """[IES 2.1] None 始终为 False"""
        return self.ib_class.registry.box(0)

    def cast_to(self, target_class: Any) -> IbObject:
        """[IES 2.1] 支持 None 的强转逻辑"""
        if target_class.name == "str":
            return self.ib_class.registry.box("None")
        if target_class.name in ("int", "float"):
            return self.ib_class.registry.box(0)
        if target_class.name == "bool":
            return self.ib_class.registry.box(0)
        return self

    def __repr__(self):
        return "null"

class IbUserFunction(IbFunction):
    """
    用户定义的 IBC 函数。
    """
    def __init__(self, node_uid: str, context: 'IExecutionContext', ib_class: Optional['IbClass'] = None, descriptor: Optional[TypeDescriptor] = None, module_name: Optional[str] = None):
        super().__init__(ib_class or context.registry.get_class("callable"))
        self.node_uid = node_uid
        self.context = context
        self._descriptor = descriptor
        self.module_name = module_name or context.current_module_name

    @property
    def descriptor(self) -> TypeDescriptor:
        return self._descriptor or super().descriptor

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """执行用户定义的函数"""
        # [IES 2.1 Context Switch] 切换到函数定义所在的模块上下文
        rt_context = self.context.runtime_context
        old_module = self.context.current_module_name
        old_scope = rt_context.current_scope
        
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
                rt_context.define_variable("self", receiver)
                
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
            for stmt_uid in body:
                self.context.visit(stmt_uid)
                
            return ib_none
        except ReturnException as e:
            return e.value
        finally:
            self.context.pop_stack()
            rt_context.exit_scope()
            # 恢复之前的模块上下文
            self.context.current_module_name = old_module
            rt_context.current_scope = old_scope

    def __repr__(self):
        node_data = self.context.get_node_data(self.node_uid)
        name = node_data.get("name", "unknown")
        return f"<Function '{name}'>"

class IbLLMFunction(IbFunction):
    """
    用户定义的 LLM 函数。
    """
    def __init__(self, node_uid: str, llm_executor: Any, context: 'IExecutionContext', descriptor: Optional[TypeDescriptor] = None, module_name: Optional[str] = None):
        super().__init__(context.registry.get_class("callable"))
        self.node_uid = node_uid
        self.llm_executor = llm_executor
        self.context = context
        self._descriptor = descriptor
        self.module_name = module_name or context.current_module_name

    @property
    def descriptor(self) -> TypeDescriptor:
        return self._descriptor or super().descriptor

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """执行 LLM 函数：负责作用域管理和参数绑定，然后分发给执行器"""
        # [IES 2.1 Context Switch] 切换到函数定义所在的模块上下文
        rt_context = self.context.runtime_context
        old_module = self.context.current_module_name
        old_scope = rt_context.current_scope
        
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
            
            # [IES 2.1 Factory] 解析呼叫级意图 (函数头上的意图)
            intent_uid = node_data.get("intent")
            call_intent = None
            if intent_uid:
                intent_data = self.context.get_node_data(intent_uid)
                # 使用工厂创建意图对象，避免局部 import
                call_intent = self.context.factory.create_intent_from_node(
                    intent_uid, 
                    intent_data, 
                    role=IntentRole.SMEAR
                )
            
            # 分发给 LLM 执行器
            # [IES 2.1 Regularization] 传递执行上下文网关，并传递解析后的意图
            return self.llm_executor.execute_llm_function(self.node_uid, self.context, call_intent=call_intent)
        finally:
            self.context.pop_stack()
            rt_context.exit_scope()
            # 恢复之前的模块上下文
            self.context.current_module_name = old_module
            rt_context.current_scope = old_scope

    def __repr__(self):
        node_data = self.context.get_node_data(self.node_uid)
        name = node_data.get("name", "unknown")
        return f"<LLMFunction '{name}'>"
