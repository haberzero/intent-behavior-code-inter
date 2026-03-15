from typing import Dict, Any, Mapping, Optional
from .type_hydrator import TypeHydrator
from core.foundation.registry import Registry

from core.runtime.exceptions import RegistryIsolationError

class LoadedArtifact:
    """已加载并水化的产物容器"""
    def __init__(self, 
                 node_pool: Dict[str, Mapping[str, Any]], 
                 symbol_pool: Dict[str, Mapping[str, Any]], 
                 scope_pool: Dict[str, Mapping[str, Any]], 
                 type_pool: Dict[str, Mapping[str, Any]], 
                 asset_pool: Dict[str, str],
                 entry_module: str,
                 type_hydrator: TypeHydrator,
                 artifact_dict: Dict[str, Any],
                 class_to_node: Dict[str, str]):
        self.node_pool = node_pool
        self.symbol_pool = symbol_pool
        self.scope_pool = scope_pool
        self.type_pool = type_pool
        self.asset_pool = asset_pool
        self.entry_module = entry_module
        self.type_hydrator = type_hydrator
        self.artifact_dict = artifact_dict
        self.class_to_node = class_to_node

class ArtifactLoader:
    """
    产物加载器：负责解析原始产物字典并执行类型重水化。
    [Plan A] 严格数据契约：仅接受 Dict 格式的产物数据，实现运行时与编译器的物理隔离。
    """
    def __init__(self, registry: Registry):
        self.registry = registry

    def load(self, artifact_dict: Dict[str, Any]) -> LoadedArtifact:
        """从扁平化字典中加载并执行类型重水化"""
        if not isinstance(artifact_dict, dict):
            raise TypeError(f"ArtifactLoader expects a dictionary, but got {type(artifact_dict).__name__}")
        
        pools = artifact_dict.get("pools", {})
        node_pool = pools.get("nodes", {})
        symbol_pool = pools.get("symbols", {})
        scope_pool = pools.get("scopes", {})
        type_pool = pools.get("types", {})
        asset_pool = pools.get("assets", {})
        
        entry_module = artifact_dict.get("entry_module") or artifact_dict.get("metadata", {}).get("entry_module", "main")

        # 执行重水化 (UTS 闭环)
        hydrator = TypeHydrator(type_pool, self.registry.get_metadata_registry())
        user_classes = hydrator.hydrate_all(self.registry)

        # [IES 2.0] STAGE 5: 预水合用户类实体，并记录类名到节点 UID 的映射
        class_to_node = {}
        # 1. 扫描所有模块寻找类定义节点
        for module_name, module_data in artifact_dict.get("modules", {}).items():
            if not isinstance(module_data, dict): continue
            root_node_uid = module_data.get("root_node_uid")
            root_node = node_pool.get(root_node_uid)
            if not root_node: continue
            
            for stmt_uid in root_node.get("body", []):
                stmt_data = node_pool.get(stmt_uid)
                if stmt_data and stmt_data.get("_type") == "IbClassDef":
                    class_to_node[stmt_data.get("name")] = (stmt_uid, module_name)

        # 2. 预注册用户定义的类 (支持继承依赖)
        remaining = [c for c in user_classes if c.is_user_defined]
        last_count = -1
        
        while remaining and len(remaining) != last_count:
            last_count = len(remaining)
            still_remaining = []
            for cls_desc in remaining:
                parent_name = cls_desc.parent_name or "Object"
                try:
                    self.registry.create_subclass(
                        cls_desc.name, 
                        cls_desc, 
                        parent_name
                    )
                except ValueError:
                    # 可能是父类尚未注册，等待下一轮
                    still_remaining.append(cls_desc)
            remaining = still_remaining
            
        if remaining:
            # [IES 2.0 FIX] 继承链断裂属于致命错误 (Item 2.2 Audit)
            # 必须在加载阶段拦截，严禁进入运行时。
            missing = [f"{c.name} (extends {c.parent_name or 'Object'})" for c in remaining]
            raise RegistryIsolationError(f"Linker Error: Broken inheritance chain for classes: {', '.join(missing)}. "
                                       f"Ensure all parent classes are defined and no circular inheritance exists.")

        return LoadedArtifact(
            node_pool=node_pool,
            symbol_pool=symbol_pool,
            scope_pool=scope_pool,
            type_pool=type_pool,
            asset_pool=asset_pool,
            entry_module=entry_module,
            type_hydrator=hydrator,
            artifact_dict=artifact_dict,
            class_to_node=class_to_node
        )
