from .types import descriptors as uts
from typing import Optional

def init_builtin_schema(registry: Optional[uts.MetadataRegistry] = None):
    """
    初始化内置类型的 Schema (方法签名与属性)。
    这是 IBCI 语言定义的“单源真理”。
    
    Args:
        registry: 如果提供，则初始化该注册表实例中的描述符；
                 如果不提供，则初始化全局原型描述符。
    """
    
    # 1. 获取目标描述符
    if registry:
        int_desc = registry.resolve("int")
        str_desc = registry.resolve("str")
        float_desc = registry.resolve("float")
        bool_desc = registry.resolve("bool")
        any_desc = registry.resolve("Any")
        void_desc = registry.resolve("void")
        list_desc = registry.resolve("list")
        dict_desc = registry.resolve("dict")
        callable_desc = registry.resolve("callable")
    else:
        int_desc = uts.INT_DESCRIPTOR
        str_desc = uts.STR_DESCRIPTOR
        float_desc = uts.FLOAT_DESCRIPTOR
        bool_desc = uts.BOOL_DESCRIPTOR
        any_desc = uts.ANY_DESCRIPTOR
        void_desc = uts.VOID_DESCRIPTOR
        list_desc = uts.LIST_DESCRIPTOR
        dict_desc = uts.DICT_DESCRIPTOR
        callable_desc = uts.CALLABLE_DESCRIPTOR

    # --- 1. Integer ---
    if int_desc:
        int_desc.members.update({
            "to_bool": uts.FunctionMetadata(name="to_bool", param_types=[], return_type=bool_desc),
            "to_list": uts.FunctionMetadata(name="to_list", param_types=[], return_type=uts.ListMetadata(element_type=int_desc)),
            "cast_to": uts.FunctionMetadata(name="cast_to", param_types=[any_desc], return_type=any_desc)
        })

    # --- 2. String ---
    if str_desc:
        str_desc.members.update({
            "len": uts.FunctionMetadata(name="len", param_types=[], return_type=int_desc),
            "to_bool": uts.FunctionMetadata(name="to_bool", param_types=[], return_type=bool_desc),
            "cast_to": uts.FunctionMetadata(name="cast_to", param_types=[any_desc], return_type=any_desc)
        })

    # --- 3. Float ---
    if float_desc:
        float_desc.members.update({
            "to_bool": uts.FunctionMetadata(name="to_bool", param_types=[], return_type=bool_desc),
            "cast_to": uts.FunctionMetadata(name="cast_to", param_types=[any_desc], return_type=any_desc)
        })

    # --- 4. List ---
    if list_desc:
        list_desc.members.update({
            "append": uts.FunctionMetadata(name="append", param_types=[any_desc], return_type=void_desc),
            "pop": uts.FunctionMetadata(name="pop", param_types=[], return_type=any_desc),
            "len": uts.FunctionMetadata(name="len", param_types=[], return_type=int_desc),
            "sort": uts.FunctionMetadata(name="sort", param_types=[], return_type=void_desc),
            "clear": uts.FunctionMetadata(name="clear", param_types=[], return_type=void_desc)
        })

    # --- 5. Dict ---
    if dict_desc:
        dict_desc.members.update({
            "get": uts.FunctionMetadata(name="get", param_types=[any_desc], return_type=any_desc),
            "keys": uts.FunctionMetadata(name="keys", param_types=[], return_type=uts.ListMetadata(element_type=any_desc)),
            "values": uts.FunctionMetadata(name="values", param_types=[], return_type=uts.ListMetadata(element_type=any_desc)),
            "len": uts.FunctionMetadata(name="len", param_types=[], return_type=int_desc)
        })

# 默认初始化全局原型，确保编译器在非隔离模式下也能正常工作
init_builtin_schema()
