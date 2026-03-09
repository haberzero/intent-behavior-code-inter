from typing import Any, List, Dict, Optional, Callable
from ..objects.kernel import IbObject, IbClass, IbNativeFunction, IbNone
from ..objects.builtins import IbInteger, IbFloat, IbString, IbList, IbDict, IbBehavior
from core.foundation.registry import Registry
from core.domain.types import descriptors as uts
from ..bootstrapper import Bootstrapper

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

def _cast_string_to(ib_str: IbString, target_class: Any) -> Any:
    """实现 Spec 中的自动类型转换策略"""
    val = ib_str.to_native().strip()
    # [FIX] 兼容性处理：target_class 可能是 IbClass 也可能是转换函数 (由于名称冲突)
    target_name = target_class.name if hasattr(target_class, 'name') else str(target_class)
    
    if "int" in target_name:
        return int(val)
    if "float" in target_name:
        return float(val)
    if "bool" in target_name:
        return val.lower() in ("true", "1", "yes")
    return val

def _cast_numeric_to(ib_num: IbObject, target_class: Any) -> Any:
    """数值类型到其他类型的转换"""
    val = ib_num.to_native()
    target_name = target_class.name if hasattr(target_class, 'name') else str(target_class)
    
    if "str" in target_name:
        return str(val)
    if "int" in target_name:
        return int(val)
    if "float" in target_name:
        return float(val)
    if "bool" in target_name:
        return 1 if val else 0
    return val

