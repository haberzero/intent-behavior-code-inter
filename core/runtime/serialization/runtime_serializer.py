import json
import uuid
from typing import Dict, Any, List, Optional, Union
from core.compiler.serialization.serializer import FlatSerializer
from core.runtime.interpreter.runtime_context import RuntimeContextImpl, ScopeImpl, RuntimeSymbolImpl
from core.runtime.objects.kernel import IbObject, IbClass, IbModule, IbFunction, IbNativeObject, IbNativeFunction, IbBoundMethod, IbNone
from core.runtime.objects.builtins import IbInteger, IbFloat, IbString, IbList, IbDict

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

    def serialize_context(self, context: RuntimeContextImpl) -> Dict[str, Any]:
        """序列化完整的运行时上下文"""
        # 1. 递归序列化作用域链 (从当前作用域向上)
        root_scope_uid = self._collect_runtime_scope(context.current_scope)
        
        # 2. 序列化意图栈和全局设置
        return {
            "version": "2.0",
            "root_scope_uid": root_scope_uid,
            "global_intents": context.get_global_intents(),
            "intent_stack": [self._process_value(i) for i in context.intent_stack],
            "intent_exclusive_depth": context._intent_exclusive_depth,
            "pools": {
                "instances": self.instance_pool,
                "runtime_scopes": self.runtime_scope_pool,
                "types": self.type_pool # 复用基类的类型池
            }
        }

    def _collect_runtime_scope(self, scope: Any) -> Optional[str]:
        if scope is None:
            return None
            
        scope_id = id(scope)
        if scope_id in self.memo:
            return self.memo[scope_id]
            
        uid = f"rt_scope_{uuid.uuid4().hex[:8]}"
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
            
        uid = f"inst_{uuid.uuid4().hex[:8]}"
        self.memo[obj_id] = uid
        
        data = {
            "uid": uid,
            "class_name": obj.ib_class.name,
        }
        
        # 根据子类类型进行差异化序列化
        if isinstance(obj, IbNone):
            data["_type"] = "none"

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

        elif isinstance(obj, IbNativeFunction):
            data["_type"] = "native_func"
            data["name"] = obj._name
            data["unbox"] = obj.unbox_args
            data["is_method"] = obj.is_method
            # 注意：原生函数本身不持久化代码，假设恢复环境中有同名注册
            
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
        """从字典数据重建运行时上下文"""
        pools = data.get("pools", {})
        self.instance_pool = pools.get("instances", {})
        self.runtime_scope_pool = pools.get("runtime_scopes", {})
        
        # 1. 重建作用域链
        root_scope_uid = data["root_scope_uid"]
        current_scope = self._get_scope(root_scope_uid)
        
        # 2. 确定全局作用域 (最顶层)
        global_scope = current_scope
        while global_scope.parent:
            global_scope = global_scope.parent
            
        context = RuntimeContextImpl(initial_scope=global_scope, registry=self.registry)
        context._current_scope = current_scope
        
        # 3. 恢复状态
        context._global_intents = data.get("global_intents", [])
        context.intent_stack = [self._deserialize_value(i) for i in data.get("intent_stack", [])]
        context._intent_exclusive_depth = data.get("intent_exclusive_depth", 0)
        
        return context

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
            # 先缓存占位符，因为 receiver 或 method 可能会循环引用回来
            # 但 BoundMethod 构造函数需要参数，所以我们这里需要一点技巧
            receiver = self._get_instance(data["receiver_uid"])
            method = self._get_instance(data["method_uid"])
            obj = IbBoundMethod(receiver, method)
            self.instance_cache[uid] = obj
            
        elif _type == "native_func":
            # 原生函数重建：假设它已经在 Registry 中了
            # 这里我们通过名称查找，或者如果找不到，尝试保持占位符
            # 实际上，这应该由具体环境（如 Builtins）在反序列化后重新绑定
            # 暂时通过 Registry.get_class("Function") 创建一个空壳
            obj = IbNativeFunction(lambda *a: None, ib_class=ib_class, name=data["name"])
            self.instance_cache[uid] = obj
            
        else:
            # 普通对象
            obj = IbObject(ib_class)
            self.instance_cache[uid] = obj
            obj.fields = {k: self._deserialize_value(v) for k, v in data.get("fields", {}).items()}
            
        return obj
