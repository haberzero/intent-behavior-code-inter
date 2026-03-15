from typing import Dict, Any, Optional, List
from core.domain.types.registry import MetadataRegistry
from core.domain.types.descriptors import (
    TypeDescriptor, 
    ListMetadata, DictMetadata, FunctionMetadata, ClassMetadata,
    INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR, BOOL_DESCRIPTOR, 
    VOID_DESCRIPTOR, ANY_DESCRIPTOR, VAR_DESCRIPTOR, CALLABLE_DESCRIPTOR,
    LIST_DESCRIPTOR, DICT_DESCRIPTOR
)

class TypeHydrator:
    """
    类型重水化器：将序列化后的 type_pool 还原为运行时的 TypeDescriptor 对象树。
    """
    def __init__(self, type_pool: Dict[str, Any], registry: MetadataRegistry):
        self.type_pool = type_pool
        self.registry = registry
        self.memo: Dict[str, TypeDescriptor] = {}
        
        # 预注册内置基础描述符，防止重复创建
        self._init_builtins()

    def _init_builtins(self):
        """同步注册表中的内置描述符到 memo"""
        for name in ["int", "str", "float", "bool", "void", "Any", "var", "callable", "list", "dict"]:
            desc = self.registry.resolve(name)
            if desc:
                # 寻找池中对应的内置类型（如果存在）并关联
                for uid, data in self.type_pool.items():
                    if data["name"] == name and not data.get("element_type_uid"):
                        self.memo[uid] = desc
                        break

    def hydrate_all(self, registry: Optional[Any] = None):
        """水化池中所有类型。采用两阶段加载：先创建所有 Shell，再填充详细信息。"""
        if registry:
            from core.foundation.registry import RegistrationState
            registry.verify_state(RegistrationState.STAGE_5_HYDRATION)
            
        # Phase 1: Create all shells
        for uid in self.type_pool:
            self._create_shell(uid)
            
        # Phase 2: Fill all fields
        for uid in self.type_pool:
            self._fill_descriptor(uid)

    def hydrate(self, uid: str) -> Optional[TypeDescriptor]:
        """按需水化单个类型（支持递归调用）"""
        if not uid or uid not in self.type_pool:
            return None
        
        if uid in self.memo:
            return self.memo[uid]
            
        # 创建并填充
        desc = self._create_shell(uid)
        self._fill_descriptor(uid)
        return desc

    def _create_shell(self, uid: str) -> TypeDescriptor:
        """创建描述符外壳并存入缓存 (Phase 1)"""
        if uid in self.memo:
            return self.memo[uid]
            
        data = self.type_pool[uid]
        kind = data.get("kind", "StaticType")
        name = data.get("name", "")
        
        factory = self.registry.factory
        descriptor: Optional[TypeDescriptor] = None
        
        # 使用工厂驻留机制创建外壳
        if name in ["int", "str", "float", "bool", "void", "Any", "var", "callable", "list", "dict", "behavior"]:
            descriptor = self.registry.resolve(name)
            if not descriptor:
                descriptor = factory.create_primitive(name)
        elif kind == "ListMetadata":
            # 初始外壳不带泛型信息，避免名称过早变为 list[Any]
            descriptor = ListMetadata(name="list")
        elif kind == "DictMetadata":
            descriptor = DictMetadata(name="dict")
        elif kind == "FunctionMetadata":
            descriptor = FunctionMetadata(name="callable")
        elif kind == "ClassMetadata":
            parent_name = data.get("parent_name")
            descriptor = factory.create_class(name, parent=parent_name)
        elif kind == "BoundMethodMetadata":
            # 运行时会动态重新合成，但在池中我们记录一个占位符
            descriptor = factory.create_primitive("bound_method")
        else:
            descriptor = TypeDescriptor(name=name)
            
        self.memo[uid] = descriptor
        self.registry.register(descriptor)
        return descriptor

    def _fill_descriptor(self, uid: str):
        """填充描述符的详细字段 (Phase 2)"""
        descriptor = self.memo.get(uid)
        if not descriptor:
            return
            
        data = self.type_pool[uid]
        
        if isinstance(descriptor, ListMetadata):
            descriptor.element_type = self.hydrate(data.get("element_type_uid"))
        elif isinstance(descriptor, DictMetadata):
            descriptor.key_type = self.hydrate(data.get("key_type_uid"))
            descriptor.value_type = self.hydrate(data.get("value_type_uid"))
        elif isinstance(descriptor, FunctionMetadata):
            param_uids = data.get("param_types_uids", [])
            descriptor.param_types = [self.hydrate(p_uid) for p_uid in param_uids if p_uid]
            descriptor.return_type = self.hydrate(data.get("return_type_uid"))
        elif isinstance(descriptor, ClassMetadata):
            # ClassMetadata 的 members 通常在运行时动态填充，或通过 symbol_pool 水化
            pass
