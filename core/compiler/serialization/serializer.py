from typing import Dict, Any, List, Optional, Union
import uuid
import json
from enum import Enum
from core.domain import ast as ast
from core.domain.symbols import Symbol, SymbolTable, StaticType
from core.domain.blueprint import CompilationArtifact, CompilationResult

class FlatSerializer:
    """
    平铺化序列化器：将嵌套的 AST 和 符号表 结构
    序列化为扁平的、基于 UID 引用的字典格式。
    """
    def __init__(self):
        self.node_pool: Dict[str, Any] = {}
        self.symbol_pool: Dict[str, Any] = {}
        self.scope_pool: Dict[str, Any] = {}
        self.type_pool: Dict[str, Any] = {}
        self.external_assets: Dict[str, str] = {} # [IES 2.2] 存储外部文本资产: uid -> content
        self.type_map: Dict[int, str] = {} # 映射内存 ID 到稳定 UID

    def serialize_artifact(self, artifact: CompilationArtifact) -> Dict[str, Any]:
        """序列化整个蓝图产物"""
        modules_data = {}
        for name, res in artifact.modules.items():
            modules_data[name] = self.serialize_result(res)
            
        return {
            "entry_module": artifact.entry_module,
            "modules": modules_data,
            "global_symbols": artifact.global_symbols,
            "pools": {
                "nodes": self.node_pool,
                "symbols": self.symbol_pool,
                "scopes": self.scope_pool,
                "types": self.type_pool,
                "assets": self.external_assets # [IES 2.2]
            }
        }

    def serialize_result(self, result: CompilationResult) -> Dict[str, Any]:
        """将 CompilationResult 转换为扁平化字典"""
        # 1. 首先处理核心入口 (会触发递归收集)
        root_scope_uid = self._collect_scope(result.symbol_table)
        root_node_uid = self._collect_node(result.module_ast)

        # 2. 重新映射侧表 (支持跨模块符号懒加载)
        remaped_scenes = {}
        for node, scene in result.node_scenes.items():
            node_uid = self._collect_node(node)
            remaped_scenes[node_uid] = scene.name if hasattr(scene, 'name') else str(scene)

        remaped_node_to_symbol = {}
        for node, sym in result.node_to_symbol.items():
            node_uid = self._collect_node(node)
            sym_uid = self._collect_symbol(sym)
            remaped_node_to_symbol[node_uid] = sym_uid

        remaped_node_to_type = {}
        for node, type_name in result.node_to_type.items():
            node_uid = self._collect_node(node)
            remaped_node_to_type[node_uid] = type_name

        remaped_node_is_deferred = {}
        for node, val in result.node_is_deferred.items():
            node_uid = self._collect_node(node)
            remaped_node_is_deferred[node_uid] = val

        return {
            "root_node_uid": root_node_uid,
            "root_scope_uid": root_scope_uid,
            "side_tables": {
                "node_scenes": remaped_scenes,
                "node_to_symbol": remaped_node_to_symbol,
                "node_to_type": remaped_node_to_type,
                "node_is_deferred": remaped_node_is_deferred
            },
            "pools": {
                "nodes": self.node_pool,
                "symbols": self.symbol_pool,
                "scopes": self.scope_pool,
                "types": self.type_pool,
                "assets": self.external_assets # [IES 2.2]
            }
        }

    def _collect_node(self, node: Any) -> Optional[str]:
        if not isinstance(node, ast.IbASTNode):
            return None
        
        node_id = id(node)
        if node_id in self.type_map:
            return self.type_map[node_id]
            
        uid = f"node_{uuid.uuid4().hex[:16]}"
        self.type_map[node_id] = uid
        
        node_data = {"_type": node.__class__.__name__}
        
        for field_name, value in vars(node).items():
            node_data[field_name] = self._process_value(value)

        self.node_pool[uid] = node_data
        return uid

    def _collect_symbol(self, sym: Symbol) -> str:
        sym_id = id(sym)
        if sym_id in self.type_map:
            return self.type_map[sym_id]
            
        uid = f"sym_{uuid.uuid4().hex[:16]}"
        self.type_map[sym_id] = uid
        
        sym_data = {
            "uid": uid,
            "name": sym.name,
            "kind": sym.kind.name,
            "type_uid": self._collect_type(sym.type_info) if hasattr(sym, 'type_info') and sym.type_info else None,
            "node_uid": self._collect_node(sym.def_node) if hasattr(sym, 'def_node') and sym.def_node else None,
            "owned_scope_uid": self._collect_scope(sym.owned_scope) if sym.owned_scope else None,
            "metadata": sym.metadata
        }
        self.symbol_pool[uid] = sym_data
        return uid

    def _collect_type(self, t: StaticType) -> str:
        """收集类型对象"""
        t_id = id(t)
        if t_id in self.type_map:
            return self.type_map[t_id]
            
        uid = f"type_{uuid.uuid4().hex[:16]}"
        self.type_map[t_id] = uid
        
        type_data = {
            "uid": uid,
            "name": t.name,
            "descriptor": t.descriptor.name if t.descriptor else None
        }
        # 如果是复合类型（如 ListType, DictType），递归收集
        if hasattr(t, 'element_type'):
            type_data["element_type_uid"] = self._collect_type(t.element_type)
        if hasattr(t, 'key_type'):
            type_data["key_type_uid"] = self._collect_type(t.key_type)
        if hasattr(t, 'value_type'):
            type_data["value_type_uid"] = self._collect_type(t.value_type)
            
        self.type_pool[uid] = type_data
        return uid

    def _collect_scope(self, scope: SymbolTable) -> str:
        scope_id = id(scope)
        if scope_id in self.type_map:
            return self.type_map[scope_id]
            
        uid = f"scope_{uuid.uuid4().hex[:16]}"
        self.type_map[scope_id] = uid
        
        scope_data = {
            "uid": uid,
            "parent_uid": self._collect_scope(scope.parent) if scope.parent else None,
            "symbols": {name: self._collect_symbol(sym) for name, sym in scope.symbols.items()},
            "global_refs": list(scope.global_refs)
        }
        self.scope_pool[uid] = scope_data
        return uid

    def _process_text_asset(self, text: str) -> Any:
        """[IES 2.2 Security Update] 文本资产化处理：大文本或特殊文本外置"""
        if not isinstance(text, str):
            return text
            
        # 安全阈值：超过 128 字符，或包含可能引起 JSON 冲突的字符 (目前只要是 str 且较长就外置)
        if len(text) > 128 or '\n' in text or '\"' in text:
            uid = f"asset_{uuid.uuid4().hex[:16]}"
            self.external_assets[uid] = text
            return {"_type": "ext_ref", "uid": uid}
        return text

    def _process_value(self, value: Any) -> Any:
        if isinstance(value, ast.IbASTNode):
            return self._collect_node(value)
        elif isinstance(value, list):
            return [self._process_value(v) for v in value]
        elif isinstance(value, dict):
            return {k: self._process_value(v) for k, v in value.items()}
        elif isinstance(value, Enum):
            return value.name
        elif isinstance(value, str):
            return self._process_text_asset(value)
        elif hasattr(value, "__dict__"): # [IES 2.2] 支持 SimpleNamespace 或其他自定义对象
            return {k: self._process_value(v) for k, v in vars(value).items()}
        return value
