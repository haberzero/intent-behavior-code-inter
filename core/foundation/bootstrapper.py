from typing import Dict, Optional, Any
from .kernel import IbClass, IbObject, IbNativeFunction, IbNativeObject, IbNone
from .registry import Registry

class Bootstrapper:
    """
    IBC-Inter 内核引导程序。
    负责解决 Type (元类) 与 Object (基类) 的循环依赖。
    并初始化全局类型系统。
    """
    
    # 全局类注册表 (模拟 .rodata 段中的虚表映射)
    _class_registry: Dict[str, IbClass] = {}
    
    TypeClass: Optional[IbClass] = None
    ObjectClass: Optional[IbClass] = None
    CallableClass: Optional[IbClass] = None
    ModuleClass: Optional[IbClass] = None

    @classmethod
    def initialize(cls):
        """
        核心引导流程：先分配内存，后绑定关系。
        """
        if cls.TypeClass: return # 避免重复初始化

        # 延迟导入以打破核心引导循环
        from .kernel import IbClass, IbNativeFunction, IbNone

        # 注册 Registry 辅助函数
        Registry.register_box_func(cls.box)
        Registry.register_create_subclass_func(cls.create_subclass)

        # Step 1: Create Type Shells (分配内存，此时 ib_class 暂未绑定)
        cls.TypeClass = IbClass("Type")
        cls.ObjectClass = IbClass("Object")
        cls.CallableClass = IbClass("callable")
        cls.ModuleClass = IbClass("IbModule")
        
        # Step 2: Wire Relationships (打破循环)
        cls.TypeClass.ib_class = cls.TypeClass
        cls.ObjectClass.ib_class = cls.TypeClass
        cls.CallableClass.ib_class = cls.TypeClass
        cls.ModuleClass.ib_class = cls.TypeClass
        
        # Object 没有父类
        cls.ObjectClass.parent = None
        # Type, callable, Module 的父类是 Object
        cls.TypeClass.parent = cls.ObjectClass
        cls.CallableClass.parent = cls.ObjectClass
        cls.ModuleClass.parent = cls.ObjectClass
        
        # 注册到全局表
        cls.register_class(cls.TypeClass)
        cls.register_class(cls.ObjectClass)
        cls.register_class(cls.CallableClass)
        cls.register_class(cls.ModuleClass)
        
        # 注册 None 单例
        Registry.register_none(IbNone())
        
        # Step 3: Register Core Protocols (元方法注入)
        cls.ObjectClass.register_method('toString', IbNativeFunction(lambda self: self.__repr__(), is_method=True))
        cls.ObjectClass.register_method('__to_prompt__', IbNativeFunction(lambda self: f"<Instance of {self.ib_class.name}>", is_method=True))
        cls.ObjectClass.register_method('to_bool', IbNativeFunction(lambda self: 1, is_method=True))
        
        # 属性访问协议
        def _default_getattr(self, name_obj):
            name = name_obj.to_native()
            # 1. 优先查字段
            if name in self.fields:
                return self.fields[name]
            # 2. 其次查方法并返回绑定方法 (Bound Method)
            method = self.ib_class.lookup_method(name)
            if method:
                from .kernel import IbBoundMethod
                return IbBoundMethod(self, method)
            return Registry.get_none()

        def _default_setattr(self, name_obj, val):
            self.fields[name_obj.to_native()] = val
            return Registry.get_none()

        cls.ObjectClass.register_method('__getattr__', IbNativeFunction(_default_getattr, is_method=True))
        cls.ObjectClass.register_method('__setattr__', IbNativeFunction(_default_setattr, is_method=True))

        # 基础比较逻辑：默认比较 ID (引用一致性)
        # 注意：子类 (如 Integer) 会重写 these 方法
        def _default_eq(self, other):
            return Registry.box(1 if self == other else 0)
            
        def _default_ne(self, other):
            return Registry.box(1 if self != other else 0)

        cls.ObjectClass.register_method('__eq__', IbNativeFunction(_default_eq, is_method=True))
        cls.ObjectClass.register_method('__ne__', IbNativeFunction(_default_ne, is_method=True))

        # 为 callable 注册 __call__ 消息实现 (调用 call 方法)
        cls.CallableClass.register_method('__call__', IbNativeFunction(lambda self, *args: self.call(Registry.get_none(), list(args)), is_method=True))

        # 为 Type 注册 __call__ 消息实现 (实例化类)
        cls.TypeClass.register_method('__call__', IbNativeFunction(lambda self, *args: self.instantiate(list(args)), is_method=True))

    @classmethod
    def register_class(cls, ib_class: IbClass):
        """向全局表注册类，并确保其 ib_class 指向 TypeClass"""
        if cls.TypeClass and not ib_class.ib_class:
            ib_class.ib_class = cls.TypeClass
        cls._class_registry[ib_class.name] = ib_class
        Registry.register_class(ib_class.name, ib_class)

    @classmethod
    def get_class(cls, name: str) -> Optional[IbClass]:
        return cls._class_registry.get(name)

    @classmethod
    def get_all_classes(cls) -> Dict[str, IbClass]:
        return dict(cls._class_registry)

    @classmethod
    def create_subclass(cls, name: str, parent_name: str = "Object") -> IbClass:
        """快速创建子类的便捷方法。如果类已存在，则返回现有实例。"""
        if name in cls._class_registry:
            return cls._class_registry[name]
            
        parent = cls.get_class(parent_name)
        if not parent and name != "Object": # Object has no parent
            raise ValueError(f"Parent class '{parent_name}' not found")
        
        new_class = IbClass(name, parent=parent)
        cls.register_class(new_class)
        return new_class

    @classmethod
    def box(cls, val: Any, memo: Optional[Dict[int, IbObject]] = None) -> IbObject:
        """
        UTS: 统一装箱逻辑。
        现在它完全解耦：不了解任何具体内置类，全部通过 Registry 路由。
        """
        if isinstance(val, IbObject): return val
        if val is None:
            return Registry.get_none()
        
        # 处理循环引用 (主要针对列表/字典等容器)
        if memo is None: memo = {}
        if id(val) in memo: return memo[id(val)]
        
        # 1. 尝试从 Registry 获取预注册的工厂函数 (消除对 Builtins 的所有引用)
        boxer_func = Registry.get_boxer(type(val))
        if boxer_func:
            return boxer_func(val, memo)

        # 2. Callable 与 Native 对象兜底 (通过 Registry 注册)
        if callable(val):
            res = IbNativeFunction(val, unbox_args=True)
            memo[id(val)] = res
            return res

        res = IbNativeObject(val)
        memo[id(val)] = res
        return res
