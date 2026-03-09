from typing import Any, List, Dict, Optional, Callable
from .kernel import IbObject, IbClass, IbNativeFunction, IbNone
from .builtins import IbInteger, IbFloat, IbString, IbList, IbDict, IbBehavior
from core.foundation.registry import Registry
from core.domain.types import descriptors as uts

def _reg_native(ib_class: IbClass, name: str, py_func: Callable, unbox: bool = True):
    """统一注册原生方法的辅助函数"""
    ib_class.register_method(name, IbNativeFunction(py_func, unbox_args=unbox, is_method=True, name=f"{ib_class.name}.{name}", ib_class=ib_class))

def _numeric_op(self: IbObject, other: Any, op_func: Callable) -> Any:
    """处理数值运算并支持 promotion"""
    a = self.to_native()
    return op_func(a, other)

def _compare_op(self: IbObject, other: Any, op_func: Callable) -> int:
    """处理比较运算"""
    a = self.to_native()
    try:
        return 1 if op_func(a, other) else 0
    except:
        return 0 

def _cast_string_to(ib_str: IbString, target_class: IbClass) -> Any:
    """实现 Spec 中的自动类型转换策略"""
    val = ib_str.to_native().strip()
    if target_class.name == "int":
        return int(val)
    if target_class.name == "float":
        return float(val)
    if target_class.name == "bool":
        return val.lower() in ("true", "1", "yes")
    return val

