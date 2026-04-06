from typing import Any, Dict, List, Optional, Callable, Union, TYPE_CHECKING
import threading
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_trace
from core.base.enums import PrivilegeLevel, RegistrationState

if TYPE_CHECKING:
    from core.kernel.types.descriptors import TypeDescriptor
    from core.kernel.axioms.protocols import TypeAxiom
    from core.kernel.axioms.registry import AxiomRegistry
    from core.kernel.interfaces import IExecutionContext

class KernelRegistry:
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
        
        # 绑定执行上下文数据，不再持有整个解释器实例
        self._execution_context: Optional[Any] = None
        self._execution_context_lock = threading.Lock()
        self._registry_lock = threading.Lock()
        
        # 注册状态机级别。默认为 1。
        self._state_level = 1
        
        # [Isolation] 元数据注册表 (UTS 驱动)
        self._metadata_registry: Any = None

        # [Active Defense] 令牌机制
        self._kernel_token = object()
        self._extension_token = object()
        self._kernel_token_granted = False
        self._extension_token_granted = False
        
        self._is_structure_sealed = False
        self._is_classes_sealed = False

        # [Builtin Instances] 内置单例实例 (如 IntentStack)
        self._builtin_instances: Dict[str, Any] = {}

    @property
    def state_level(self) -> int:
        return self._state_level

    def set_state_level(self, new_level: int, token: Any):
        """[Mechanism] 跃迁注册状态级别。必须持有内核令牌且符合单向增长规则。"""
        self._verify_kernel(token)
        if new_level <= self._state_level:
            raise PermissionError(f"Registry: Invalid level transition from {self._state_level} to {new_level}. Levels must progress forward.")
        
        core_trace(CoreModule.INTERPRETER, DebugLevel.BASIC, f"Registry level transition: {self._state_level} -> {new_level}")
        self._state_level = new_level

    def verify_level(self, required_level: int):
        """[Mechanism] 校验当前级别是否完全匹配。"""
        if self._state_level != required_level:
            raise PermissionError(f"Registry: Operation requires level {required_level}, but current level is {self._state_level}")

    def verify_level_at_least(self, minimum_level: int):
        """[Mechanism] 校验当前级别是否达到最小要求。"""
        if self._state_level < minimum_level:
            raise PermissionError(f"Registry: Operation requires at least level {minimum_level}, but current level is {self._state_level}")

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

    @property
    def is_sealed(self) -> bool:
        return self._is_classes_sealed

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

    def register_builtin_instance(self, name: str, instance: Any, token: Any = None):
        """
        注册内置单例实例（如 IntentStack）。
        内置实例在结构封印后仍然可以注册，但仅限初始化阶段。
        """
        if self._is_structure_sealed:
            raise PermissionError("Registry: Cannot register builtin instance after structure is sealed.")
        self._builtin_instances[name] = instance

    def get_builtin_instance(self, name: str) -> Optional[Any]:
        """获取内置单例实例。"""
        return self._builtin_instances.get(name)

    def set_execution_context(self, context: 'IExecutionContext', token: Any):
        """注册执行上下文引用，仅内核可调。"""
        self._verify_kernel(token)
        if self._is_structure_sealed:
            raise PermissionError("Registry: Cannot re-bind ExecutionContext after structure is sealed.")
        with self._execution_context_lock:
            self._execution_context = context

    def get_execution_context(self) -> Optional['IExecutionContext']:
        """获取执行上下文引用。
        
        注意：此方法供内核内部使用（IbClass 实例化等）。
        在 Registry 封印后返回已设置的上下文引用。
        
        Returns:
            IExecutionContext 或 None（如果尚未设置）
        """
        with self._execution_context_lock:
            return self._execution_context

    def create_instance(self, class_name: str, *args, **kwargs) -> Any:
        """
        统一对象实例化入口。
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

    def register_class(self, name: str, ib_class: Any, token: Any, descriptor: 'TypeDescriptor'):
        """
        注册类（内置或用户定义），并强制关联其 UTS 描述符。
        [Active Defense] 拒绝任何无元数据描述或名称不匹配的裸类注入。
        """
        self._verify_class_registration(token)
        
        if not descriptor:
            raise ValueError(f"Registry: Cannot register class '{name}' without a UTS descriptor.")
            
        if descriptor.name != name:
             raise ValueError(f"Registry: Descriptor name '{descriptor.name}' does not match registered name '{name}'.")

        if name in self._classes:
             raise ValueError(f"Registry: Class '{name}' is already registered. Duplicate registration is forbidden in strict mode.")

        # 自动同步到元数据注册表，并获取克隆后的隔离副本
        if self._metadata_registry:
            descriptor = self._metadata_registry.register(descriptor)
            
        # 强制绑定描述符到类对象上 (此时 descriptor 已经是注册表返回的隔离副本)
        ib_class.descriptor = descriptor
        self._classes[name] = ib_class
        
        # 绑定注册表引用
        if hasattr(ib_class, 'registry'):
            ib_class.registry = self

    def register_function(self, name: str, descriptor: 'TypeDescriptor', token: Any):
        """注册全局函数元数据 (仅用于编译器发现)"""
        self._verify_class_registration(token)
        if descriptor.name != name:
             raise ValueError(f"Registry: Function descriptor name '{descriptor.name}' does not match registered name '{name}'.")
             
        # 自动同步到元数据注册表，并获取克隆后的隔离副本
        if self._metadata_registry:
            descriptor = self._metadata_registry.register(descriptor)

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

    def create_subclass(self, name: str, descriptor: 'TypeDescriptor', parent_name: str = "Object") -> Any:
        """[Authorized] 通过内核绑定的工厂方法创建类。强制校验封印状态。"""
        # 类注册封印后，禁止通过任何途径（包括工厂）创建新类
        if self._is_classes_sealed:
            raise PermissionError(f"Sealed Registry Violation: Cannot create subclass '{name}' after registry is sealed.")
            
        if not descriptor:
            raise ValueError(f"Registry: Cannot create subclass '{name}' without a UTS descriptor.")
        if descriptor.name != name:
            raise ValueError(f"Registry: Subclass descriptor name '{descriptor.name}' does not match '{name}'.")
            
        if self._create_subclass_func:
            return self._create_subclass_func(self, name, descriptor, parent_name)
        return None

    def box(self, value: Any, memo: Optional[Dict[int, Any]] = None) -> Any:
        """[Authorized] 通过内核绑定的工厂方法装箱，支持多引擎实例。"""
        if self._box_func:
            return self._box_func(self, value, memo)
        return value

    def is_truthy(self, obj: Any) -> bool:
        """ 判定对象的真值 (Truthy)。"""
        if obj is None or obj is self._none_instance:
            return False
        if hasattr(obj, 'to_bool'):
            res = obj.to_bool()
            # to_bool 应该返回 IbInteger(0 或 1)
            return bool(res.value) if hasattr(res, 'value') else bool(res)
        if hasattr(obj, 'value'):
            return bool(obj.value)
        return True

    def clone(self) -> 'KernelRegistry':
        """
        创建 KernelRegistry 的浅克隆。
        类定义和函数通过引用共享，但 MetadataRegistry 进行深克隆以确保类型隔离。
        用于 spawn_interpreter 创建隔离的解释器实例。
        """
        new_registry = KernelRegistry()
        new_registry._classes = dict(self._classes)
        new_registry._none_instance = self._none_instance
        new_registry._box_func = self._box_func
        new_registry._create_subclass_func = self._create_subclass_func
        new_registry._boxers = dict(self._boxers)
        new_registry._metadata_registry = self._metadata_registry.clone()
        new_registry._is_structure_sealed = self._is_structure_sealed
        new_registry._is_classes_sealed = self._is_classes_sealed
        new_registry._state_level = self._state_level
        return new_registry
