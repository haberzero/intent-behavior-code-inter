import json
import uuid
from typing import Dict, Any, List, Optional, Union, Callable
from core.base.serialization import BaseFlatSerializer
from core.runtime.interfaces import IExecutionContext, IStateProvider, Scope, RuntimeSymbol, IObjectFactory, RuntimeContext
from core.runtime.objects.kernel import IbObject, IbClass, IbModule, IbFunction, IbNativeObject, IbNativeFunction, IbBoundMethod, IbNone
from core.runtime.objects.builtins import IbInteger, IbFloat, IbString, IbList, IbDict, IbBehavior

class RuntimeSerializer(BaseFlatSerializer):
    """
    深度运行时序列化器：继承 BaseFlatSerializer，支持对运行时对象图和执行上下文的持久化。
    """
    def __init__(self, registry):
        super().__init__()
        self.registry = registry
        self.instance_pool: Dict[str, Any] = {}
        self.runtime_scope_pool: Dict[str, Any] = {}
        self.memo: Dict[int, str] = {} # 记录已处理对象的 Python ID

    def serialize_context(self, context: IStateProvider, include_static: bool = True, execution_context: Optional[IExecutionContext] = None) -> Dict[str, Any]:
        """序列化完整的运行时上下文"""
        # 1. 递归序列化作用域链 (从当前作用域向上)
        root_scope_uid = self._collect_runtime_scope(context.get_current_scope())
        
        pools = {
            "instances": self.instance_pool,
            "runtime_scopes": self.runtime_scope_pool,
            "types": self.type_pool,
            "assets": self.external_assets 
        }
        
        # [IES 2.1] 如果提供，包含静态池以实现全量快照
        if include_static and execution_context:
            pools["nodes"] = execution_context.node_pool
            pools["symbols"] = execution_context.symbol_pool
            pools["scopes"] = execution_context.scope_pool
            pools["types"] = execution_context.type_pool
            # [IES 2.2] 合并现有的资产池
            if hasattr(execution_context, 'asset_pool'):
                self.external_assets.update(execution_context.asset_pool)
            
        return {
            "version": "2.0",
            "root_scope_uid": root_scope_uid,
            "global_intents": context.get_global_intents(),
            "intent_stack": [self._process_value(i) for i in context.get_active_intents()],
            "intent_exclusive_depth": context.intent_exclusive_depth,
            "pools": pools
        }

    def _collect_runtime_scope(self, scope: Optional[Scope]) -> Optional[str]:
        if scope is None:
            return None
            
        scope_id = id(scope)
        if scope_id in self.memo:
            return self.memo[scope_id]
            
        uid = f"rt_scope_{uuid.uuid4().hex[:16]}"
        self.memo[scope_id] = uid
        
        # 序列化当前作用域的所有符号
        symbols_data = {}
        for name, sym in scope.get_all_symbols().items():
            symbols_data[name] = self._serialize_symbol(sym)
            
        uid_symbols_data = {}
        # 注意：_uid_to_symbol 目前不在 Scope 接口中，但这是内部实现细节
        # 如果需要彻底解耦，应在 Scope 接口中增加获取 UID 符号的方法
        if hasattr(scope, '_uid_to_symbol'):
            for suid, sym in getattr(scope, '_uid_to_symbol').items():
                uid_symbols_data[suid] = self._serialize_symbol(sym)

        self.runtime_scope_pool[uid] = {
            "uid": uid,
            "parent_uid": self._collect_runtime_scope(scope.parent) if scope.parent else None,
            "symbols": symbols_data,
            "uid_to_symbol": uid_symbols_data
        }
        return uid

    def _serialize_symbol(self, sym: RuntimeSymbol) -> Dict[str, Any]:
        return {
            "name": sym.name,
            "value": self._process_value(sym.value),
            "is_const": sym.is_const,
            "declared_type": str(sym.declared_type) if sym.declared_type else None
        }

    def _process_value(self, value: Any) -> Any:
        # 处理 IbObject 及其子类
        if isinstance(value, IbObject):
            return self._collect_instance(value)
        
        # 处理基本 Python 类型 (Fallback)
        return super()._process_value(value)

    def _collect_instance(self, obj: IbObject) -> str:
        obj_id = id(obj)
        if obj_id in self.memo:
            return self.memo[obj_id]
            
        uid = f"inst_{uuid.uuid4().hex[:16]}"
        self.memo[obj_id] = uid
        
        data = {
            "uid": uid,
            "class_name": obj.ib_class.name,
        }
        
        # 根据子类类型进行差异化序列化
        if isinstance(obj, IbNone):
            data["_type"] = "none"

        elif isinstance(obj, IbNativeFunction):
            data["_type"] = "native_func"
            data["name"] = obj._name
            data["unbox"] = obj.unbox_args
            data["is_method"] = obj.is_method
            if hasattr(obj, 'logic_id') and obj.logic_id:
                data["logic_id"] = obj.logic_id
                
        elif isinstance(obj, IbNativeObject):
            data["_type"] = "native"
            # 尝试记录原生值
            val = obj.to_native()
            try:
                json.dumps(val)
                data["py_value"] = val
            except:
                data["py_value"] = f"<Non-Serializable: {repr(val)}>"
                
        elif isinstance(obj, (IbInteger, IbFloat, IbString)):
            data["_type"] = "primitive"
            data["value"] = self._process_value(obj.to_native())
            
        elif isinstance(obj, IbList):
            data["_type"] = "list"
            data["elements"] = [self._process_value(e) for e in obj.elements]
            
        elif isinstance(obj, IbDict):
            data["_type"] = "dict"
            data["fields"] = {str(k): self._process_value(v) for k, v in obj.fields.items()}
            
        elif isinstance(obj, IbModule):
            data["_type"] = "module"
            data["name"] = obj.name
            data["scope_uid"] = self._collect_runtime_scope(obj.scope)

        elif isinstance(obj, IbBoundMethod):
            data["_type"] = "bound_method"
            data["receiver_uid"] = self._collect_instance(obj.receiver)
            data["method_uid"] = self._collect_instance(obj.method)

        elif isinstance(obj, IbBehavior):
            data["_type"] = "behavior"
            data["node_uid"] = obj.node
            data["captured_intents"] = [self._process_value(i) for i in obj.captured_intents]
            data["expected_type"] = obj.expected_type
            
        else:
            # 普通用户定义对象
            data["_type"] = "object"
            data["fields"] = {k: self._process_value(v) for k, v in obj.fields.items()}
            
        self.instance_pool[uid] = data
        return uid

