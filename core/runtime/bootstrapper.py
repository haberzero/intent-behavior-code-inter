from typing import Dict, Optional, Any, TYPE_CHECKING
from .objects.kernel import IbClass, IbObject, IbNativeFunction, IbNativeObject, IbNone, IbBoundMethod
from core.kernel.registry import KernelRegistry
from core.kernel.factory import create_default_registry

if TYPE_CHECKING:
    from core.kernel.types.descriptors import TypeDescriptor

class Bootstrapper:
    """
    IBC-Inter 内核引导程序。
    负责解决 Type (元类) 与 Object (基类) 的循环依赖。
    并初始化全局类型系统。
    现在支持基于实例的 Registry 以实现多引擎隔离。
    """
    
    def __init__(self, registry: KernelRegistry):
        self.registry = registry
        self._token = registry.get_kernel_token() # 获取内核特权令牌
        self._class_registry: Dict[str, IbClass] = {}
        self.TypeClass: Optional[IbClass] = None
        self.ObjectClass: Optional[IbClass] = None
        self.CallableClass: Optional[IbClass] = None
        self.ModuleClass: Optional[IbClass] = None
        self.IntentClass: Optional[IbClass] = None

    @property
    def token(self) -> Any:
        return self._token

    def initialize(self, metadata_registry: Any):
        """
        核心引导流程：先声明元数据，再注入内存，最后绑定关系。
        [Active Defense] 贯彻“元数据先行”原则，内核类不再是例外。
        """
        if self.TypeClass: return # 避免重复初始化

        # 注册 Registry 辅助函数 (将实例方法绑定到 registry 实例)
        self.registry.register_box_func(self.box, self._token)
        self.registry.register_create_subclass_func(self.create_subclass, self._token)

        # Step 0: Create Core Descriptors (元数据声明)
        factory = metadata_registry.factory
        type_desc = factory.create_class("Type", is_nullable=False)
        obj_desc = factory.create_class("Object", is_nullable=True)
        callable_desc = factory.create_class("callable", is_nullable=True)
        module_desc = factory.create_class("IbModule", is_nullable=True)
        intent_desc = factory.create_class("Intent", is_nullable=True)
        
        # 内核类不属于用户定义类
        for d in [type_desc, obj_desc, callable_desc, module_desc, intent_desc]:
            d.is_user_defined = False

        # Step 1: Create Type Shells (注入内存)
        self.TypeClass = IbClass("Type", registry=self.registry)
        self.ObjectClass = IbClass("Object", registry=self.registry)
        self.CallableClass = IbClass("callable", registry=self.registry)
        self.ModuleClass = IbClass("IbModule", registry=self.registry)
        self.IntentClass = IbClass("Intent", registry=self.registry)
        
        # Step 2: Wire Relationships (打破循环并绑定描述符)
        self.TypeClass.ib_class = self.TypeClass
        self.ObjectClass.ib_class = self.TypeClass
        self.CallableClass.ib_class = self.TypeClass
        self.ModuleClass.ib_class = self.TypeClass
        self.IntentClass.ib_class = self.TypeClass
        
        # 强制绑定描述符
        self.TypeClass.descriptor = type_desc
        self.ObjectClass.descriptor = obj_desc
        self.CallableClass.descriptor = callable_desc
        self.ModuleClass.descriptor = module_desc
        self.IntentClass.descriptor = intent_desc

        # Object 没有父类
        self.ObjectClass.parent = None
        # Type, callable, Module 的父类是 Object
        self.TypeClass.parent = self.ObjectClass
        self.CallableClass.parent = self.ObjectClass
        self.ModuleClass.parent = self.ObjectClass
        self.IntentClass.parent = self.ObjectClass
        
        # 注册到本实例表并同步到元数据注册表
        self.register_class(self.TypeClass, type_desc)
        self.register_class(self.ObjectClass, obj_desc)
        self.register_class(self.CallableClass, callable_desc)
        self.register_class(self.ModuleClass, module_desc)
        self.register_class(self.IntentClass, intent_desc)
        
        # Step 3: Register Core Protocols (元方法注入)
        # (后续逻辑保持不变，用于补全成员元数据)
        self.ObjectClass.register_method('toString', IbNativeFunction(lambda self: self.__repr__(), is_method=True, ib_class=self.ObjectClass))
        self.ObjectClass.register_method('__to_prompt__', IbNativeFunction(lambda self: f"<Instance of {self.ib_class.name}>", is_method=True, ib_class=self.ObjectClass))
        self.ObjectClass.register_method('to_bool', IbNativeFunction(lambda self: 1, is_method=True, ib_class=self.ObjectClass))
        
        # 逻辑非协议 (Active Defense)
        def _default_not(self):
            bool_val = self.receive('to_bool', []).to_native()
            return self.ib_class.registry.box(0 if bool_val else 1)
            
        self.ObjectClass.register_method('__not__', IbNativeFunction(_default_not, is_method=True, ib_class=self.ObjectClass))

        # 属性访问协议
        def _default_getattr(self, name_obj):
            name = name_obj.to_native()
            # 1. 优先查字段
            if name in self.fields:
                return self.fields[name]
            # 2. 其次查方法并返回绑定方法 (Bound Method)
            method = self.ib_class.lookup_method(name)
            if method:
                return IbBoundMethod(self, method)
            return self.ib_class.registry.get_none()

        def _default_setattr(self, name_obj, val):
            self.fields[name_obj.to_native()] = val
            return self.ib_class.registry.get_none()

        self.ObjectClass.register_method('__getattr__', IbNativeFunction(_default_getattr, is_method=True, ib_class=self.ObjectClass))
        self.ObjectClass.register_method('__setattr__', IbNativeFunction(_default_setattr, is_method=True, ib_class=self.ObjectClass))

        # 基础比较逻辑：默认比较 ID (引用一致性)
        def _default_eq(self, other):
            return self.ib_class.registry.box(1 if self == other else 0)
            
        def _default_ne(self, other):
            return self.ib_class.registry.box(1 if self != other else 0)

        self.ObjectClass.register_method('__eq__', IbNativeFunction(_default_eq, is_method=True, ib_class=self.ObjectClass))
        self.ObjectClass.register_method('__ne__', IbNativeFunction(_default_ne, is_method=True, ib_class=self.ObjectClass))

        # 为 callable 注册 __call__ 消息实现 (调用 call 方法)
        self.CallableClass.register_method('__call__', IbNativeFunction(lambda self, *args: self.call(self.ib_class.registry.get_none(), list(args)), is_method=True, ib_class=self.CallableClass))

        # 为 Type 注册 __call__ 消息实现 (实例化类)
        self.TypeClass.register_method('__call__', IbNativeFunction(lambda self, *args: self.instantiate(list(args)), is_method=True, ib_class=self.TypeClass))

    def register_class(self, ib_class: IbClass, descriptor: 'TypeDescriptor'):
        """向实例表注册类，并确保其 ib_class 指向 TypeClass。强制绑定描述符。"""
        if self.TypeClass and not ib_class.ib_class:
            ib_class.ib_class = self.TypeClass
        self._class_registry[ib_class.name] = ib_class
        self.registry.register_class(ib_class.name, ib_class, self._token, descriptor=descriptor)

    def get_class(self, name: str) -> Optional[IbClass]:
        return self._class_registry.get(name)

    def get_all_classes(self) -> Dict[str, IbClass]:
        return dict(self._class_registry)

    def create_subclass(self, registry: KernelRegistry, name: str, descriptor: 'TypeDescriptor', parent_name: str = "Object") -> IbClass:
        """快速创建子类的便捷方法。如果类已存在，则返回现有实例。强制绑定描述符。"""
        if name in self._class_registry:
            return self._class_registry[name]
            
        parent = self.get_class(parent_name)
        if not parent and name != "Object": # Object has no parent
            raise ValueError(f"Parent class '{parent_name}' not found")
        
        new_class = IbClass(name, parent=parent, registry=registry)
        self.register_class(new_class, descriptor)
        return new_class

    def box(self, registry: KernelRegistry, val: Any, memo: Optional[Dict[int, IbObject]] = None) -> IbObject:
        """
        UTS: 统一装箱逻辑。
        """
        if isinstance(val, IbObject): return val
        if val is None:
            return registry.get_none()
        
        # 处理循环引用 (主要针对列表/字典等容器)
        if memo is None: memo = {}
        if id(val) in memo: return memo[id(val)]
        
        # 1. 尝试从 Registry 获取预注册的工厂函数
        boxer_func = registry.get_boxer(type(val))
        if boxer_func:
            return boxer_func(registry, val, memo)

        # 2. Callable 与 Native 对象兜底
        if callable(val):
            # 获取 None 类或 Object 类
            callable_class = self.get_class("callable") or self.get_class("Object")
            res = IbNativeFunction(val, unbox_args=True, ib_class=callable_class)
            memo[id(val)] = res
            return res

        obj_class = self.get_class("Object")
        res = IbNativeObject(val, ib_class=obj_class)
        memo[id(val)] = res
        return res
