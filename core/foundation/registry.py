from typing import Any, Dict, Optional

from enum import Enum, auto

class PrivilegeLevel(Enum):
    KERNEL = auto()    # 内核级：允许修改核心工厂、封印结构
    EXTENSION = auto() # 扩展级：允许注册普通类、注入元数据
    UNAUTHORIZED = auto()

class Registry:
    """
    IBC-Inter 内核对象注册表。
    用于解耦 Kernel, Builtins 和 Bootstrapper 之间的循环引用。
    [Active Defense] 增强的令牌审计机制，区分内核特权与普通扩展权限。
    """
    def __init__(self):
        self._classes: Dict[str, Any] = {}
        self._none_instance: Any = None
        self._box_func: Any = None
        self._create_subclass_func: Any = None
        self._boxers: Dict[type, Any] = {} # py_type -> Callable[[Any], IbObject]
        self._int_cache: Dict[int, Any] = {} # 小整数驻留缓存 (引擎实例隔离)
        
        # [Isolation] 元数据注册表 (UTS 驱动)
        self._metadata_registry: Any = None

        # [Active Defense] 令牌机制
        self._kernel_token = object()
        self._extension_token = object()
        self._kernel_token_granted = False
        self._extension_token_granted = False
        
        self._is_structure_sealed = False
        self._is_classes_sealed = False

    @property
    def is_initialized(self) -> bool:
        """检查注册表是否已完成核心初始化并封印。"""
        return self._is_structure_sealed

    def get_kernel_token(self) -> Any:
        """获取内核特权令牌。仅允许引导程序调用一次。"""
        if self._kernel_token_granted:
            return None
        self._kernel_token_granted = True
        return self._kernel_token

    def get_extension_token(self) -> Any:
        """获取扩展权限令牌。供插件加载系统使用。"""
        # 扩展令牌可以多次获取，但其权限受限
        return self._extension_token

    def _get_privilege(self, token: Any) -> PrivilegeLevel:
        if token is self._kernel_token:
            return PrivilegeLevel.KERNEL
        if token is self._extension_token:
            return PrivilegeLevel.EXTENSION
        return PrivilegeLevel.UNAUTHORIZED

    def _verify_kernel(self, token: Any):
        if self._get_privilege(token) != PrivilegeLevel.KERNEL:
            raise PermissionError("Registry: Kernel privilege required.")

    def _verify_structure(self, token: Any):
        if self._is_structure_sealed:
            raise PermissionError("Registry: Structure is sealed.")
        self._verify_kernel(token)

    def _verify_class_registration(self, token: Any):
        if self._is_classes_sealed:
            raise PermissionError("Registry: Class registration is sealed.")
        priv = self._get_privilege(token)
        if priv not in (PrivilegeLevel.KERNEL, PrivilegeLevel.EXTENSION):
            raise PermissionError("Registry: Unauthorized class registration.")

    def seal_structure(self, token: Any):
        """封印注册表结构（装箱、创建类等核心工厂函数）。"""
        self._verify_structure(token)
        self._is_structure_sealed = True

    def seal_classes(self, token: Any):
        """封印类注册表。封印后禁止注册任何新类。"""
        self._verify_kernel(token)
        self._is_classes_sealed = True

    # --- 注册接口 (需校验令牌) ---

    def get_metadata_registry(self) -> Any:
        """获取元数据注册表实例。"""
        return self._metadata_registry

    def register_boxer(self, py_type: type, boxer_func: Any, token: Any):
        self._verify_structure(token)
        self._boxers[py_type] = boxer_func

    def register_none(self, instance: Any, token: Any):
        self._verify_structure(token)
        self._none_instance = instance

    def register_box_func(self, func: Any, token: Any):
        self._verify_structure(token)
        self._box_func = func

    def register_create_subclass_func(self, func: Any, token: Any):
        self._verify_structure(token)
        self._create_subclass_func = func

    def register_metadata_registry(self, metadata_registry: Any, token: Any):
        """注册元数据注册表实例。"""
        self._verify_kernel(token)
        self._metadata_registry = metadata_registry

    def create_instance(self, class_name: str, *args, **kwargs) -> Any:
        """
        [IES 2.0 Factory] 统一对象实例化入口。
        确保每个实例都绑定到当前的 Registry，并根据真相源获取类定义。
        """
        ib_class = self.get_class(class_name)
        if not ib_class:
            raise ValueError(f"Registry: Class '{class_name}' not found.")
        
        # 优先调用类对象的 instantiate 方法
        if hasattr(ib_class, 'instantiate'):
            # 这里的 args 应该是 IbObject 列表
            return ib_class.instantiate(list(args))
        
        # Fallback: 如果是普通 Python 类 (例如在引导阶段)
        return ib_class(*args, **kwargs)

    def register_class(self, name: str, ib_class: Any, token: Any, descriptor: Any):
        """
        注册类（内置或用户定义），并强制关联其 UTS 描述符。
        [Active Defense] 拒绝任何无元数据描述的裸类注入。
        """
        self._verify_class_registration(token)
        
        if not descriptor:
            raise ValueError(f"Registry: Cannot register class '{name}' without a UTS descriptor.")

        self._classes[name] = ib_class
        
        # [IES 2.0] 绑定注册表引用
        if hasattr(ib_class, 'registry'):
            ib_class.registry = self
            
        # 强制绑定描述符到类对象上
        if hasattr(ib_class, 'descriptor'):
            ib_class.descriptor = descriptor
            
        # 自动同步到元数据注册表
        if self._metadata_registry:
            self._metadata_registry.register(descriptor)

    def register_function(self, name: str, descriptor: Any, token: Any):
        """注册全局函数元数据 (仅用于编译器发现)"""
        self._verify_class_registration(token)
        if self._metadata_registry:
            self._metadata_registry.register(descriptor)

    def export_manifest(self) -> Dict[str, Any]:
        """导出当前 Registry 的类型清单快照 (供编译器使用)"""
        return dict(self._classes)

    # --- 开放查询接口 (无需令牌) ---

    def get_boxer(self, py_type: type) -> Any:
        return self._boxers.get(py_type)

    def get_class(self, name: str) -> Any:
        return self._classes.get(name)

    def get_all_classes(self) -> Dict[str, Any]:
        return dict(self._classes)

    def get_int_cache(self) -> Dict[int, Any]:
        return self._int_cache

    def get_none(self) -> Any:
        return self._none_instance

    def create_subclass(self, name: str, descriptor: Any, parent_name: str = "Object") -> Any:
        """[Authorized] 通过内核绑定的工厂方法创建类，支持动态继承链。强制绑定描述符。"""
        if self._create_subclass_func:
            return self._create_subclass_func(self, name, descriptor, parent_name)
        return None

    def box(self, value: Any, memo: Optional[Dict[int, Any]] = None) -> Any:
        """[Authorized] 通过内核绑定的工厂方法装箱，支持多引擎实例。"""
        if self._box_func:
            return self._box_func(self, value, memo)
        return value
