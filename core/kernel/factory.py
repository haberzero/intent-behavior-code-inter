from typing import TYPE_CHECKING
import copy

from core.kernel.types.registry import MetadataRegistry
from core.kernel.types.descriptors import (
    INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR,
    BOOL_DESCRIPTOR, VOID_DESCRIPTOR, ANY_DESCRIPTOR,
    VAR_DESCRIPTOR, CALLABLE_DESCRIPTOR, LIST_DESCRIPTOR,
    DICT_DESCRIPTOR, NONE_DESCRIPTOR, BEHAVIOR_DESCRIPTOR,
    BOUND_METHOD_DESCRIPTOR, EXCEPTION_DESCRIPTOR, MODULE_DESCRIPTOR
)

# [Architecture] 核心工厂模块不被 descriptors.py 导入，因此在此处进行顶层导入是安全的。
from core.kernel.axioms.registry import AxiomRegistry
from core.kernel.axioms.primitives import register_core_axioms

def create_default_registry() -> MetadataRegistry:
    """创建并预填充基础类型的注册表实例 (通过克隆原型实现物理隔离)"""
    
    axiom_reg = AxiomRegistry()
    register_core_axioms(axiom_reg)
    
    # 注入到元数据注册表
    reg = MetadataRegistry(axiom_registry=axiom_reg)
    
    # [IES 2.0 Bootstrapping] 采用两阶段注册协议，确保原子描述符（如 int, bool）在执行
    # 方法水化（Hydration）前已完成物理占位，避免循环类型引用导致的解析失败。
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
