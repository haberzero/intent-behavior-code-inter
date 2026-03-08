from typing import Dict, Optional, Any
from .kernel import IbClass, IbObject, IbNativeFunction, IbNone

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
    def reset(cls):
        """
        重置引导状态 (主要用于单元测试)。
        """
        cls._class_registry.clear()
        cls.TypeClass = None
        cls.ObjectClass = None
        cls.CallableClass = None
        cls.ModuleClass = None

    @classmethod
    def initialize(cls):
        """
        核心引导流程：先分配内存，后绑定关系。
        """
        if cls.TypeClass: return # 避免重复初始化

        # Step 1: Create Type Shells (分配内存，此时 ib_class 暂未绑定)
        cls.TypeClass = IbClass("Type")
        cls.ObjectClass = IbClass("Object")
        cls.CallableClass = IbClass("callable")
        cls.ModuleClass = IbClass("Module")
        
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
        
        # Step 3: Register Core Protocols (元方法注入)
        cls.ObjectClass.register_method('toString', IbNativeFunction(lambda self: self.__repr__(), is_method=True))
        cls.ObjectClass.register_method('__to_prompt__', IbNativeFunction(lambda self: f"<Instance of {self.ib_class.name}>", is_method=True))
        cls.ObjectClass.register_method('to_bool', IbNativeFunction(lambda self: 1, is_method=True))
        
        # 基础比较逻辑：默认比较 ID (引用一致性)
        # 注意：子类 (如 Integer) 会重写 these 方法
        def _default_eq(self, other):
            from .builtins import IbInteger
            return IbInteger.from_native(1 if self == other else 0)
            
        def _default_ne(self, other):
            from .builtins import IbInteger
            return IbInteger.from_native(1 if self != other else 0)

        cls.ObjectClass.register_method('__eq__', IbNativeFunction(_default_eq, is_method=True))
        cls.ObjectClass.register_method('__ne__', IbNativeFunction(_default_ne, is_method=True))

        # 为 callable 注册 __call__ 消息实现 (调用 call 方法)
        cls.CallableClass.register_method('__call__', IbNativeFunction(lambda self, *args: self.call(IbNone(), list(args)), is_method=True))

        # 为 Type 注册 __call__ 消息实现 (实例化类)
        cls.TypeClass.register_method('__call__', IbNativeFunction(lambda self, *args: self.instantiate(list(args)), is_method=True))

    @classmethod
    def register_class(cls, ib_class: IbClass):
        """向全局表注册类，并确保其 ib_class 指向 TypeClass"""
        if cls.TypeClass and not ib_class.ib_class:
            ib_class.ib_class = cls.TypeClass
        cls._class_registry[ib_class.name] = ib_class

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
        """UTS: 统一装箱逻辑，将原生对象转为 IbObject"""
        if isinstance(val, IbObject): return val
        if val is None:
            from .builtins import IbNone
            return IbNone()
        
        # 处理循环引用
        if memo is None: memo = {}
        if id(val) in memo: return memo[id(val)]
        
        # 延迟导入以解决循环依赖
        from .builtins import IbInteger, IbFloat, IbString, IbList, IbDict, IbNone
        
        if isinstance(val, bool): return IbInteger.from_native(1 if val else 0)
        if isinstance(val, int): return IbInteger.from_native(val)
        if isinstance(val, float): return IbFloat(val)
        if isinstance(val, str): return IbString(val)
        
        if isinstance(val, list):
            # 创建空列表并缓存，防止循环引用
            res = IbList([])
            memo[id(val)] = res
            res.elements = [cls.box(i, memo) for i in val]
            return res
            
        if isinstance(val, dict):
            # 创建空字典并缓存，防止循环引用
            res = IbDict({})
            memo[id(val)] = res
            res.fields = {k: cls.box(v, memo) for k, v in val.items()}
            return res
        
        # 处理 callable
        if callable(val):
            from .kernel import IbNativeFunction
            res = IbNativeFunction(val, unbox_args=True)
            memo[id(val)] = res
            return res

        from .kernel import IbNativeObject
        res = IbNativeObject(val)
        memo[id(val)] = res
        return res