class RuntimeDeserializer:
    """
    运行时反序列化器：从扁平化池数据重建完整的执行上下文和对象图。
    """
    def __init__(self, registry: Any, factory: Optional[IObjectFactory] = None):
        self.registry = registry
        self.factory = factory
        self.instance_cache: Dict[str, IbObject] = {}
        self.scope_cache: Dict[str, Scope] = {}
        self.asset_pool: Dict[str, str] = {} 

    def deserialize_context(self, data: Dict[str, Any]) -> RuntimeContext:
        """从字典数据重建运行时上下文"""
        pools = data.get("pools", {})
        self.node_pool = pools.get("nodes", {})
        self.symbol_pool = pools.get("symbols", {})
        self.scope_pool = pools.get("scopes", {})
        self.type_pool = pools.get("types", {})
        self.instance_pool = pools.get("instances", {})
        self.runtime_scope_pool = pools.get("runtime_scopes", {})
        self.asset_pool = pools.get("assets", {}) 
        
        if not self.factory:
            raise RuntimeError("RuntimeDeserializer: ObjectFactory is required for deserialization.")

        root_scope_uid = data["root_scope_uid"]
        current_scope = self._get_scope(root_scope_uid)
        
        global_scope = current_scope
        while global_scope.parent:
            global_scope = global_scope.parent
            
        context = self.factory.create_context(initial_scope=global_scope)
        # 使用反射设置私有属性，保持接口纯净
        if hasattr(context, '_current_scope'):
            setattr(context, '_current_scope', current_scope)
            
        if "global_intents" in data:
            # 恢复全局意图 (通常是 IbIntent 实例)
            ctx_global = context.get_global_intents()
            ctx_global.clear()
            for i_data in data["global_intents"]:
                 ctx_global.append(self._deserialize_value(i_data))
        
        intent_stack_data = data.get("intent_stack", [])
        active_intents = [self._deserialize_value(i) for i in intent_stack_data]
        
        # 恢复活跃意图栈
        if hasattr(context, 'restore_active_intents'):
            getattr(context, 'restore_active_intents')(active_intents)
        
        if hasattr(context, '_intent_exclusive_depth'):
            setattr(context, '_intent_exclusive_depth', data.get("intent_exclusive_depth", 0))
        
        return context

    def on_rebind(self, logic_id_map: Dict[str, Any]):
        """全局重绑定协议"""
        for obj in self.instance_cache.values():
            if isinstance(obj, IbNativeFunction) and obj.logic_id:
                if obj.logic_id in logic_id_map:
                    obj.py_func = logic_id_map[obj.logic_id]

    def _get_scope(self, uid: str) -> Scope:
        if uid in self.scope_cache:
            return self.scope_cache[uid]
            
        data = self.runtime_scope_pool[uid]
        parent_uid = data.get("parent_uid")
        parent = self._get_scope(parent_uid) if parent_uid else None
        
        scope = self.factory.create_scope(parent=parent)
        self.scope_cache[uid] = scope
        
        for name, sym_data in data.get("symbols", {}).items():
            sym = self._deserialize_symbol(sym_data)
            scope.define_variable(name, sym.value, declared_type=sym.declared_type, is_const=sym.is_const)
            
        for suid, sym_data in data.get("uid_to_symbol", {}).items():
            sym = self._deserialize_symbol(sym_data)
            if hasattr(scope, 'bind_symbol_by_uid'):
                getattr(scope, 'bind_symbol_by_uid')(suid, sym)
            
        return scope

    def _deserialize_symbol(self, data: Dict[str, Any]) -> RuntimeSymbol:
        val = self._deserialize_value(data["value"])
        return self.factory.create_runtime_symbol(
            name=data["name"], 
            value=val, 
            is_const=data.get("is_const", False)
        )

    def _deserialize_value(self, val: Any) -> Any:
        if isinstance(val, str) and val.startswith("inst_"):
            return self._get_instance(val)
            
        if isinstance(val, dict) and val.get("_type") == "ext_ref":
            uid = val.get("uid")
            if uid in self.asset_pool:
                return self.asset_pool[uid]
            return f"__EXT_ASSET_MISSING_{uid}__"
            
        return val

    def _get_instance(self, uid: str) -> IbObject:
        if uid in self.instance_cache:
            return self.instance_cache[uid]
            
        data = self.instance_pool[uid]
        cls_name = data["class_name"]
        ib_class = self.registry.get_class(cls_name)
        
        obj = None
        _type = data.get("_type")
        
        if _type == "none":
            obj = self.registry.get_none()
            self.instance_cache[uid] = obj

        elif _type == "primitive":
            obj = self.registry.box(self._deserialize_value(data["value"]))
            self.instance_cache[uid] = obj
            
        elif _type == "list":
            obj = self.factory.create_list([])
            self.instance_cache[uid] = obj 
            obj.elements = [self._deserialize_value(e) for e in data.get("elements", [])]
            
        elif _type == "dict":
            # IbDict 尚未有标准工厂方法，暂用 Registry
            obj = IbDict({}, ib_class)
            self.instance_cache[uid] = obj
            obj.fields = {k: self._deserialize_value(v) for k, v in data.get("fields", {}).items()}
            
        elif _type == "module":
            scope = self._get_scope(data["scope_uid"])
            obj = self.factory.create_module(data["name"], scope)
            self.instance_cache[uid] = obj
            
        elif _type == "native":
            py_val = data.get("py_value")
            obj = self.registry.box(py_val)
            self.instance_cache[uid] = obj

        elif _type == "bound_method":
            method = self._get_instance(data["method_uid"])
            obj = IbBoundMethod(None, method)
            self.instance_cache[uid] = obj
            obj.receiver = self._get_instance(data["receiver_uid"])
            
        elif _type == "native_func":
            logic_id = data.get("logic_id")
            obj = IbNativeFunction(
                lambda *a: None, 
                ib_class=ib_class, 
                name=data.get("name", "anonymous"),
                logic_id=logic_id,
                unbox_args=data.get("unbox", False),
                is_method=data.get("is_method", False)
            )
            self.instance_cache[uid] = obj
            
        elif _type == "behavior":
            captured = [self._deserialize_value(i) for i in data.get("captured_intents", [])]
            obj = self.factory.create_behavior(data["node_uid"], captured, data.get("expected_type"))
            self.instance_cache[uid] = obj
            
        else:
            obj = IbObject(ib_class)
            self.instance_cache[uid] = obj
            obj.fields = {k: self._deserialize_value(v) for k, v in data.get("fields", {}).items()}
            
        return obj