def initialize_builtin_classes(registry: Registry):
    """
    初始化 IBCI 核心内置类及其 UTS 契约。
    支持多引擎实例隔离。
    """
    from ..bootstrapper import Bootstrapper
    bootstrapper = Bootstrapper(registry)
    bootstrapper.initialize()
    
    # 1. 创建核心内置类 (注入到 registry)
    integer_class = registry.create_subclass("int")
    float_class = registry.create_subclass("float")
    string_class = registry.create_subclass("str")
    list_class = registry.create_subclass("list")
    dict_class = registry.create_subclass("dict")
    none_class = registry.create_subclass("None")
    behavior_class = registry.create_subclass("behavior")
    bool_class = registry.create_subclass("bool")
    callable_class = registry.create_subclass("callable")
    var_class = registry.create_subclass("var")
    
    # 特殊：IbModule 类
    module_class = registry.create_subclass("IbModule")
    registry.register_class("IbModule", module_class)
    
    # 2. UTS 注册
    uts.MetadataRegistry.register(integer_class)
    uts.MetadataRegistry.register(float_class)
    uts.MetadataRegistry.register(string_class)
    uts.MetadataRegistry.register(bool_class)
    uts.MetadataRegistry.register(none_class)
    uts.MetadataRegistry.register(var_class)
    
    # 3. 注册 None 单例 (Per-registry)
    registry.register_none(IbNone(none_class))
    
    # 4. 注册原生方法代理 (Integer)
    _reg_native(integer_class, '__to_prompt__', lambda self: str(self.to_native()))
    _reg_native(integer_class, 'to_bool', lambda self: 1 if self.to_native() != 0 else 0)
    _reg_native(integer_class, 'to_list', lambda self: list(range(self.to_native())))
    
    _reg_native(integer_class, '__add__', lambda self, other: _numeric_op(self, other, lambda a, b: a + b))
    _reg_native(integer_class, '__sub__', lambda self, other: _numeric_op(self, other, lambda a, b: a - b))
    _reg_native(integer_class, '__mul__', lambda self, other: _numeric_op(self, other, lambda a, b: a * b))
    _reg_native(integer_class, '__div__', lambda self, other: _numeric_op(self, other, lambda a, b: a // b if isinstance(a, int) and isinstance(b, int) else a / b))
    _reg_native(integer_class, '__mod__', lambda self, other: _numeric_op(self, other, lambda a, b: a % b))
    
    _reg_native(integer_class, '__and__', lambda self, other: self.to_native() & other)
    _reg_native(integer_class, '__or__', lambda self, other: self.to_native() | other)
    _reg_native(integer_class, '__xor__', lambda self, other: self.to_native() ^ other)
    _reg_native(integer_class, '__lshift__', lambda self, other: self.to_native() << other)
    _reg_native(integer_class, '__rshift__', lambda self, other: self.to_native() >> other)
    _reg_native(integer_class, '__invert__', lambda self: ~self.to_native())
    
    _reg_native(integer_class, '__lt__', lambda self, other: _compare_op(self, other, lambda a, b: a < b))
    _reg_native(integer_class, '__le__', lambda self, other: _compare_op(self, other, lambda a, b: a <= b))
    _reg_native(integer_class, '__gt__', lambda self, other: _compare_op(self, other, lambda a, b: a > b))
    _reg_native(integer_class, '__ge__', lambda self, other: _compare_op(self, other, lambda a, b: a >= b))
    _reg_native(integer_class, '__eq__', lambda self, other: _compare_op(self, other, lambda a, b: a == b))
    _reg_native(integer_class, '__ne__', lambda self, other: _compare_op(self, other, lambda a, b: a != b))
    
    # Float
    _reg_native(float_class, '__to_prompt__', lambda self: str(self.to_native()))
    _reg_native(float_class, '__add__', lambda self, other: _numeric_op(self, other, lambda a, b: a + b))
    _reg_native(float_class, '__sub__', lambda self, other: _numeric_op(self, other, lambda a, b: a - b))
    _reg_native(float_class, '__mul__', lambda self, other: _numeric_op(self, other, lambda a, b: a * b))
    _reg_native(float_class, '__div__', lambda self, other: _numeric_op(self, other, lambda a, b: a / b))
    _reg_native(float_class, '__eq__', lambda self, other: _compare_op(self, other, lambda a, b: a == b))
    _reg_native(float_class, '__ne__', lambda self, other: _compare_op(self, other, lambda a, b: a != b))

    # String
    _reg_native(string_class, '__to_prompt__', lambda self: self.to_native())
    _reg_native(string_class, '__add__', lambda self, other: str(self.to_native()) + (other if not isinstance(other, IbObject) else str(other.receive("__to_prompt__", []).to_native())))
    _reg_native(string_class, 'cast_to', lambda self, target_class: _cast_string_to(self, target_class), unbox=False)

    # List
    _reg_native(list_class, '__to_prompt__', lambda self: "[" + ", ".join(e.receive('__to_prompt__', []).to_native() for e in self.elements) + "]")
    _reg_native(list_class, 'to_list', lambda self: self.elements)
    _reg_native(list_class, 'append', lambda self, item: self.elements.append(item), unbox=False)
    _reg_native(list_class, 'len', lambda self: len(self.elements))
    _reg_native(list_class, 'sort', lambda self: self.elements.sort(key=lambda x: x.to_native()))
    _reg_native(list_class, '__getitem__', lambda self, key: self.elements[key])
    _reg_native(list_class, '__setitem__', lambda self, key, val: self.elements.__setitem__(key, val), unbox=False)

    # Dict
    _reg_native(dict_class, '__to_prompt__', lambda self: "{" + ", ".join(f'"{k}": {v.receive("__to_prompt__", []).to_native()}' for k, v in self.fields.items()) + "}")
    _reg_native(dict_class, 'get', lambda self, key: self.fields.get(key, None))
    _reg_native(dict_class, '__getitem__', lambda self, key: self.fields[key])
    _reg_native(dict_class, '__setitem__', lambda self, key, val: self.fields.update({key: val}), unbox=False)

    # 5. 注册装箱逻辑
    registry.register_boxer(int, lambda v, memo=None: IbInteger.from_native(v, integer_class))
    registry.register_boxer(bool, lambda v, memo=None: IbInteger.from_native(1 if v else 0, integer_class))
    registry.register_boxer(float, lambda v, memo=None: IbFloat(v, float_class))
    registry.register_boxer(str, lambda v, memo=None: IbString(v, string_class))
    
    def _box_list(val, memo):
        res = IbList([], list_class)
        memo[id(val)] = res
        res.elements = [registry.box(i, memo) for i in val]
        return res
        
    def _box_dict(val, memo):
        res = IbDict({}, dict_class)
        memo[id(val)] = res
        res.fields = {k: registry.box(v, memo) for k, v in val.items()}
        return res
        
    registry.register_boxer(list, _box_list)
    registry.register_boxer(dict, _box_dict)
