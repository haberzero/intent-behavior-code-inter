from typing import Dict, Any, List, Optional, Union
import json
from enum import Enum
from core.kernel import ast as ast
from core.kernel.symbols import Symbol, SymbolTable
from core.kernel.spec import IbSpec, TypeDef
from core.kernel.spec.specs import TypeDef
from core.kernel.spec.base import TypeKind
from core.kernel.spec.type_ref import TypeRef
from core.kernel.blueprint import CompilationArtifact, CompilationResult
from core.base.serialization import BaseFlatSerializer
from core.base.uid import node_uid, type_uid, anon_symbol_uid

# S4 声明驱动：payload 字段名 → 序列化字段名映射（历史兼容）。
# positional_element_types 的序列化键为 positional_type_names（rehydrator 历史约定）。
_PAYLOAD_FIELD_NAMES = {
    "positional_element_types": "positional_type",
}

class FlatSerializer(BaseFlatSerializer):
    """
    平铺化序列化器：将嵌套的 AST 和 符号表 结构
    序列化为扁平的、基于 UID 引用的字典格式。
    """
    def __init__(self, registry: Optional[Any] = None):
        super().__init__()
        self.node_pool: Dict[str, Any] = {}
        self.symbol_pool: Dict[str, Any] = {}
        self.scope_pool: Dict[str, Any] = {}
        # 类型注册表（可选）：用于把 CLASS 父类泛型实参（TypeRef）解析为
        # spec 并递归收集（父特化 spec 非符号/绑定引用的孤点）。
        self.registry = registry
        # 泛型声明表（S4 声明驱动）：经 GenericTypeRegistry 驱动泛型承载字段
        # 收集（payload_fields），消除 per-kind 手工分支。
        self.generic_types = None
        if registry is not None:
            generic_types = getattr(registry, "generic_types", None)
            if generic_types is not None:
                self.generic_types = generic_types

    def serialize_artifact(self, artifact: CompilationArtifact) -> Dict[str, Any]:
        """序列化整个蓝图产物"""
        modules_data = {}
        # 排序模块名以确保输出稳定
        for name in sorted(artifact.modules.keys()):
            res = artifact.modules[name]
            modules_data[name] = self.serialize_result(res)
            
        # 确保全局符号也被正确池化，而非裸字典导出
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
                "assets": self.external_assets
            }
        }

    def serialize_result(self, result: CompilationResult) -> Dict[str, Any]:
        """将 CompilationResult 转换为扁平化字典"""
        # 1. 首先处理核心入口 (会触发递归收集)
        root_scope_uid = self._collect_scope(result.symbol_table)
        root_node_uid = self._collect_node(result.module_ast)

        # 2. 重新映射侧表 (支持跨模块符号懒加载)
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

        remaped_node_to_loc = {}
        for node, loc in result.node_to_loc.items():
            node_uid = self._collect_node(node)
            remaped_node_to_loc[node_uid] = loc

        return {
            "root_node_uid": root_node_uid,
            "root_scope_uid": root_scope_uid,
            "import_star_members": dict(result.import_star_members),
            "side_tables": {
                "node_to_symbol": remaped_node_to_symbol,
                "node_to_type": remaped_node_to_type,
                "node_to_loc": remaped_node_to_loc
            },
            "pools": {
                "nodes": self.node_pool,
                "symbols": self.symbol_pool,
                "scopes": self.scope_pool,
                "types": self.type_pool,
                "assets": self.external_assets
            }
        }

    def _collect_node(self, node: Any) -> Optional[str]:
        if not isinstance(node, ast.IbASTNode):
            return None
        
        node_id = id(node)
        if node_id in self.type_map:
            return self.type_map[node_id]
            

        # 先收集字段数据，再根据内容生成确定性哈希作为 UID。
        node_data = {"_type": node.__class__.__name__}
        
        for field_name, value in vars(node).items():
            node_data[field_name] = self._process_value(value)

        # 序列化为稳定 JSON 字符串并生成哈希
        content_str = json.dumps(node_data, sort_keys=True)
        uid = node_uid(content_str)
        
        self.type_map[node_id] = uid
        self.node_pool[uid] = node_data
        return uid

    def _collect_symbol(self, sym: Any) -> str:
        sym_id = id(sym)
        if sym_id in self.type_map:
            return self.type_map[sym_id]
            
        # 使用符号自身的稳定 UID (name@depth)
        uid = getattr(sym, 'uid', None)
        if not uid:
            if hasattr(sym, 'get_content_hash'):
                uid = anon_symbol_uid(sym.get_content_hash())
            else:
                uid = anon_symbol_uid(f"{hash(str(sym)) & 0xFFFFFFFFFFFFFFFF:016x}")
        
        self.type_map[sym_id] = uid
        
        sym_data = {
            "uid": uid,
            "name": sym.name,
            "kind": sym.kind.name if hasattr(sym.kind, 'name') else str(sym.kind),
            "type_uid": self._collect_type(sym.spec) if hasattr(sym, 'spec') and sym.spec else None,
            "node_uid": self._collect_node(sym.def_node) if hasattr(sym, 'def_node') and sym.def_node else None,
            "owned_scope_uid": self._collect_scope(sym.owned_scope) if hasattr(sym, 'owned_scope') and sym.owned_scope else None,
            "metadata": sym.metadata
        }
        self.symbol_pool[uid] = sym_data
        return uid

    def _collect_type(self, t: IbSpec) -> str:
        """收集类型对象"""
        t_id = id(t)
        if t_id in self.type_map:
            return self.type_map[t_id]
            
        # 基于类型全名生成稳定 UID
        uid = type_uid(t.module_path, t.name)
        self.type_map[t_id] = uid
        
        type_data = {
            "uid": uid,
            "kind": t.kind,
            "name": t.name,
            "module_path": t.module_path,
            "provenance": t.provenance.name,
            "visibility": t.visibility.name,
            "storage_model": t.storage_model.name,
            "exported_types": list(getattr(t, "exported_types", [])),
        }

        # Persist scalar fields for callable-instance specs (fn_callable[T] / behavior[T])
        # so the runtime rehydrator can reconstruct the proper variant.
        # ``axiom_name`` carries the "fn_callable" / "behavior" axiom dispatch key,
        # which is needed to disambiguate the two variants now that they share
        # ``TypeKind.CALLABLE_INSTANCE``.
        # ``capture_mode`` is NOT persisted here — it lives on the runtime value
        # (IbFnCallable/IbBehavior) and on the AST node, both of which round-trip
        # through their own channels.
        if t.kind == TypeKind.CALLABLE_INSTANCE.value:
            type_data["axiom_name"] = t.get_base_name()

        # 声明驱动泛型承载字段（S4）：经 GenericTypeDeclaration.payload_fields
        # 统一收集类型实参（value_type/element_type/wrapped_type 等），消除
        # per-kind 手工分支。非泛型 kind（CLASS/FUNCTION 等）不在此列。
        self._collect_generic_payload(t, type_data)

        # Persist TypeDef param/return signature for structural checking.
        if t.kind == TypeKind.CALLABLE_SIG.value:
            type_data["param_type_names"] = [p.head for p in t.param_types]
            ret_ref = t.return_type
            type_data["return_type_name"] = ret_ref.head if ret_ref is not None else "auto"

        # 多态收集类型引用，消除 isinstance 硬编码检查
        refs = t.get_references()
        for key, val in refs.items():
            if val is None: continue
            if isinstance(val, list):
                type_data[f"{key}_uids"] = [self._collect_type(p) for p in val]
            else:
                type_data[f"{key}_uid"] = self._collect_type(val)
        
        # 使用 is_class() 代替 isinstance 检查
        if t.kind == TypeKind.CLASS.value:
            # 父类引用：从 parent_type TypeRef 提取扁平名供反序列化使用
            p_ref = t.parent_type
            type_data["parent_name"] = p_ref.head if p_ref is not None else None
            type_data["parent_module"] = p_ref.module if p_ref is not None else None
            # 父类泛型实参（class Sub[T](Box[T]) / 特化 Sub[int] 的 Box[int]）：
            # 持久化实参名，rehydrator 据此重建泛型 parent_type。父特化 spec
            # （如 Box[int]）非符号/绑定引用，须在此经 registry 解析并收集。
            if p_ref is not None and p_ref.args:
                type_data["parent_args"] = [a.canonical_name for a in p_ref.args]
                # 父特化 spec（Box[int]）非符号/绑定引用孤点：经 registry 按
                # 特化全名解析并收集，否则运行时 metadata_registry 缺父特化。
                if self.registry is not None:
                    parent_spec = self.registry.resolve(
                        p_ref.canonical_name, p_ref.module
                    )
                    if parent_spec is not None:
                        self._collect_type(parent_spec)
            # 用户类泛型类型参数（class Box[T]）：持久化供 rehydrate 重建。
            if getattr(t, "type_params", None):
                type_data["type_params"] = list(t.type_params)
            # 用户类泛型特化实参（Box[int] → ["int"]）+ 原始基类名：
            # 持久化供 from_spec 结构化构造与 rehydrate 重建。
            if getattr(t, "type_args", None):
                type_data["type_args"] = [a.canonical_name for a in t.type_args]
            if getattr(t, "base_name", None):
                type_data["base_name"] = t.base_name
            
        # 收集成员表 (实现元数据与符号系统的闭环)
        # 运行时加载器虽然不认符号，但序列化时需要将成员符号中的类型 UID 提取出来
        if t.members:
            type_data["members_uids"] = {
                name: self._collect_symbol(sym) for name, sym in t.members.items()
            }
            
        self.type_pool[uid] = type_data
        return uid

    def _collect_generic_payload(self, t: "TypeDef", type_data: dict) -> None:
        """声明驱动泛型承载字段收集（S4）。

        经 ``GenericTypeDeclaration.payload_fields`` 统一持久化类型实参——
        value_type/element_type/wrapped_type 等 TypeRef 字段写
        ``{field}_name``/``{field}_module``（canonical_name 保真嵌套），
        key_type/value_type 为 dict 双字段。消除 per-kind 手工分支
        （serializer 曾对 thread/thread_result/chan/slot/generator 各写一份
        value_type 持久化代码）。非泛型 kind（CLASS/FUNCTION 等）无声明，跳过。
        """
        from core.kernel.spec.base import TypeKind

        if t.kind in (TypeKind.CLASS.value, TypeKind.FUNCTION.value,
                      TypeKind.BOUND_METHOD.value, TypeKind.MODULE.value,
                      TypeKind.CALLABLE_SIG.value, TypeKind.TYPE_PARAM.value,
                      TypeKind.PRIMITIVE.value, TypeKind.LAZY.value,
                      TypeKind.SUBSCRIBER.value):
            return
        base_name = t.get_base_name()
        generic_types = self.generic_types
        if generic_types is None:
            # 无 registry 路径：构建默认 GenericTypeRegistry（声明驱动不依赖
            # 具体注册表实例，纯声明表）。消除 per-kind 手工分支。
            from core.kernel.spec.generic import create_generic_registry
            generic_types = create_generic_registry()
        decl = generic_types.get(base_name)
        if decl is None or not decl.payload_fields:
            return
        for field in decl.payload_fields:
            refs = getattr(t, field, None)
            # 序列化字段名（历史兼容映射：positional_element_types → positional_type）
            name_key = _PAYLOAD_FIELD_NAMES.get(field, field)
            if isinstance(refs, list):
                if not refs:
                    continue
                type_data[f"{name_key}_names"] = [r.canonical_name for r in refs]
                type_data[f"{name_key}_modules"] = [r.module for r in refs]
            elif refs is not None:
                type_data[f"{name_key}_name"] = refs.canonical_name
                type_data[f"{name_key}_module"] = refs.module

    def _collect_scope(self, scope: SymbolTable) -> str:
        scope_id = id(scope)
        if scope_id in self.type_map:
            return self.type_map[scope_id]
            
        # 使用作用域自身的路径 UID
        uid = scope.uid
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
