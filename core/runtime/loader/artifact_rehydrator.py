from typing import Dict, Any, Optional, List
from core.kernel.types.registry import MetadataRegistry
from core.base.enums import RegistrationState
from core.kernel.types.descriptors import (
    TypeDescriptor, 
    ListMetadata, DictMetadata, FunctionMetadata, ClassMetadata, ModuleMetadata,
    INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR, BOOL_DESCRIPTOR, 
    VOID_DESCRIPTOR, ANY_DESCRIPTOR, AUTO_DESCRIPTOR, CALLABLE_DESCRIPTOR,
    LIST_DESCRIPTOR, DICT_DESCRIPTOR
)

# 统一内置原始类型列表，确保水化阶段一致性
BUILTIN_TYPES = ["int", "str", "float", "bool", "void", "any", "auto", "callable", "list", "dict", "behavior"]

class ArtifactRehydrator:
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
        for name in BUILTIN_TYPES:
            desc = self.registry.resolve(name)
            if desc:
                # 寻找池中对应的内置类型（如果存在）并关联
                for uid, data in self.type_pool.items():
                    if data["name"] == name and not data.get("element_type_uid"):
                        self.memo[uid] = desc
                        break

    def hydrate_all(self, registry: Optional[Any] = None) -> List[ClassMetadata]:
        """
        水化池中所有类型。采用两阶段加载：先创建所有 Shell，再填充详细信息。
        返回所有被成功水化的 ClassMetadata。
        """
        if registry:
             registry.verify_level(RegistrationState.STAGE_5_HYDRATION.value)
            
        # Phase 1: Create all shells
        for uid in self.type_pool:
            self._create_shell(uid)
            
        # Phase 2: Fill all fields
        classes = []
        for uid in self.type_pool:
            desc = self._fill_descriptor(uid)
            # 使用 is_class() 代替名称比对
            if desc and desc.is_class():
                classes.append(desc)
        
        return classes

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
        # 使用 TypeDescriptor 作为通用回退标识
        kind = data.get("kind", "TypeDescriptor")
        name = data.get("name", "")
        is_user_defined = data.get("is_user_defined", False)
        
        factory = self.registry.factory
        
        # 映射驱动的 Shell 创建，消除 if/elif kind 硬编码
        shell_creators = {
            "ListMetadata": lambda: ListMetadata(name="list"),
            "DictMetadata": lambda: DictMetadata(name="dict"),
            "FunctionMetadata": lambda: FunctionMetadata(name="callable"),
            "ClassMetadata": lambda: factory.create_class(name, parent=data.get("parent_name")),
            "BoundMethodMetadata": lambda: factory.create_primitive("bound_method"),
            "ModuleMetadata": lambda: ModuleMetadata(name=name)
        }
        
        if name in BUILTIN_TYPES and kind == "TypeDescriptor":
            descriptor = self.registry.resolve(name) or factory.create_primitive(name)
        else:
            creator = shell_creators.get(kind, lambda: TypeDescriptor(name=name))
            descriptor = creator()
            
        if descriptor:
            descriptor.is_user_defined = is_user_defined
            # 注册以确保物理隔离（克隆）并绑定注册表上下文
            descriptor = self.registry.register(descriptor)
            
        self.memo[uid] = descriptor
        return descriptor

    def _fill_descriptor(self, uid: str) -> Optional[TypeDescriptor]:
        """填充描述符的详细字段 (Phase 2)"""
        descriptor = self.memo.get(uid)
        if not descriptor:
            return None
            
        data = self.type_pool[uid]
        
        # 使用重水化接口，消除硬编码 isinstance 检查
        descriptor.rehydrate_fields(data, self)
            
        return descriptor
