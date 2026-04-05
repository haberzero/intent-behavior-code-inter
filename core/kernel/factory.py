from typing import TYPE_CHECKING

from core.kernel.types.registry import MetadataRegistry
from core.kernel.types.descriptors import (
    INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR,
    BOOL_DESCRIPTOR, VOID_DESCRIPTOR, ANY_DESCRIPTOR, AUTO_DESCRIPTOR, SLICE_DESCRIPTOR, CALLABLE_DESCRIPTOR, LIST_DESCRIPTOR,
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

    # 采用两阶段注册协议，统一由 register() 负责
    # 克隆、hydration 和 axiom injection，消除双重克隆开销。
    for d in (INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR,
              BOOL_DESCRIPTOR, VOID_DESCRIPTOR, ANY_DESCRIPTOR,
              AUTO_DESCRIPTOR, SLICE_DESCRIPTOR, CALLABLE_DESCRIPTOR, LIST_DESCRIPTOR, DICT_DESCRIPTOR,
              NONE_DESCRIPTOR, BEHAVIOR_DESCRIPTOR, BOUND_METHOD_DESCRIPTOR,
              EXCEPTION_DESCRIPTOR, MODULE_DESCRIPTOR):
        reg.register(d)
    return reg
