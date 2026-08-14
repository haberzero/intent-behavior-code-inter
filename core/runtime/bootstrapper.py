from typing import Dict, Optional, Any
from core.base.enums import Provenance, Visibility
from .objects.kernel import IbClass, IbObject, IbNativeFunction, IbNativeObject, IbNone, IbBoundMethod
from core.kernel.registry import KernelRegistry
from core.kernel.factory import create_default_registry
from core.kernel.spec import IbSpec, TypeDef
from core.kernel.issue import InterpreterError
from core.runtime.shared.waitable import Waitable

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
        # [S3 单类表] 不再维护独立 _class_registry——KernelRegistry._classes 是
        # 运行期类表唯一权威（Bootstrapper 全委托）。此前双表（Bootstrapper
        # 影子表 + KernelRegistry 权威表）是历史包袱：Enum 仅注册权威表不经
        # 影子表，两处 [Enum Hook] 兜底即为弥合缺口；单表后自动消除。
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
        type_desc = factory.create_class("Type")
        obj_desc = factory.create_class("Object")
        callable_desc = factory.create_class("callable")
        module_desc = factory.create_class("IbModule")
        intent_desc = factory.create_class("Intent")
        intent_stack_desc = factory.create_class("IntentStack")

        # 内核类不属于用户定义类
        for d in [type_desc, obj_desc, callable_desc, module_desc, intent_desc, intent_stack_desc]:
            d.provenance = Provenance.KERNEL_NATIVE
            d.visibility = Visibility.PRELUDE_VISIBLE

        # Step 1: Create Type Shells (注入内存)
        self.TypeClass = IbClass("Type", registry=self.registry)
        self.ObjectClass = IbClass("Object", registry=self.registry)
        self.CallableClass = IbClass("callable", registry=self.registry)
        self.ModuleClass = IbClass("IbModule", registry=self.registry)
        self.IntentClass = IbClass("Intent", registry=self.registry)
        self.IntentStackClass = IbClass("IntentStack", registry=self.registry)

        # Step 2: Wire Relationships (打破循环并绑定描述符)
        self.TypeClass.ib_class = self.TypeClass
        self.ObjectClass.ib_class = self.TypeClass
        self.CallableClass.ib_class = self.TypeClass
        self.ModuleClass.ib_class = self.TypeClass
        self.IntentClass.ib_class = self.TypeClass
        self.IntentStackClass.ib_class = self.TypeClass

        # 强制绑定描述符
        self.TypeClass.spec = type_desc
        self.ObjectClass.spec = obj_desc
        self.CallableClass.spec = callable_desc
        self.ModuleClass.spec = module_desc
        self.IntentClass.spec = intent_desc
        self.IntentStackClass.spec = intent_stack_desc

        # Object 没有父类
        self.ObjectClass.parent = None
        # Type, callable, Module 的父类是 Object
        self.TypeClass.parent = self.ObjectClass
        self.CallableClass.parent = self.ObjectClass
        self.ModuleClass.parent = self.ObjectClass
        self.IntentClass.parent = self.ObjectClass
        self.IntentStackClass.parent = self.ObjectClass

        # 注册到本实例表并同步到元数据注册表
        self.register_class(self.TypeClass, type_desc)
        self.register_class(self.ObjectClass, obj_desc)
        self.register_class(self.CallableClass, callable_desc)
        self.register_class(self.ModuleClass, module_desc)
        self.register_class(self.IntentClass, intent_desc)
        self.register_class(self.IntentStackClass, intent_stack_desc)
        
        # Step 3: Register Core Protocols (元方法注入)
        # (后续逻辑保持不变，用于补全成员元数据)
        self.ObjectClass.register_method('toString', IbNativeFunction(lambda self: self.__repr__(), is_method=True, ib_class=self.ObjectClass))
        self.ObjectClass.register_method('__to_prompt__', IbNativeFunction(lambda self: f"<Instance of {self.ib_class.name}>", is_method=True, ib_class=self.ObjectClass))
        self.ObjectClass.register_method('to_bool', IbNativeFunction(lambda self: 1, is_method=True, ib_class=self.ObjectClass))
        
        # 逻辑非协议 (Active Defense)
        def _default_not(self):
            bool_val = self.receive('to_bool', []).to_native()
            return self.ib_class.registry.box(False if bool_val else True)
            
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
            # 3. 未声明属性：fail-fast（RUN_ATTRIBUTE_ERROR）。
            #    此前静默返回 None——错误值流入用户程序（读取未声明属性得到
            #    None，随后调用报困惑的 "Object of type 'None' has no method
            #    '__call__'"）。属性缺失是程序错误，按工作模式定论应显式报错。
            raise InterpreterError(
                f"AttributeError: '{self.ib_class.name}' object has no attribute '{name}'",
                error_code="RUN_ATTRIBUTE_ERROR",
            )

        def _default_setattr(self, name_obj, val):
            attr = name_obj.to_native()
            # 统一 Optional 值模型：字段声明为 Optional[T] 时，写入前按字段
            # 声明类型包装（空值 → IbOptional(is_some=False)，与局部变量/
            # 参数/返回路径一致）。字段类型经 member_types 缓存沿继承链解析
            # （子类/父类字段均命中），无缓存/非 Optional 原样写入。
            self.fields[attr] = self.ib_class._wrap_field_value(attr, val)
            return self.ib_class.registry.get_none()

        self.ObjectClass.register_method('__getattr__', IbNativeFunction(_default_getattr, is_method=True, ib_class=self.ObjectClass))
        self.ObjectClass.register_method('__setattr__', IbNativeFunction(_default_setattr, is_method=True, ib_class=self.ObjectClass))

        # 基础比较逻辑：默认比较 ID (引用一致性)，返回 bool 类型
        def _default_eq(self, other):
            return self.ib_class.registry.box(True if self is other else False)
            
        def _default_ne(self, other):
            return self.ib_class.registry.box(False if self is other else True)

        self.ObjectClass.register_method('__eq__', IbNativeFunction(_default_eq, is_method=True, ib_class=self.ObjectClass))
        self.ObjectClass.register_method('__ne__', IbNativeFunction(_default_ne, is_method=True, ib_class=self.ObjectClass))

        # 为 callable 注册 __call__ 消息实现 (调用 call 方法)
        self.CallableClass.register_method('__call__', IbNativeFunction(lambda self, *args: self.call(self.ib_class.registry.get_none(), list(args)), is_method=True, ib_class=self.CallableClass))

        # 为 Type 注册 __call__ 消息实现 (实例化类)
        self.TypeClass.register_method('__call__', IbNativeFunction(lambda self, *args: self.instantiate(list(args)), is_method=True, ib_class=self.TypeClass))

    def register_class(self, ib_class: IbClass, spec: 'IbSpec'):
        """向单类表（KernelRegistry._classes）注册类，并确保其 ib_class 指向 TypeClass。

        [S3 单类表] 不再写影子表——KernelRegistry.register_class 是唯一写入
        点（键 = spec.qualified_name，与编译期 spec 身份 (module_path, name)
        对齐）。[Module Identity] 跨模块同名用户类独立注册（geo.Box /
        graph.Box / main.Box），内置类 module_path 为 None，键 = 裸名。
        """
        if self.TypeClass and not ib_class.ib_class:
            ib_class.ib_class = self.TypeClass
        self.registry.register_class(ib_class.name, ib_class, self._token, spec=spec)

    def get_class(self, name: str, module: Optional[str] = None) -> Optional[IbClass]:
        """module 感知类查找（委托 KernelRegistry 单表，逻辑同构）。"""
        return self.registry.get_class(name, module=module)

    def get_all_classes(self) -> Dict[str, IbClass]:
        """全部类（委托 KernelRegistry 单表）。"""
        return self.registry.get_all_classes()

    def create_subclass(self, registry: KernelRegistry, name: str, spec: 'IbSpec', parent_name: str = "Object") -> IbClass:
        """快速创建子类的便捷方法。如果类已存在，则返回现有实例。强制绑定 spec。

        [S3 单类表] 存在性检查与父查找均委托 KernelRegistry（唯一权威表，
        涵盖此前仅注册于权威表的 Enum 等内置类——不再需要 [Enum Hook] 兜底）。
        ``name`` 可为裸类名（``Box[int]``）或 qualified 名（``geo.Box[int]``）；
        注册键 = 描述符 ``qualified_name``（跨模块同名类独立）。裸类名自末段
        提取（module 可含点，类名不可含点）。父类查找 module 感知（spec 的
        module_path 作为父模块上下文——父类与子类同模块，parser 仅支持单标识符
        父名；qualified 父名直接精确命中）。
        """
        key = spec.qualified_name if spec is not None else name
        if self.registry.get_class(key) is not None:
            return self.registry.get_class(key)

        bare = name.rsplit(".", 1)[-1] if "." in name else name
        module = spec.module_path if spec is not None else None
        parent = self.registry.get_class(parent_name, module=module)

        if not parent and parent_name != "Object": # Object has no parent
            raise ValueError(f"Parent class '{parent_name}' not found")

        new_class = IbClass(bare, parent=parent, registry=registry)
        self.register_class(new_class, spec)
        return new_class

    def box(self, registry: KernelRegistry, val: Any, memo: Optional[Dict[int, IbObject]] = None) -> IbObject:
        """
        UTS: 统一装箱逻辑。
        """
        if isinstance(val, IbObject): return val
        if val is None:
            return registry.get_none()
        # Waitable（异步操作句柄：LLMFuture / HostAwaitable）原样透传，不装箱——
        # 装箱会破坏其 Waitable 身份，导致 VM 调度器无法识别并挂起。Waitable 是
        # 异步基础设施对象，非普通值，不应被包装为 primitive。
        if isinstance(val, Waitable):
            return val
        # Uncertain 字面量哨兵：Uncertain 关键字被解析为此特殊字符串常量，
        # 此处将其映射到 llm_uncertain 单例，与 None → get_none() 的模式完全对称。
        if val == "__IBCI_UNCERTAIN_LITERAL__":
            return registry.get_llm_uncertain()
        
        # 处理循环引用 (主要针对列表/字典等容器)
        if memo is None: memo = {}
        if id(val) in memo: return memo[id(val)]
        
        # 1. 尝试从 Registry 获取预注册的工厂函数
        boxer_func = registry.get_boxer(type(val))
        if boxer_func:
            return boxer_func(registry, val, memo)

        # 2. Callable 与 Native 对象映射路径
        if callable(val):
            # 获取 None 类或 Object 类（委托 KernelRegistry 单表）
            callable_class = registry.get_class("callable") or registry.get_class("Object")
            res = IbNativeFunction(val, unbox_args=True, ib_class=callable_class)
            memo[id(val)] = res
            return res

        obj_class = registry.get_class("Object")
        res = IbNativeObject(val, ib_class=obj_class)
        memo[id(val)] = res
        return res
