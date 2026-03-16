from typing import Any, List, Dict, Optional, Callable, TYPE_CHECKING
from core.runtime.objects.type_registry import get_ib_implementation
from ..objects.kernel import IbClass, IbNativeFunction, IbNone, IbObject
from ..objects.builtins import IbInteger, IbFloat, IbString, IbList, IbDict, IbBehavior
from core.foundation.registry import Registry
from core.runtime.enums import RegistrationState
from core.domain.issue import InterpreterError
from core.domain.types import descriptors as uts
from core.domain.types.descriptors import (
    INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR, 
    BOOL_DESCRIPTOR, VOID_DESCRIPTOR, ANY_DESCRIPTOR
)
from core.runtime.support.converters import _cast_numeric_to_native, _cast_string_to_native
from core.domain.factory import create_default_registry
from ..bootstrapper import Bootstrapper

def _reg_native(ib_class: IbClass, name: str, py_func: Callable, unbox: bool = True):
    """统一注册原生方法的辅助函数"""
    ib_class.register_method(name, IbNativeFunction(py_func, unbox_args=unbox, is_method=True, name=f"{ib_class.name}.{name}", ib_class=ib_class))

def _numeric_op(self: 'IbObject', other: Any, op_func: Callable) -> Any:
    """处理数值运算并支持 promotion"""
    a = self.to_native()
    return op_func(a, other)

def _compare_op(self: 'IbObject', other: Any, op_func: Callable) -> int:
    """处理比较运算"""
    a = self.to_native()
    try:
        return 1 if op_func(a, other) else 0
    except:
        return 0 

def _cast_string_to(ib_str: 'IbString', target_class: Any) -> Any:
    """实现 Spec 中的自动类型转换策略 (Descriptor Identity 版)"""
    target_desc = target_class.descriptor if hasattr(target_class, 'descriptor') else None
    return _cast_string_to_native(ib_str.to_native(), target_desc)

def _cast_numeric_to(ib_num: 'IbObject', target_class: Any) -> Any:
    """数值类型到其他类型的转换 (Descriptor Identity 版)"""
    target_desc = target_class.descriptor if hasattr(target_class, 'descriptor') else None
    return _cast_numeric_to_native(ib_num.to_native(), target_desc)

