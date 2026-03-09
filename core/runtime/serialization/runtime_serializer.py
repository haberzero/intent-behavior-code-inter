import json
import uuid
from typing import Dict, Any, List, Optional, Union, Callable
from core.compiler.serialization.serializer import FlatSerializer
from core.runtime.interpreter.runtime_context import RuntimeContextImpl, ScopeImpl, RuntimeSymbolImpl
from core.runtime.objects.kernel import IbObject, IbClass, IbModule, IbFunction, IbNativeObject, IbNativeFunction, IbBoundMethod, IbNone
from core.runtime.objects.builtins import IbInteger, IbFloat, IbString, IbList, IbDict, IbBehavior

class RuntimeSerializer(FlatSerializer):
    """
    深度运行时序列化器：扩展 FlatSerializer，支持对运行时对象图和执行上下文的持久化。
    """
    def __init__(self, registry):
        super().__init__()
        self.registry = registry
        self.instance_pool: Dict[str, Any] = {}
        self.runtime_scope_pool: Dict[str, Any] = {}
        self.memo: Dict[int, str] = {} # 记录已处理对象的 Python ID

    def serialize_context(self, context: RuntimeContextImpl, include_static: bool = True) -> Dict[str, Any]:
        """序列化完整的运行时上下文"""
        # 1. 递归序列化作用域链 (从当前作用域向上)
        root_scope_uid = self._collect_runtime_scope(context.current_scope)
        
        pools = {
            "instances": self.instance_pool,
            "runtime_scopes": self.runtime_scope_pool,
            "types": self.type_pool # 复用基类的类型池
        }
        
        # [IES 2.1] 如果需要，包含静态池以实现全量快照
        if include_static and hasattr(context, '_interpreter') and context._interpreter:
            itp = context._interpreter
            pools["nodes"] = itp.node_pool
            pools["symbols"] = itp.symbol_pool
            pools["scopes"] = itp.scope_pool
            
        # 2. 序列意图栈和全局设置
        return {
            "version": "2.0",
            "root_scope_uid": root_scope_uid,
            "global_intents": context.get_global_intents(),
            "intent_stack": [self._process_value(i) for i in context.get_active_intents()],
            "intent_exclusive_depth": context._intent_exclusive_depth,
            "pools": pools
        }

    def _collect_runtime_scope(self, scope: Any) -> Optional[str]:
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
        if hasattr(scope, '_uid_to_symbol'):
            for suid, sym in scope._uid_to_symbol.items():
                uid_symbols_data[suid] = self._serialize_symbol(sym)

        self.runtime_scope_pool[uid] = {
            "uid": uid,
            "parent_uid": self._collect_runtime_scope(scope.parent) if scope.parent else None,
            "symbols": symbols_data,
            "uid_to_symbol": uid_symbols_data
        }
        return uid

    def _serialize_symbol(self, sym: RuntimeSymbolImpl) -> Dict[str, Any]:
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
            # 尝试记录原生值，如果不可序列化则记录为 Repr
            val = obj.to_native()
            try:
                json.dumps(val)
                data["py_value"] = val
            except:
                data["py_value"] = f"<Non-Serializable: {repr(val)}>"
                
        elif isinstance(obj, (IbInteger, IbFloat, IbString)):
            data["_type"] = "primitive"
            data["value"] = obj.to_native()
            
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
    def __init__(self, registry):
        self.registry = registry
        self.instance_cache: Dict[str, IbObject] = {}
        self.scope_cache: Dict[str, ScopeImpl] = {}

    def deserialize_context(self, data: Dict[str, Any]) -> RuntimeContextImpl:
        """从字典数据重建运行时上下文 (已修复方法覆盖 BUG)"""
        # 1. 首先恢复所有平铺池 (包括编译器池和运行时池)
        pools = data.get("pools", {})
        self.node_pool = pools.get("nodes", {})
        self.symbol_pool = pools.get("symbols", {})
        self.scope_pool = pools.get("scopes", {})
        self.type_pool = pools.get("types", {})
        self.instance_pool = pools.get("instances", {})
        self.runtime_scope_pool = pools.get("runtime_scopes", {})

        # 2. 从当前/根作用域开始重建作用域链
        root_scope_uid = data["root_scope_uid"]
        current_scope = self._get_scope(root_scope_uid)
        
        # 3. 向上回溯确定全局作用域
        global_scope = current_scope
        while global_scope.parent:
            global_scope = global_scope.parent
            
        # 4. 创建 Context 实例
        from core.runtime.interpreter.runtime_context import RuntimeContextImpl
        context = RuntimeContextImpl(initial_scope=global_scope, registry=self.registry)
        context._current_scope = current_scope
        
        # 5. 恢复意图栈、全局意图及排他深度
        context._global_intents = data.get("global_intents", [])
        context.intent_stack = [self._deserialize_value(i) for i in data.get("intent_stack", [])]
        context._intent_exclusive_depth = data.get("intent_exclusive_depth", 0)
        
        return context

    def on_rebind(self, logic_id_map: Dict[str, Any]):
        """
        [IES 2.0] 全局重绑定协议。
        扫描已实例化的对象池，将带有 logic_id 的占位对象链接到当前环境的真实实现。
        """
        for obj in self.instance_cache.values():
            if isinstance(obj, IbNativeFunction) and obj.logic_id:
                if obj.logic_id in logic_id_map:
                    obj.py_func = logic_id_map[obj.logic_id]

    def _get_scope(self, uid: str) -> ScopeImpl:
        if uid in self.scope_cache:
            return self.scope_cache[uid]
            
        data = self.runtime_scope_pool[uid]
        parent_uid = data.get("parent_uid")
        parent = self._get_scope(parent_uid) if parent_uid else None
        
        # [FIX] 先创建对象并入缓存，然后再填充符号，防止递归死循环
        scope = ScopeImpl(parent=parent, registry=self.registry)
        self.scope_cache[uid] = scope
        
        # 恢复普通符号
        for name, sym_data in data.get("symbols", {}).items():
            scope._symbols[name] = self._deserialize_symbol(sym_data)
            
        # 恢复编译器绑定的 UID 符号
        for suid, sym_data in data.get("uid_to_symbol", {}).items():
            scope._uid_to_symbol[suid] = self._deserialize_symbol(sym_data)
            
        return scope

    def _deserialize_symbol(self, data: Dict[str, Any]) -> RuntimeSymbolImpl:
        val = self._deserialize_value(data["value"])
        return RuntimeSymbolImpl(
            name=data["name"], 
            value=val, 
            is_const=data.get("is_const", False)
        )

    def _deserialize_value(self, val: Any) -> Any:
        # 如果是 UID 引用，则从池中重建对象
        if isinstance(val, str) and val.startswith("inst_"):
            return self._get_instance(val)
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
            obj = self.registry.box(data["value"])
            self.instance_cache[uid] = obj
            
        elif _type == "list":
            obj = IbList([], ib_class)
            self.instance_cache[uid] = obj # 先入缓存防止递归
            obj.elements = [self._deserialize_value(e) for e in data.get("elements", [])]
            
        elif _type == "dict":
            obj = IbDict({}, ib_class)
            self.instance_cache[uid] = obj
            obj.fields = {k: self._deserialize_value(v) for k, v in data.get("fields", {}).items()}
            
        elif _type == "module":
            # 模块对象需要特殊处理其内部作用域
            scope = self._get_scope(data["scope_uid"])
            obj = IbModule(data["name"], scope, registry=self.registry)
            self.instance_cache[uid] = obj
            
        elif _type == "native":
            # 原生对象重建 (目前仅支持基本类型，否则保持 Repr 字符串)
            py_val = data.get("py_value")
            obj = self.registry.box(py_val)
            self.instance_cache[uid] = obj

        elif _type == "bound_method":
            # [FIX] 解决循环引用：先解析 method，创建 IbBoundMethod 占位，再解析 receiver (可能参与循环)
            method = self._get_instance(data["method_uid"])
            obj = IbBoundMethod(None, method)
            self.instance_cache[uid] = obj
            obj.receiver = self._get_instance(data["receiver_uid"])
            
        elif _type == "native_func":
            # 原生函数重建：记录逻辑标识以供后续重绑定
            logic_id = data.get("logic_id")
            # 创建一个占位函数
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
            # [IES 2.0] 行为对象重建：先创建空壳，后续由 Interpreter 补齐引用
            obj = IbBehavior(data["node_uid"], None, [], data.get("expected_type"))
            self.instance_cache[uid] = obj
            obj.captured_intents = [self._deserialize_value(i) for i in data.get("captured_intents", [])]
            
        else:
            # 普通对象
            obj = IbObject(ib_class)
            self.instance_cache[uid] = obj
            obj.fields = {k: self._deserialize_value(v) for k, v in data.get("fields", {}).items()}
            
        return obj
