import uuid
from enum import Enum
from dataclasses import asdict, is_dataclass
from typing import Dict, List, Any, Optional, Set
from core.domain import ast as ast
from core.domain.symbols import Symbol, SymbolTable, StaticType

class FlatSerializer:
    """
    平铺化序列化器：将 AST 和符号表转换为无循环引用的扁平化池结构。
    """
    def __init__(self):
        self.node_pool: Dict[str, Dict[str, Any]] = {}
        self.symbol_pool: Dict[str, Dict[str, Any]] = {}
        self.scope_pool: Dict[str, Dict[str, Any]] = {}
        self.type_pool: Dict[str, Dict[str, Any]] = {}
        self.type_map: Dict[int, str] = {} # 映射内存 ID 到稳定 UID
        self._visited_nodes: Set[int] = set()

    def serialize_result(self, result: 'CompilationResult') -> Dict[str, Any]:
        """将 CompilationResult 转换为扁平化字典"""
        # 1. 首先处理符号表和符号
        root_scope_uid = self._collect_scope(result.symbol_table)
        
        # 2. 处理 AST 树
        root_node_uid = self._collect_node(result.module_ast)

        return {
            "root_node_uid": root_node_uid,
            "root_scope_uid": root_scope_uid,
            "side_tables": {
                "node_scenes": {uid: scene.name if hasattr(scene, 'name') else str(scene) 
                               for uid, scene in result.node_scenes.items()},
                "node_to_symbol": result.node_to_symbol,
                "node_to_type": result.node_to_type
            },
            "pools": {
                "nodes": self.node_pool,
                "symbols": self.symbol_pool,
                "scopes": self.scope_pool,
                "types": self.type_pool
            }
        }

    def serialize_artifact(self, artifact: 'CompilationArtifact') -> Dict[str, Any]:
        """[NEW] 将完整的 CompilationArtifact 序列化为扁平化字典，共享池结构"""
        modules_data = {}
        for name, res in artifact.modules.items():
            modules_data[name] = self.serialize_result(res)
            
        return {
            "entry_module": artifact.entry_module,
            "modules": modules_data,
            "pools": {
                "nodes": self.node_pool,
                "symbols": self.symbol_pool,
                "scopes": self.scope_pool,
                "types": self.type_pool
            },
            # 全局符号处理
            "global_symbols": {name: asdict(sym) if hasattr(sym, '__dataclass_fields__') else str(sym) 
                               for name, sym in (artifact.global_symbols or {}).items()}
        }

    def _collect_node(self, node: Any) -> Optional[str]:
        if not isinstance(node, ast.ASTNode):
            return None
        
        # 分配 UID
        if not node.uid:
            node.uid = f"node_{uuid.uuid4().hex[:8]}"
        
        node_id = id(node)
        if node_id in self._visited_nodes:
            return node.uid
        self._visited_nodes.add(node_id)

        node_data = {"_type": node.__class__.__name__}
        
        for field_name, value in vars(node).items():
            # 排除掉 UID (已在外部处理)
            if field_name == 'uid':
                continue
            
            node_data[field_name] = self._process_value(value)

        self.node_pool[node.uid] = node_data
        return node.uid

    def _collect_scope(self, scope: SymbolTable) -> str:
        if not scope.uid:
            scope.uid = f"scope_{uuid.uuid4().hex[:8]}"
        
        if scope.uid in self.scope_pool:
            return scope.uid

        # 预先占位，防止递归死循环
        scope_data = {
            "uid": scope.uid,
            "parent_uid": None,
            "symbols": {},
            "global_refs": list(scope.global_refs) # 记录全局引用
        }
        self.scope_pool[scope.uid] = scope_data

        if scope.parent:
            scope_data["parent_uid"] = self._collect_scope(scope.parent)

        for name, sym in scope.symbols.items():
            sym_uid = self._collect_symbol(sym)
            scope_data["symbols"][name] = sym_uid

        return scope.uid

    def _collect_symbol(self, sym: Symbol) -> str:
        if not sym.uid:
            sym.uid = f"sym_{uuid.uuid4().hex[:8]}"
        
        if sym.uid in self.symbol_pool:
            return sym.uid

        sym_data = {
            "uid": sym.uid,
            "name": sym.name,
            "kind": sym.kind.name,
            "node_uid": sym.node_uid,
            "owned_scope_uid": self._collect_scope(sym.owned_scope) if sym.owned_scope else None,
            "metadata": sym.metadata
        }
        
        # 处理类型信息 (池化)
        type_info = getattr(sym, 'type_info', None) or getattr(sym, 'static_type', None)
        if type_info:
            sym_data["type_uid"] = self._collect_type(type_info)

        self.symbol_pool[sym.uid] = sym_data
        return sym.uid

    def _process_value(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._process_value(v) for v in value]
        if isinstance(value, ast.ASTNode):
            return self._collect_node(value)
        if isinstance(value, Enum):
            return value.name
        if is_dataclass(value) and not isinstance(value, ast.ASTNode):
            return asdict(value)
        return value

    def _collect_type(self, t: StaticType) -> str:
        """池化处理静态类型，使用稳定递增的 UID"""
        type_id_int = id(t)
        if type_id_int in self.type_map:
            return self.type_map[type_id_int]
            
        # 生成稳定 UID：类型名 + 池中序号
        type_uid = f"type_{t.name}_{len(self.type_pool)}"
        self.type_map[type_id_int] = type_uid
        
        res = {"uid": type_uid, "name": t.name, "_type": t.__class__.__name__}
        self.type_pool[type_uid] = res # 先存入池，防止递归
        
        if hasattr(t, 'descriptor') and t.descriptor:
            res["uts_descriptor"] = asdict(t.descriptor)
        
        # 1. 处理容器类型
        if hasattr(t, '_element_type') and t._element_type:
            res["element_type_uid"] = self._collect_type(t._element_type)
        
        if hasattr(t, '_key_type') and t._key_type:
            res["key_type_uid"] = self._collect_type(t._key_type)
        if hasattr(t, '_value_type') and t._value_type:
            res["value_type_uid"] = self._collect_type(t._value_type)
        
        # 2. 处理类类型 (避免递归 scope，只记录 ID)
        if hasattr(t, 'scope') and t.scope:
            res["scope_uid"] = self._collect_scope(t.scope)
            
        # 3. 处理函数签名
        if hasattr(t, 'param_types') and t.param_types:
            res["param_types_uids"] = [self._collect_type(p) for p in t.param_types]
        if hasattr(t, 'return_type') and t.return_type:
            res["return_type_uid"] = self._collect_type(t.return_type)
            
        return type_uid
