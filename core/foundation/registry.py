from typing import Any, Dict, Optional

class Registry:
    """
    IBC-Inter 内核对象注册表。
    用于解耦 Kernel, Builtins 和 Bootstrapper 之间的循环引用。
    [Active Defense] 现在引入了基于令牌的权限审计机制，防止非特权代码（如外部插件）恶意注册或修改核心组件。
    """
    def __init__(self):
        self._classes: Dict[str, Any] = {}
        self._none_instance: Any = None
        self._box_func: Any = None
        self._create_subclass_func: Any = None
        self._boxers: Dict[type, Any] = {} # py_type -> Callable[[Any], IbObject]
        self._int_cache: Dict[int, Any] = {} # 小整数驻留缓存 (引擎实例隔离)
        
        # [Active Defense] 令牌机制
        self._token = object()
        self._is_token_granted = False
        self._is_structure_sealed = False
        self._is_classes_sealed = False

    @property
    def is_initialized(self) -> bool:
        """检查注册表是否已完成核心初始化并封印。"""
        return self._is_structure_sealed

    def get_privileged_token(self) -> Any:
        """[Active Defense] 获取特权令牌。仅允许调用一次。"""
        if self._is_token_granted:
            return None
        self._is_token_granted = True
        return self._token

    def _verify_structure(self, token: Any):
        if self._is_structure_sealed:
            raise PermissionError("Registry structure is sealed. Core factories cannot be modified.")
        if token is None or token is not self._token:
            raise PermissionError("Unauthorized modification to Registry structure. Privileged token required.")

    def _verify_class(self, token: Any):
        if self._is_classes_sealed:
            raise PermissionError("Registry classes are sealed. No more classes can be registered.")
        if token is None or token is not self._token:
            raise PermissionError("Unauthorized class registration. Privileged token required.")

    def seal_structure(self, token: Any):
        """[Active Defense] 封印注册表结构（装箱、创建类等核心工厂函数）。"""
        self._verify_structure(token)
        self._is_structure_sealed = True

    def seal_classes(self, token: Any):
        """[Active Defense] 封印类注册表。封印后禁止注册任何新类。"""
        self._verify_class(token)
        self._is_classes_sealed = True

    # --- 注册接口 (需校验令牌) ---

    def register_boxer(self, py_type: type, boxer_func: Any, token: Any):
        """让内置类型主动向注册表报告自己的装箱逻辑"""
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

    def register_class(self, name: str, ib_class: Any, token: Any):
        """注册类（内置或用户定义）"""
        self._verify_class(token)
        self._classes[name] = ib_class

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

    def create_subclass(self, name: str, parent_name: str = "Object") -> Any:
        """[Authorized] 通过内核绑定的工厂方法创建类，支持动态继承链。"""
        if self._create_subclass_func:
            return self._create_subclass_func(self, name, parent_name)
        return None

    def box(self, value: Any, memo: Optional[Dict[int, Any]] = None) -> Any:
        """[Authorized] 通过内核绑定的工厂方法装箱，支持多引擎实例。"""
        if self._box_func:
            return self._box_func(self, value, memo)
        return value
