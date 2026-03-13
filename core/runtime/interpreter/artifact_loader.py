from typing import Dict, Any, Mapping, Optional
from core.compiler.serialization.serializer import FlatSerializer
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
    实现执行引擎与数据加载逻辑的彻底解耦。
    """
    def __init__(self, registry: Registry):
        self.registry = registry

    def load(self, artifact: Any) -> LoadedArtifact:
        """从各种格式的产物中加载并水化"""
        artifact_dict = self._normalize_artifact(artifact)
        
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

    def _normalize_artifact(self, artifact: Any) -> Dict[str, Any]:
        """将 CompilationArtifact 或其他格式统一为字典"""
        if not artifact:
            return {}
            
        if hasattr(artifact, 'to_dict'):
            return artifact.to_dict()
        elif hasattr(artifact, 'modules'): # 识别为 CompilationArtifact
            serializer = FlatSerializer()
            return serializer.serialize_artifact(artifact)
        elif isinstance(artifact, dict):
            return artifact
        
        return {}
