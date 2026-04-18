from typing import Dict, Any, Optional, List
from core.kernel.spec.registry import SpecRegistry
from core.kernel.spec import IbSpec, ClassSpec, ListSpec, DictSpec, FuncSpec, BoundMethodSpec, ModuleSpec
from core.kernel.spec.specs import DeferredSpec, BehaviorSpec
from core.base.enums import RegistrationState

# 统一内置原始类型列表，确保水化阶段一致性
BUILTIN_TYPES = ["int", "str", "float", "bool", "void", "any", "auto", "callable", "list", "dict", "behavior"]

class ArtifactRehydrator:
    """
    类型重水化器：将序列化后的 type_pool 还原为运行时的 IbSpec 对象树。
    """
    def __init__(self, type_pool: Dict[str, Any], registry: SpecRegistry):
        self.type_pool = type_pool
        self.registry = registry
        self.memo: Dict[str, IbSpec] = {}
        
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

    def hydrate_all(self, registry: Optional[Any] = None) -> List[ClassSpec]:
        """
        水化池中所有类型。采用两阶段加载：先创建所有 Shell，再填充详细信息。
        返回所有被成功水化的 ClassSpec。
        """
        if registry:
             registry.verify_level(RegistrationState.STAGE_5_HYDRATION.value)
            
        # Phase 1: Create all shells
        for uid in self.type_pool:
            self._create_shell(uid)
            
        # Phase 2: Fill all fields
        classes = []
        for uid in self.type_pool:
            spec = self._fill_descriptor(uid)
            if isinstance(spec, ClassSpec):
                classes.append(spec)
        
        return classes

    def hydrate(self, uid: str) -> Optional[IbSpec]:
        """按需水化单个类型（支持递归调用）"""
        if not uid or uid not in self.type_pool:
            return None
        
        if uid in self.memo:
            return self.memo[uid]
            
        # 创建并填充
        spec = self._create_shell(uid)
        self._fill_descriptor(uid)
        return spec

    def _create_shell(self, uid: str) -> IbSpec:
        """创建 spec 外壳并存入缓存 (Phase 1)"""
        if uid in self.memo:
            return self.memo[uid]
            
        data = self.type_pool[uid]
        kind = data.get("kind", "TypeDescriptor")
        name = data.get("name", "")
        is_user_defined = data.get("is_user_defined", False)
        
        factory = self.registry.factory
        
        # 映射驱动的 Shell 创建
        shell_creators = {
            "ListMetadata": lambda: ListSpec(name="list", is_user_defined=False),
            "DictMetadata": lambda: DictSpec(name="dict", is_user_defined=False),
            "FunctionMetadata": lambda: FuncSpec(name=name or "callable", is_user_defined=False),
            "ClassMetadata": lambda: factory.create_class(name, parent_name=data.get("parent_name"), is_user_defined=is_user_defined),
            "BoundMethodMetadata": lambda: BoundMethodSpec(name="bound_method", is_user_defined=False),
            "ModuleMetadata": lambda: ModuleSpec(name=name, is_user_defined=False),
            # Typed deferred / behavior specs — reconstruct the proper subclass so
            # that get_base_name() returns "deferred" / "behavior" (not "deferred[str]"),
            # allowing SpecRegistry.is_assignable() to resolve the correct axiom.
            "DeferredSpec": lambda: factory.create_deferred(
                value_type_name=data.get("value_type_name", "auto"),
                deferred_mode=data.get("deferred_mode", "lambda"),
            ),
            "BehaviorSpec": lambda: factory.create_behavior(
                value_type_name=data.get("value_type_name", "auto"),
                deferred_mode=data.get("deferred_mode", "lambda"),
            ),
        }
        
        if name in BUILTIN_TYPES and kind == "TypeDescriptor":
            spec = self.registry.resolve(name) or factory.create_primitive(name)
        else:
            creator = shell_creators.get(kind)
            if creator:
                spec = creator()
            else:
                spec = self.registry.resolve(name) or IbSpec(name=name)
            
        if spec:
            spec.is_user_defined = is_user_defined
            spec = self.registry.register(spec)
            
        self.memo[uid] = spec
        return spec

    def _fill_descriptor(self, uid: str) -> Optional[IbSpec]:
        """填充 spec 的详细字段 (Phase 2)"""
        spec = self.memo.get(uid)
        if not spec:
            return None
            
        data = self.type_pool[uid]
        
        if isinstance(spec, ListSpec):
            elem = self.hydrate(data.get("element_type_uid"))
            if elem:
                spec.element_type_name = elem.name
                spec.name = f"list[{elem.name}]"
        elif isinstance(spec, DictSpec):
            key = self.hydrate(data.get("key_type_uid"))
            val = self.hydrate(data.get("value_type_uid"))
            if key:
                spec.key_type_name = key.name
            if val:
                spec.value_type_name = val.name
            spec.name = f"dict[{spec.key_type_name},{spec.value_type_name}]"
        elif isinstance(spec, FuncSpec):
            param_uids = data.get("param_types_uids", [])
            spec.param_type_names = [
                s.name for uid in param_uids
                if (s := self.hydrate(uid)) is not None
            ]
            ret = self.hydrate(data.get("return_type_uid"))
            spec.return_type_name = ret.name if ret else "void"
        elif isinstance(spec, DeferredSpec):
            # Restore scalar fields for DeferredSpec / BehaviorSpec.
            # BehaviorSpec is a subclass of DeferredSpec so this branch covers both.
            spec.value_type_name = data.get("value_type_name", spec.value_type_name)
            spec.deferred_mode = data.get("deferred_mode", spec.deferred_mode)
        elif isinstance(spec, ClassSpec):
            spec.parent_name = data.get("parent_name")
            spec.parent_module = data.get("parent_module")
            
        return spec