def initialize_builtin_classes(registry: Registry) -> Any:
    """
    初始化 IBCI 核心内置类及其 UTS 契约。
    支持多引擎实例隔离。
    """
    if registry.is_initialized:
        return None # 已初始化
        
    # [IES 2.0] 确保处于 STAGE_1_BOOTSTRAP 状态
    registry.verify_level(RegistrationState.STAGE_1_BOOTSTRAP.value)
    
    # 1. 准备 UTS 元数据注册表 (隔离引擎实例)
    # [Active Defense] 贯彻“元数据先行”原则
    metadata_registry = create_default_registry()
    
    # 2. 引导核心类 (Type, Object, callable, IbModule, Intent)
    bootstrapper = Bootstrapper(registry)
    bootstrapper.initialize(metadata_registry)
    token = bootstrapper.token
    
    # [IES 2.0 Transition] 跃迁到 STAGE_2_CORE_TYPES
    registry.set_state_level(RegistrationState.STAGE_2_CORE_TYPES.value, token)
    
    # 注册元数据注册表到 Registry
    registry.register_metadata_registry(metadata_registry, token)

    # 3. 创建核心内置类 (Axiom-Driven Automation)
    # [NEW] 遍历 AxiomRegistry 自动初始化所有注册的原子类型
    
    # 基础类型映射表 (用于绑定具体的 IbClass 实现)
    # [IES 2.1 Regularization] 基础类型与实现类的映射已下沉到各实现类的 @register_ib_type 装饰器中
    # 自动创建类并注册
    # 注意：我们必须保证顺序，或者允许多次查找
    # 依赖于 pritmives.py 中的注册顺序 (int before bool)
    
    core_axioms = []
    axiom_registry = metadata_registry.get_axiom_registry()
    if axiom_registry:
        core_axioms = axiom_registry.get_all_names()
    else:
        # Fallback (Safety net) - 仅在极端的 UTS 注册表未对齐时使用
        core_axioms = ["int", "str", "float", "bool", "list", "dict", "None", "behavior", "callable", "bound_method", "var", "Any", "void"]
    
    # 自动创建类并注册
    ib_classes = {}
    for name in core_axioms:
        # 获取描述符 (Bootstrapper 初始化时已经注入了 MetadataRegistry)
        desc = metadata_registry.resolve(name)
        if not desc: continue
            
        # 创建类
        parent = "Object"
        if name == "bool": parent = "int" # 特殊继承关系
        if name == "bound_method": parent = "callable"
        
        ib_cls = registry.create_subclass(name, desc, parent_name=parent)
        ib_classes[name] = ib_cls
        
    # [Axiom-Driven Automation] 能力注入
    # 遍历公理中定义的所有方法，并从 IbObject 实现类中自动查找并绑定同名方法
    for name, ib_cls in ib_classes.items():
        desc = ib_cls.descriptor
        axiom = desc._axiom if desc else None
        if axiom:
            methods = axiom.get_methods()
            # [IES 2.1 Regularization] 从全局类型注册表获取实现类，消除硬编码映射
            py_impl_cls = get_ib_implementation(name)
            if py_impl_cls:
                for method_name in methods:
                    if hasattr(py_impl_cls, method_name):
                        # 获取 Python 实现的方法
                        py_method = getattr(py_impl_cls, method_name)
                        # 绑定为原生方法
                        _reg_native(ib_cls, method_name, py_method, unbox=False)

    # 获取引用以便后续绑定 (保持兼容性)
    integer_class = ib_classes.get("int")
    float_class = ib_classes.get("float")
    string_class = ib_classes.get("str")
    list_class = ib_classes.get("list")
    dict_class = ib_classes.get("dict")
    none_class = ib_classes.get("None")
    bool_class = ib_classes.get("bool")
    
    # 特殊：module 类 (Bootstrapper 已经创建过一次)
    module_class = registry.create_subclass("module", metadata_registry.resolve("module"))
    
    # 4. 注册内置全局函数元数据 (供编译器发现)
    registry.register_function("print", uts.FunctionMetadata(
        name="print", 
        param_types=[metadata_registry.resolve("Any")], 
        return_type=metadata_registry.resolve("void")
    ), token)
    
    registry.register_function("len", uts.FunctionMetadata(
        name="len", 
        param_types=[metadata_registry.resolve("Any")], 
        return_type=metadata_registry.resolve("int")
    ), token)

    registry.register_function("get_self_source", uts.FunctionMetadata(
        name="get_self_source",
        param_types=[],
        return_type=metadata_registry.resolve("str")
    ), token)

    # --- Dynamic Host Meta APIs ---
    registry.register_function("host_save_state", uts.FunctionMetadata(
        name="host_save_state",
        param_types=[metadata_registry.resolve("str")],
        return_type=metadata_registry.resolve("void")
    ), token)
    
    registry.register_function("host_load_state", uts.FunctionMetadata(
        name="host_load_state",
        param_types=[metadata_registry.resolve("str")],
        return_type=metadata_registry.resolve("void")
    ), token)
    
    registry.register_function("host_run", uts.FunctionMetadata(
        name="host_run",
        param_types=[metadata_registry.resolve("str")],
        return_type=metadata_registry.resolve("bool")
    ), token)
    
    registry.register_function("host_get_source", uts.FunctionMetadata(
        name="host_get_source",
        param_types=[],
        return_type=metadata_registry.resolve("str")
    ), token)
    # ------------------------------

    # 4. 注册 None 单例 (Per-registry)
    registry.register_none(IbNone(none_class), token)
    _reg_native(none_class, '__to_prompt__', lambda self: "None")
    _reg_native(none_class, 'to_bool', lambda self: 0)
    
    # 4. 注册原生方法代理 (Integer)
    _reg_native(integer_class, '__to_prompt__', lambda self: str(self.to_native()))
    
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
        if other.descriptor is not STR_DESCRIPTOR:
            raise InterpreterError(f"TypeError: Cannot concatenate 'str' and '{other.ib_class.name}'. Use cast_to(str) first.")
        return str(self.to_native()) + str(other.to_native())
        
    _reg_native(string_class, '__add__', _string_add, unbox=False)

    # [NEW] str(x) 构造函数/转换逻辑
    def _str_call(self, *args):
        if not args: return self.registry.box("")
        return args[0].receive('__to_prompt__', [])
    _reg_native(string_class, '__call__', _str_call, unbox=False)

    _reg_native(list_class, '__to_prompt__', lambda self: "[" + ", ".join(e.receive('__to_prompt__', []).to_native() for e in self.elements) + "]")
    _reg_native(list_class, 'to_list', lambda self: self.elements)
    _reg_native(list_class, 'len', lambda self: self.len())

    # Dict
    _reg_native(dict_class, '__to_prompt__', lambda self: "{" + ", ".join(f'"{k}": {v.receive("__to_prompt__", []).to_native()}' for k, v in self.fields.items()) + "}")
    _reg_native(dict_class, 'len', lambda self: self.len())
    
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

    # [IES 2.0 Transition] 跃迁到 STAGE_3_PLUGIN_METADATA
    registry.set_state_level(RegistrationState.STAGE_3_PLUGIN_METADATA.value, token)
    
    # [IES 2.1 Audit] 清理遗留 Legacy 术语与残留注释
    return token
