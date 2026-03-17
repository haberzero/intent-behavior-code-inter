from typing import Dict, Any, List, Optional, Union
import uuid
import json
from enum import Enum
from core.domain import ast as ast
from core.domain.symbols import Symbol, SymbolTable
from core.domain.types.descriptors import TypeDescriptor, ClassMetadata, FunctionMetadata, BoundMethodMetadata, ListMetadata, DictMetadata
from core.domain.blueprint import CompilationArtifact, CompilationResult
from core.foundation.serialization import BaseFlatSerializer

class FlatSerializer(BaseFlatSerializer):
    """
    平铺化序列化器：将嵌套的 AST 和 符号表 结构
    序列化为扁平的、基于 UID 引用的字典格式。
    """
    def __init__(self):
        super().__init__()
        self.node_pool: Dict[str, Any] = {}
        self.symbol_pool: Dict[str, Any] = {}
        self.scope_pool: Dict[str, Any] = {}

    def serialize_artifact(self, artifact: CompilationArtifact) -> Dict[str, Any]:
        """序列化整个蓝图产物"""
        modules_data = {}
        for name, res in artifact.modules.items():
            modules_data[name] = self.serialize_result(res)
            
        # [IES 2.1 Fix] 确保全局符号也被正确池化，而非裸字典导出
        serialized_globals = {}
        if artifact.global_symbols:
            for name, sym in artifact.global_symbols.items():
                if isinstance(sym, Symbol):
                    serialized_globals[name] = self._collect_symbol(sym)
                else:
                    # 对于非符号对象，执行基础序列化
                    serialized_globals[name] = self._process_value(sym)

        return {
            "entry_module": artifact.entry_module,
            "modules": modules_data,
            "global_symbols": serialized_globals,
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
        for node, type_obj in result.node_to_type.items():
            node_uid = self._collect_node(node)
            type_uid = self._collect_type(type_obj)
            remaped_node_to_type[node_uid] = type_uid

        remaped_node_is_deferred = {}
        for node, val in result.node_is_deferred.items():
            node_uid = self._collect_node(node)
            remaped_node_is_deferred[node_uid] = val

        remaped_node_intents = {}
        for node, intents in result.node_intents.items():
            node_uid = self._collect_node(node)
            remaped_node_intents[node_uid] = [self._collect_node(i) for i in intents]

        remaped_node_to_loc = {}
        for node, loc in result.node_to_loc.items():
            node_uid = self._collect_node(node)
            remaped_node_to_loc[node_uid] = loc

        return {
            "root_node_uid": root_node_uid,
            "root_scope_uid": root_scope_uid,
            "side_tables": {
                "node_scenes": remaped_scenes,
                "node_to_symbol": remaped_node_to_symbol,
                "node_to_type": remaped_node_to_type,
                "node_is_deferred": remaped_node_is_deferred,
                "node_intents": remaped_node_intents,
                "node_to_loc": remaped_node_to_loc
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

    def _collect_symbol(self, sym: Any) -> str:
        sym_id = id(sym)
        if sym_id in self.type_map:
            return self.type_map[sym_id]
            
        uid = f"sym_{uuid.uuid4().hex[:16]}"
        self.type_map[sym_id] = uid
        
        # [Robustness] 兼容直接在 members 中存储 TypeDescriptor 的情况
        if isinstance(sym, TypeDescriptor):
            sym_data = {
                "uid": uid,
                "name": sym.name,
                "kind": "VARIABLE", # 默认视为变量符号
                "type_uid": self._collect_type(sym),
                "node_uid": None,
                "owned_scope_uid": None,
                "metadata": {"is_synthetic": True}
            }
        else:
            sym_data = {
                "uid": uid,
                "name": sym.name,
                "kind": sym.kind.name if hasattr(sym.kind, 'name') else str(sym.kind),
                "type_uid": self._collect_type(sym.descriptor) if hasattr(sym, 'descriptor') and sym.descriptor else None,
                "node_uid": self._collect_node(sym.def_node) if hasattr(sym, 'def_node') and sym.def_node else None,
                "owned_scope_uid": self._collect_scope(sym.owned_scope) if hasattr(sym, 'owned_scope') and sym.owned_scope else None,
                "metadata": sym.metadata
            }
        self.symbol_pool[uid] = sym_data
        return uid

    def _collect_type(self, t: TypeDescriptor) -> str:
        """收集类型对象"""
        t_id = id(t)
        if t_id in self.type_map:
            return self.type_map[t_id]
            
        uid = f"type_{uuid.uuid4().hex[:16]}"
        self.type_map[t_id] = uid
        
        type_data = {
            "uid": uid,
            "kind": t.__class__.__name__,
            "name": t.name,
            "module_path": t.module_path,
            "is_nullable": t.is_nullable,
            "is_user_defined": t.is_user_defined, # [NEW]
        }
        
        # [IES 2.1 Refactor] 多态收集类型引用，消除 isinstance 硬编码检查
        refs = t.get_references()
        for key, val in refs.items():
            if val is None: continue
            if isinstance(val, list):
                type_data[f"{key}_uids"] = [self._collect_type(p) for p in val]
            else:
                type_data[f"{key}_uid"] = self._collect_type(val)
        
        # [IES 2.1 Refactor] 使用 is_class() 代替 isinstance 检查
        if t.is_class():
            # 这里的字段是字符串，直接存储
            type_data["parent_name"] = getattr(t, "parent_name", None)
            type_data["parent_module"] = getattr(t, "parent_module", None)
            
        # [NEW] 收集成员表 (实现元数据与符号系统的闭环)
        # 运行时加载器虽然不认符号，但序列化时需要将成员符号中的类型 UID 提取出来
        if t.members:
            type_data["members_uids"] = {
                name: self._collect_symbol(sym) for name, sym in t.members.items()
            }
            
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

    def _process_value(self, value: Any) -> Any:
        if isinstance(value, ast.IbASTNode):
            return self._collect_node(value)
        return super()._process_value(value)
