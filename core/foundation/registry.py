from typing import Any, Dict, Optional

class Registry:
    """
    IBC-Inter 内核对象注册表。
    用于解耦 Kernel, Builtins 和 Bootstrapper 之间的循环引用。
    现在支持实例化以支持多引擎隔离。
    """
    def __init__(self):
        self._classes: Dict[str, Any] = {}
        self._none_instance: Any = None
        self._box_func: Any = None
        self._create_subclass_func: Any = None
        self._boxers: Dict[type, Any] = {} # py_type -> Callable[[Any], IbObject]

    def register_boxer(self, py_type: type, boxer_func: Any):
        """让内置类型主动向注册表报告自己的装箱逻辑"""
        self._boxers[py_type] = boxer_func

    def get_boxer(self, py_type: type) -> Any:
        return self._boxers.get(py_type)

    def register_class(self, name: str, ib_class: Any):
        self._classes[name] = ib_class

    def get_class(self, name: str) -> Any:
        return self._classes.get(name)

    def get_all_classes(self) -> Dict[str, Any]:
        return dict(self._classes)

    def register_none(self, instance: Any):
        self._none_instance = instance

    def get_none(self) -> Any:
        return self._none_instance

    def register_box_func(self, func: Any):
        self._box_func = func

    def register_create_subclass_func(self, func: Any):
        self._create_subclass_func = func

    def create_subclass(self, name: str, parent_name: str = "Object") -> Any:
        if self._create_subclass_func:
            return self._create_subclass_func(self, name, parent_name)
        return None

    def box(self, value: Any, memo: Optional[Dict[int, Any]] = None) -> Any:
        if self._box_func:
            return self._box_func(self, value, memo)
        return value

# --- 兼容性层 (Transition Compatibility) ---
# 提供一个默认单例，直到所有调用方完成实例化迁移
_default_registry = Registry()

def get_default_registry() -> Registry:
    return _default_registry
