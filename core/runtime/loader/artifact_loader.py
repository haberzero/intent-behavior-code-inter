from typing import Dict, Any, Mapping, Optional
from .type_hydrator import TypeHydrator
from core.foundation.registry import Registry

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
                 artifact_dict: Dict[str, Any]):
        self.node_pool = node_pool
        self.symbol_pool = symbol_pool
        self.scope_pool = scope_pool
        self.type_pool = type_pool
        self.asset_pool = asset_pool
        self.entry_module = entry_module
        self.type_hydrator = type_hydrator
        self.artifact_dict = artifact_dict

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
        hydrator.hydrate_all()

        return LoadedArtifact(
            node_pool=node_pool,
            symbol_pool=symbol_pool,
            scope_pool=scope_pool,
            type_pool=type_pool,
            asset_pool=asset_pool,
            entry_module=entry_module,
            type_hydrator=hydrator,
            artifact_dict=artifact_dict
        )