def initialize_builtin_classes(registry: Registry):
    """
    初始化 IBCI 核心内置类及其 UTS 契约。
    支持多引擎实例隔离。
    """
    if registry.is_initialized:
        return # 已初始化
        
    bootstrapper = Bootstrapper(registry)
    bootstrapper.initialize()
    token = bootstrapper.token
    
    # 0. 准备 UTS 元数据注册表 (隔离引擎实例)
    from core.domain.builtin_schema import init_builtin_schema
    metadata_registry = uts.create_default_registry()
    init_builtin_schema(metadata_registry) # 初始化内置类型的 Schema
    registry.register_metadata_registry(metadata_registry, token)

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
    
    # 2. 绑定 UTS 描述符并注册到 Registry
    registry.register_class("int", integer_class, token, descriptor=metadata_registry.resolve("int"))
    registry.register_class("float", float_class, token, descriptor=metadata_registry.resolve("float"))
    registry.register_class("str", string_class, token, descriptor=metadata_registry.resolve("str"))
    registry.register_class("list", list_class, token, descriptor=metadata_registry.resolve("list"))
    registry.register_class("dict", dict_class, token, descriptor=metadata_registry.resolve("dict"))
    registry.register_class("None", none_class, token, descriptor=metadata_registry.resolve("void"))
    registry.register_class("behavior", behavior_class, token, descriptor=metadata_registry.resolve("callable"))
    registry.register_class("bool", bool_class, token, descriptor=metadata_registry.resolve("bool"))
    registry.register_class("callable", callable_class, token, descriptor=metadata_registry.resolve("callable"))
    registry.register_class("var", var_class, token, descriptor=metadata_registry.resolve("Any"))
    
    # 特殊：IbModule 类
    module_class = registry.create_subclass("IbModule")
    registry.register_class("IbModule", module_class, token, descriptor=metadata_registry.resolve("module"))
    
    # 3. 注册 None 单例 (Per-registry)
    registry.register_none(IbNone(none_class), token)
    _reg_native(none_class, '__to_prompt__', lambda self: "None")
    _reg_native(none_class, 'to_bool', lambda self: 0)
    
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
    _reg_native(integer_class, '__neg__', lambda self: -self.to_native())
    _reg_native(integer_class, '__pos__', lambda self: +self.to_native())
    
    _reg_native(integer_class, '__lt__', lambda self, other: _compare_op(self, other, lambda a, b: a < b))
    _reg_native(integer_class, '__le__', lambda self, other: _compare_op(self, other, lambda a, b: a <= b))
    _reg_native(integer_class, '__gt__', lambda self, other: _compare_op(self, other, lambda a, b: a > b))
    _reg_native(integer_class, '__ge__', lambda self, other: _compare_op(self, other, lambda a, b: a >= b))
    _reg_native(integer_class, '__eq__', lambda self, other: _compare_op(self, other, lambda a, b: a == b))
    _reg_native(integer_class, '__ne__', lambda self, other: _compare_op(self, other, lambda a, b: a != b))
    _reg_native(integer_class, 'cast_to', lambda self, target_class: _cast_numeric_to(self, target_class), unbox=False)
    
    # [NEW] int(x) 构造函数/转换逻辑
    def _int_call(self, *args):
        if not args: return self.registry.box(0)
        return args[0].receive('cast_to', [self])
    _reg_native(integer_class, '__call__', _int_call, unbox=False)
    
    # Float
    _reg_native(float_class, '__to_prompt__', lambda self: str(self.to_native()))
    _reg_native(float_class, '__add__', lambda self, other: _numeric_op(self, other, lambda a, b: a + b))
    _reg_native(float_class, '__sub__', lambda self, other: _numeric_op(self, other, lambda a, b: a - b))
    _reg_native(float_class, '__mul__', lambda self, other: _numeric_op(self, other, lambda a, b: a * b))
    _reg_native(float_class, '__div__', lambda self, other: _numeric_op(self, other, lambda a, b: a / b))
    _reg_native(float_class, '__neg__', lambda self: -self.to_native())
    _reg_native(float_class, '__pos__', lambda self: +self.to_native())
    _reg_native(float_class, '__eq__', lambda self, other: _compare_op(self, other, lambda a, b: a == b))
    _reg_native(float_class, '__ne__', lambda self, other: _compare_op(self, other, lambda a, b: a != b))
    _reg_native(float_class, 'cast_to', lambda self, target_class: _cast_numeric_to(self, target_class), unbox=False)

    # [NEW] float(x) 构造函数/转换逻辑
    def _float_call(self, *args):
        if not args: return self.registry.box(0.0)
        return args[0].receive('cast_to', [self])
    _reg_native(float_class, '__call__', _float_call, unbox=False)

    # String
    _reg_native(string_class, '__to_prompt__', lambda self: self.to_native())
    
    def _string_add(self, other):
        if not isinstance(other, IbObject):
            return str(self.to_native()) + str(other)
        if other.ib_class.name != "str":
            from core.domain.issue import InterpreterError
            raise InterpreterError(f"TypeError: Cannot concatenate 'str' and '{other.ib_class.name}'. Use cast_to(str) first.")
        return str(self.to_native()) + str(other.to_native())
        
    _reg_native(string_class, '__add__', _string_add, unbox=False)
    _reg_native(string_class, 'cast_to', lambda self, target_class: _cast_string_to(self, target_class), unbox=False)

    # [NEW] str(x) 构造函数/转换逻辑
    def _str_call(self, *args):
        if not args: return self.registry.box("")
        return args[0].receive('__to_prompt__', [])
    _reg_native(string_class, '__call__', _str_call, unbox=False)

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
    
    def _dict_get(self, key, default=None):
        native_key = key.to_native() if hasattr(key, 'to_native') else key
        return self.fields.get(native_key, default)
        
    def _dict_getitem(self, key):
        native_key = key.to_native() if hasattr(key, 'to_native') else key
        return self.fields[native_key]
        
    def _dict_setitem(self, key, val):
        native_key = key.to_native() if hasattr(key, 'to_native') else key
        self.fields[native_key] = val
        return self.ib_class.registry.get_none()

    _reg_native(dict_class, 'get', _dict_get, unbox=False)
    _reg_native(dict_class, '__getitem__', _dict_getitem, unbox=False)
    _reg_native(dict_class, '__setitem__', _dict_setitem, unbox=False)

    # 5. 注册装箱逻辑
    registry.register_boxer(int, lambda v, memo=None: IbInteger.from_native(v, integer_class), token)
    registry.register_boxer(bool, lambda v, memo=None: IbInteger.from_native(1 if v else 0, integer_class), token)
    registry.register_boxer(float, lambda v, memo=None: IbFloat(v, float_class), token)
    registry.register_boxer(str, lambda v, memo=None: IbString(v, string_class), token)
    
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
        
    registry.register_boxer(list, _box_list, token)
    registry.register_boxer(dict, _box_dict, token)
    
    # 6. 封印注册表结构 (Active Defense)
    registry.seal_structure(token)
