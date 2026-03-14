from typing import TYPE_CHECKING
import copy

from core.domain.types.registry import MetadataRegistry
from core.domain.types.descriptors import (
    INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR, 
    BOOL_DESCRIPTOR, VOID_DESCRIPTOR, ANY_DESCRIPTOR, 
    VAR_DESCRIPTOR, CALLABLE_DESCRIPTOR, LIST_DESCRIPTOR, 
    DICT_DESCRIPTOR, NONE_DESCRIPTOR, BEHAVIOR_DESCRIPTOR, 
    BOUND_METHOD_DESCRIPTOR, EXCEPTION_DESCRIPTOR, MODULE_DESCRIPTOR
)

# [De-static] Runtime imports to avoid circular dependency with descriptors.py
# These imports are now safe because this factory module is not imported by descriptors.py
from core.domain.axioms.registry import AxiomRegistry
from core.domain.axioms.primitives import register_core_axioms

def create_default_registry() -> MetadataRegistry:
    """创建并预填充基础类型的注册表实例 (通过克隆原型实现物理隔离)"""
    
    axiom_reg = AxiomRegistry()
    register_core_axioms(axiom_reg)
    
    # 注入到元数据注册表
    reg = MetadataRegistry(axiom_registry=axiom_reg)
    
    # [Fix] 使用两阶段注册，确保在执行方法水化 (Hydration) 时，
    # 所有的基础描述符 (int, bool, Any 等) 都已经可以在注册表中被解析。
    # 否则 int.to_bool() 的返回类型 bool 可能会因为解析不到而变成没有公理的外壳。
    descriptors = []
    for d in (INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR, 
              BOOL_DESCRIPTOR, VOID_DESCRIPTOR, ANY_DESCRIPTOR, 
              VAR_DESCRIPTOR, CALLABLE_DESCRIPTOR, LIST_DESCRIPTOR, DICT_DESCRIPTOR,
              NONE_DESCRIPTOR, BEHAVIOR_DESCRIPTOR, BOUND_METHOD_DESCRIPTOR, 
              EXCEPTION_DESCRIPTOR, MODULE_DESCRIPTOR):
        # 1. 物理克隆
        cloned = copy.deepcopy(d)
        descriptors.append(cloned)
        # 2. 预填充类型图 (让 resolve() 能立刻找到它)
        reg._descriptors[cloned.name] = cloned

    for d in descriptors:
        # 3. 正式注册并触发公理注入
        reg.register(d)
    return reg
