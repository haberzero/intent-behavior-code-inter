from typing import Any, Dict, Optional

class Registry:
    """
    IBC-Inter 内核对象注册表。
    用于解耦 Kernel, Builtins 和 Bootstrapper 之间的循环引用。
    """
    _classes: Dict[str, Any] = {}
    _none_instance: Any = None
    _box_func: Any = None
    _create_subclass_func: Any = None
    _boxers: Dict[type, Any] = {} # py_type -> Callable[[Any], IbObject]

    @classmethod
    def register_boxer(cls, py_type: type, boxer_func: Any):
        """让内置类型主动向注册表报告自己的装箱逻辑"""
        cls._boxers[py_type] = boxer_func

    @classmethod
    def get_boxer(cls, py_type: type) -> Any:
        return cls._boxers.get(py_type)

    @classmethod
    def register_class(cls, name: str, ib_class: Any):
        cls._classes[name] = ib_class

    @classmethod
    def get_class(cls, name: str) -> Any:
        return cls._classes.get(name)

    @classmethod
    def get_all_classes(cls) -> Dict[str, Any]:
        return dict(cls._classes)

    @classmethod
    def register_none(cls, instance: Any):
        cls._none_instance = instance

    @classmethod
    def get_none(cls) -> Any:
        return cls._none_instance

    @classmethod
    def register_box_func(cls, func: Any):
        cls._box_func = func

    @classmethod
    def register_create_subclass_func(cls, func: Any):
        cls._create_subclass_func = func

    @classmethod
    def create_subclass(cls, name: str, parent_name: str = "Object") -> Any:
        if cls._create_subclass_func:
            return cls._create_subclass_func(name, parent_name)
        return None

    @classmethod
    def box(cls, value: Any, memo: Optional[Dict[int, Any]] = None) -> Any:
        if cls._box_func:
            return cls._box_func(value, memo)
        return value
