import json
import uuid
from typing import Dict, Any, List, Optional, Union, Callable
from core.base.serialization import BaseFlatSerializer
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger
from core.base.enums import StorageModel
from core.runtime.interfaces import IExecutionContext, IStateProvider, Scope, RuntimeSymbol, IObjectFactory, RuntimeContext
from core.runtime.objects.kernel import IbObject, IbValue, IbClass, IbModule, IbFunction, IbNativeObject, IbNativeFunction, IbBoundMethod
from core.runtime.objects.primitives import IbOptional
from core.runtime.objects.intent_node import IntentNode
from core.runtime.objects.intent import IbIntent
from core.runtime.objects.intent_context import IbIntentContext
from core.kernel.intent_logic import IntentMode, IntentRole

class RuntimeSerializer(BaseFlatSerializer):
    """
    深度运行时序列化器：继承 BaseFlatSerializer，支持对运行时对象图和执行上下文的持久化。
    """
    def __init__(self, registry):
        super().__init__()
        self.registry = registry
        self.instance_pool: Dict[str, Any] = {}
        self.runtime_scope_pool: Dict[str, Any] = {}
        self.intent_pool: Dict[str, Any] = {} # 意图节点池，实现拓扑序列化
        self.memo: Dict[int, str] = {} # 记录已处理对象的 Python ID

    def serialize_context(self, context: IStateProvider, include_static: bool = True, execution_context: Optional[IExecutionContext] = None) -> Dict[str, Any]:
        """序列化完整的运行时上下文"""
        # 1. 递归序列化作用域链 (从当前作用域向上)
        root_scope_uid = self._collect_runtime_scope(context.get_current_scope())
        
        pools = {
            "instances": self.instance_pool,
            "runtime_scopes": self.runtime_scope_pool,
            "intents": self.intent_pool,
            "types": self.type_pool,
            "assets": self.external_assets 
        }
        
        # 如果提供，包含静态池以实现全量快照
        if include_static and execution_context:
            pools["nodes"] = execution_context.node_pool
            pools["symbols"] = execution_context.symbol_pool
            pools["scopes"] = execution_context.scope_pool
            pools["types"] = execution_context.type_pool
            # 合并现有的资产池
            self.external_assets.update(execution_context.asset_pool)

        # 完整 IbIntentContext + 活跃 intent_context IBCI 指针。
        # 快照序列化失败必须 fail-fast：静默丢弃会使恢复端拿到错误的意图上下文。
        full_intent_ctx_uid = None
        intent_ctx = context.intent_context
        if intent_ctx is not None:
            full_intent_ctx_uid = self._collect_intent_context(intent_ctx)

        active_intent_ibobj_uid = None
        active = context.get_active_intent_ibobj()
        if active is not None:
            active_intent_ibobj_uid = self._collect_instance(active)

        return {
            "version": "2.1",
            "root_scope_uid": root_scope_uid,
            "global_intents": context.get_global_intents(),
            "intent_stack": self._process_value(context.intent_stack),
            "intent_ctx_uid": full_intent_ctx_uid,
            "active_intent_ibobj_uid": active_intent_ibobj_uid,
            "pools": pools
        }

    def _collect_intent_node(self, node: Any) -> str:
        """ 实现 IntentNode 的拓扑序列化，保留链表引用关系"""
        if node is None:
            return None
            
        node_id = id(node)
        if node_id in self.memo:
            return self.memo[node_id]
            
        uid = f"intent_{uuid.uuid4().hex[:16]}"
        self.memo[node_id] = uid
        
        # 记录节点内容及父节点引用
        self.intent_pool[uid] = {
            "uid": uid,
            "intent": self._process_value(node.intent),
            "parent_uid": self._collect_intent_node(node.parent) if node.parent else None
        }
        return uid

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
        for suid, sym in scope.get_all_symbols_by_uid().items():
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
        
        # 拓扑序列化 IntentNode，保留结构共享
        if isinstance(value, IntentNode):
            return self._collect_intent_node(value)

        # 拓扑序列化 IbIntentContext Python 值
        if isinstance(value, IbIntentContext):
            return self._collect_intent_context(value)

        # 处理基本 Python 类型 (Fallback)
        return super()._process_value(value)

    def _collect_intent_context(self, ic: Any) -> str:
        """序列化完整的 ``IbIntentContext`` Python 对象。

        保留全部 6 个槽位：``_intent_top`` (持久栈) / ``_smear_queue`` (涂抹队列) /
        ``_override`` (排他槽) / ``_global_intents`` (Engine 级注入) /
        ``_inherited_smear`` (从父帧继承的涂抹) / ``_inherited_override`` (从父帧继承的排他)。
        通过 Python id memo 维持身份共享。
        """
        ic_id = id(ic)
        if ic_id in self.memo:
            return self.memo[ic_id]

        uid = f"intentctx_{uuid.uuid4().hex[:16]}"
        self.memo[ic_id] = uid

        intent_top = ic.get_intent_top()
        data = {
            "uid": uid,
            "intent_top_uid": self._collect_intent_node(intent_top) if intent_top is not None else None,
            "smear_queue": [self._process_value(i) for i in ic._smear_queue],
            "override": self._process_value(ic._override) if ic._override is not None else None,
            "global_intents": [self._process_value(i) for i in ic._global_intents],
            "inherited_smear": [self._process_value(i) for i in ic._inherited_smear],
            "inherited_override": self._process_value(ic._inherited_override) if ic._inherited_override is not None else None,
        }
        # 复用 instance_pool 作为统一对象池；以 ``_type == "intent_context_native"``
        # 区分于 IBCI ``intent_context`` 封装实例。
        data["_type"] = "intent_context_native"
        self.instance_pool[uid] = data
        return uid

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
        if isinstance(obj, IbValue):
            type_ref = obj.type_ref
            data["type_ref"] = str(type_ref) if type_ref is not None else None
            if obj.meta:
                data["value_meta"] = dict(obj.meta)

        # 类元对象（IbClass）：序列化为类引用（类名），反序列化时重绑定 registry
        # 真实类——此前落 else object 分支展开为空 fields，反序列化时被
        # registry.get_class 构造为对应类的空普通实例，类型符号身份破坏。
        # 类型符号是"类型引用"而非实例值（与 IbModule scope_native 模式一致）。
        if isinstance(obj, IbClass):
            data["_type"] = "class_ref"
            data["name"] = obj.name
            self.instance_pool[uid] = data
            return uid

        # 瞬态对象协议：实现 __transient_state__ 的对象序列化为纯状态存根，不递归
        # 运行时句柄（thread 的 coordinator 引用环 / chan 的队列 / slot 的值 /
        # subscriber 的订阅视图）。检测用公开 dunder 协议（与 disk_backed 鸭子
        # 先例一致），非 per-type 类名分支。state 值经 _process_value 递归
        # （嵌套 IbObject 如 slot 的值保持完整往返）。
        if not isinstance(obj, IbClass) and hasattr(obj, "__transient_state__"):
            state = obj.__transient_state__()
            data["_type"] = "transient"
            data["state"] = {k: self._process_value(v) for k, v in state.items()}
            self.instance_pool[uid] = data
            return uid
        
        # 根据类型名进行差异化序列化（通过 ib_class.name 而非 isinstance 分派）
        cls_name = obj.ib_class.name

        # 按 storage_model 分发：磁盘型对象序列化为路径描述符，不物化字节。
        # 注意：只处理实例（IbValue），不处理类元对象（IbClass）。
        spec = obj.ib_class.spec
        if isinstance(obj, IbValue) and spec is not None and spec.storage_model is StorageModel.DISK_BACKED:
            data["_type"] = "disk_backed"
            descriptor = obj.receive("__to_descriptor__", [])
            # 协议返回不保证为 IbObject：鸭子拆箱（receive 可返回第三方/原生描述符）
            if hasattr(descriptor, "to_native"):
                descriptor = descriptor.to_native()
            data["descriptor"] = descriptor
            self.instance_pool[uid] = data
            return uid

        if isinstance(obj, IbValue) and cls_name == "None":
            data["_type"] = "none"

        elif isinstance(obj, IbNativeFunction):
            data["_type"] = "native_func"
            data["name"] = obj._name
            data["unbox"] = obj.unbox_args
            data["is_method"] = obj.is_method
            if obj.logic_id:
                data["logic_id"] = obj.logic_id
                
        elif isinstance(obj, IbNativeObject):
            data["_type"] = "native"
            # 记录原生值；非 JSON 序列化值必须 fail-fast——占位字符串会
            # 在恢复时静默替换为错误数据，掩盖真实的序列化失败。
            val = obj.to_native()
            try:
                json.dumps(val)
            except (TypeError, ValueError) as e:
                raise TypeError(
                    f"Cannot serialize native object of class '{cls_name}': "
                    f"to_native() produced non-JSON-serializable value {val!r}"
                ) from e
            data["py_value"] = val
                
        elif isinstance(obj, IbValue) and cls_name in ("int", "float", "str", "bool"):
            data["_type"] = "primitive"
            data["value"] = self._process_value(obj.to_native())
            
        elif isinstance(obj, IbValue) and cls_name == "list":
            data["_type"] = "list"
            data["elements"] = [self._process_value(e) for e in obj.elements]

        elif isinstance(obj, IbValue) and cls_name == "tuple":
            data["_type"] = "tuple"
            data["elements"] = [self._process_value(e) for e in obj.elements]
            
        elif isinstance(obj, IbValue) and cls_name == "dict":
            data["_type"] = "dict"
            data["fields"] = {str(k): self._process_value(v) for k, v in obj.fields.items()}

        elif isinstance(obj, IbValue) and cls_name == "Optional":
            data["_type"] = "optional"
            data["is_some"] = obj._is_some
            data["inner"] = self._process_value(obj.payload) if obj._is_some else None

        # thread_result 是 IbValue 值对象（payload 承载成功值）——
        # 按 ib_class.name 分发而非 isinstance。
        elif cls_name == "thread_result" and not isinstance(obj, IbClass):
            from core.runtime.objects.thread import ThreadStatus
            data["_type"] = "thread_result"
            data["status"] = obj._status
            data["value"] = self._process_value(obj.payload) if obj._status == ThreadStatus.DONE else None
            data["error"] = self._process_value(obj._error) if obj._error is not None else None

        elif isinstance(obj, IbModule):
            data["_type"] = "module"
            data["name"] = obj.name
            # Kernel-native modules are backed by an IbNativeObject (the runtime
            # implementation), not a Scope. They are re-bound at load time by
            # HostService._rebind_environment, so we must not recurse into the
            # native implementation here.
            if hasattr(obj.scope, "get_all_symbols"):
                data["scope_uid"] = self._collect_runtime_scope(obj.scope)
            else:
                data["scope_native"] = True

        elif isinstance(obj, IbBoundMethod):
            data["_type"] = "bound_method"
            data["receiver_uid"] = self._collect_instance(obj.receiver)
            data["method_uid"] = self._collect_instance(obj.method)

        elif isinstance(obj, IbValue) and cls_name == "behavior":
            data["_type"] = "behavior"
            data["node_uid"] = obj.node
            # captured_intents 协议：None 或 IbIntentContext。
            # 此处展开为 active_intents 的 list 形态以兼容序列化反序列化的读取方。
            ci = obj.captured_intents
            if ci is None:
                data["captured_intents"] = []
            elif isinstance(ci, IbIntentContext):
                data["captured_intents"] = [self._process_value(i) for i in ci.get_active_intents()]
            else:
                raise TypeError(
                    "Unexpected captured_intents type "
                    f"{type(ci).__name__} (contract requires None or IbIntentContext)"
                )
            data["expected_type"] = obj.expected_type
            if obj.call_intent is not None:
                data["call_intent"] = self._process_value(obj.call_intent)

        elif isinstance(obj, IbValue) and cls_name == "fn_callable":
            data["_type"] = "fn_callable"
            data["node_uid"] = obj.node_uid
            data["capture_mode"] = obj.capture_mode

        elif cls_name == "intent_context":
            # ``intent_context`` IBCI 封装实例序列化
            data["_type"] = "intent_context"
            ctx = obj.fields.get("_ctx")
            data["ctx_uid"] = self._collect_intent_context(ctx) if ctx is not None else None
            extra_fields = {
                k: self._process_value(v)
                for k, v in (obj.fields or {}).items()
                if k != "_ctx"
            }
            if extra_fields:
                data["fields"] = extra_fields

        elif isinstance(obj, IbIntent):
            # ``IbIntent`` 使用 ``__slots__`` 存放状态
            data["_type"] = "intent"
            data["content"] = obj.content
            data["mode"] = obj.mode.value if hasattr(obj.mode, "value") else str(obj.mode)
            data["tag"] = obj.tag
            data["role"] = obj.role.value if hasattr(obj.role, "value") else str(obj.role)
            data["source_uid"] = obj.source_uid
            data["pop_top"] = obj.pop_top
            if obj.segments:
                data["segments"] = [self._process_value(s) for s in obj.segments]

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
        self.intent_cache: Dict[str, IntentNode] = {}
        self.intent_ctx_cache: Dict[str, Any] = {}
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
        self.intent_pool = pools.get("intents", {}) 
        self.asset_pool = pools.get("assets", {}) 
        
        if not self.factory:
            raise RuntimeError("RuntimeDeserializer: ObjectFactory is required for deserialization.")

        root_scope_uid = data["root_scope_uid"]
        current_scope = self._get_scope(root_scope_uid)
        
        global_scope = current_scope
        while global_scope.parent:
            global_scope = global_scope.parent
            
        context = self.factory.create_context(initial_scope=global_scope)
        context.current_scope = current_scope

        intent_ctx_uid = data.get("intent_ctx_uid")
        if intent_ctx_uid:
            restored_ctx = self._get_intent_context(intent_ctx_uid)
            if restored_ctx is not None:
                context.replace_intent_context(restored_ctx)
            active_uid = data.get("active_intent_ibobj_uid")
            if active_uid:
                active_obj = self._get_instance(active_uid)
                # 确保共享引用不变量
                if active_obj is not None:
                    if active_obj.fields.get("_ctx") is not context.intent_context:
                        active_obj.fields["_ctx"] = context.intent_context
                context.set_active_intent_ibobj(active_obj)
        else:
            if "global_intents" in data:
                # 恢复全局意图 (通常是 IbIntent 实例)
                ctx_global = context.get_global_intents()
                ctx_global.clear()
                for i_data in data["global_intents"]:
                    ctx_global.append(self._deserialize_value(i_data))

            # 恢复意图栈 (拓扑结构)
            intent_stack_raw = data.get("intent_stack")
            active_intents = self._deserialize_value(intent_stack_raw)

            # 恢复活跃意图栈
            context.restore_active_intents(active_intents)

        return context

    def _get_intent_context(self, uid: str) -> Any:
        """从池中重建 IbIntentContext Python 对象（共享身份）。"""
        if uid in self.intent_ctx_cache:
            return self.intent_ctx_cache[uid]
        data = self.instance_pool.get(uid)
        if data is None or data.get("_type") != "intent_context_native":
            return None
        ic = IbIntentContext()
        # 先入缓存以打断潜在的循环引用
        self.intent_ctx_cache[uid] = ic
        # 持久栈
        top_uid = data.get("intent_top_uid")
        if top_uid:
            ic.set_intent_top(self._get_intent_node(top_uid))
        # smear_queue
        for sv in data.get("smear_queue", []) or []:
            iv = self._deserialize_value(sv)
            if iv is not None:
                ic._smear_queue.append(iv)
        # override
        ov = data.get("override")
        if ov is not None:
            ic._override = self._deserialize_value(ov)
        # global_intents
        for gv in data.get("global_intents", []) or []:
            iv = self._deserialize_value(gv)
            if iv is not None:
                ic._global_intents.append(iv)
        # inherited_smear
        for sv in data.get("inherited_smear", []) or []:
            iv = self._deserialize_value(sv)
            if iv is not None:
                ic._inherited_smear.append(iv)
        # inherited_override
        iov = data.get("inherited_override")
        if iov is not None:
            ic._inherited_override = self._deserialize_value(iov)
        return ic

    def _get_intent_node(self, uid: str) -> IntentNode:
        """ 从池中重建 IntentNode 链表节点，保留结构共享"""
        if uid in self.intent_cache:
            return self.intent_cache[uid]
            
        data = self.intent_pool[uid]
        intent = self._deserialize_value(data["intent"])
        parent_uid = data.get("parent_uid")
        parent_node = self._get_intent_node(parent_uid) if parent_uid else None
        
        node = IntentNode(intent, parent_node)
        self.intent_cache[uid] = node
        return node

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
            scope.define(name, sym.value, declared_type=sym.declared_type, is_const=sym.is_const)
            
        for suid, sym_data in data.get("uid_to_symbol", {}).items():
            sym = self._deserialize_symbol(sym_data)
            scope.bind_symbol_by_uid(suid, sym)
            
        return scope

    def _deserialize_symbol(self, data: Dict[str, Any]) -> RuntimeSymbol:
        val = self._deserialize_value(data["value"])
        return self.factory.create_runtime_symbol(
            name=data["name"], 
            value=val, 
            is_const=data.get("is_const", False)
        )

    def _deserialize_value(self, val: Any) -> Any:
        if isinstance(val, str):
            # 引用解析守卫：仅当字符串确实是本池中的引用 UID 才按引用解析，
            # 否则视为普通字面量——避免用户数据撞 inst_/intent_ 前缀被误判
            # 为引用（此前 `"inst_userdata"` 未在池中也会 KeyError）。
            if val.startswith("inst_") and (val in self.instance_pool or val in self.instance_cache):
                return self._get_instance(val)
            if val.startswith("intent_") and not val.startswith("intentctx_") and (
                val in self.intent_pool or val in self.intent_cache
            ):
                return self._get_intent_node(val)
            if val.startswith("intentctx_") and (
                val in self.instance_pool or val in self.intent_ctx_cache
            ):
                return self._get_intent_context(val)

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
        cls_name = data["class_name"] if "class_name" in data else None
        ib_class = self.registry.get_class(cls_name) if cls_name else None
        
        obj = None
        _type = data.get("_type")

        if _type == "class_ref":
            # 类引用：重绑定 registry 真实类——类型符号是"类型引用"
            # 而非实例值，反序列化后必须仍为 IbClass（类型身份保留）。
            # 必须 return：否则落入下方 else 分支被覆盖为 IbObject(ib_class)。
            obj = self.registry.get_class(data.get("name"))
            self.instance_cache[uid] = obj
            return obj

        elif _type == "intent_context_native":
            # 该条目不是 IbObject 实例，由 ``_get_intent_context`` 处理。
            # 调用方误以 inst_ 前缀来到这里时，回退到 native 路径。
            return self._get_intent_context(uid)

        if _type == "disk_backed":
            descriptor = data.get("descriptor", {})
            descriptor_obj = (
                self.factory.create_dict(dict(descriptor))
                if self.factory is not None
                else descriptor
            )
            obj = ib_class.receive("__from_descriptor__", [descriptor_obj])
            self.instance_cache[uid] = obj
            return obj

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

        elif _type == "tuple":
            # Cache an empty IbTuple first to break potential circular references,
            # then fill elements (mirroring the cache-before-recurse pattern used for IbList).
            obj = self.factory.create_tuple(())
            self.instance_cache[uid] = obj
            obj.elements = tuple(self._deserialize_value(e) for e in data.get("elements", []))
            
        elif _type == "dict":
            # Cache an empty IbDict first to break potential circular references,
            # then fill fields (mirroring the cache-before-recurse pattern used for IbList/IbTuple).
            obj = self.factory.create_dict({})
            self.instance_cache[uid] = obj
            obj.fields = {k: self._deserialize_value(v) for k, v in data.get("fields", {}).items()}

        elif _type == "optional":
            is_some = data.get("is_some", False)
            inner = self._deserialize_value(data.get("inner")) if is_some else None
            obj = IbOptional(ib_class, inner, is_some)
            self.instance_cache[uid] = obj

        elif _type == "thread_result":
            from core.runtime.objects.thread import ThreadStatus
            from core.runtime.objects.thread_result import IbThreadResult
            status = data.get("status", ThreadStatus.DONE)
            value = self._deserialize_value(data.get("value")) if status == ThreadStatus.DONE else None
            error = self._deserialize_value(data.get("error")) if data.get("error") is not None else None
            obj = IbThreadResult(ib_class, value=value, error=error, status=status)
            self.instance_cache[uid] = obj

        elif _type == "transient":
            # 瞬态对象不可复活（活体句柄/队列/订阅视图），重建为携带已知状态的
            # 占位 IbObject 供内省（快照恢复后仍可读取 mode/name/value/state 等）。
            # thread 原 thread_transient 亦走本路径（行为不变，多保留状态）。
            obj = IbObject(ib_class)
            self.instance_cache[uid] = obj
            obj.fields["_transient_state"] = {
                k: self._deserialize_value(v) for k, v in data.get("state", {}).items()
            }

        elif _type == "module":
            if data.get("scope_native"):
                # Kernel-native module: the real implementation is re-bound at
                # load time. We only need a stable placeholder here.
                obj = self.factory.create_module(
                    data["name"], self.factory.create_scope(parent=None)
                )
            else:
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
            call_intent_raw = data.get("call_intent")
            call_intent = self._deserialize_value(call_intent_raw) if call_intent_raw is not None else None
            obj = self.factory.create_behavior(data["node_uid"], captured, data.get("expected_type"), call_intent=call_intent)
            self.instance_cache[uid] = obj

        elif _type == "intent_context":
            # ``intent_context`` IBCI 封装实例 — 先入缓存（打断潜在循环），
            # 再恢复 ``_ctx`` 字段为对应的 native IbIntentContext（共享身份）。
            obj = IbObject(ib_class)
            self.instance_cache[uid] = obj
            ctx_uid = data.get("ctx_uid")
            if ctx_uid:
                obj.fields["_ctx"] = self._get_intent_context(ctx_uid)
            for k, v in (data.get("fields") or {}).items():
                obj.fields[k] = self._deserialize_value(v)

        elif _type == "intent":
            # ``IbIntent`` 反序列化分支
            try:
                mode = IntentMode(data.get("mode", "+"))
            except Exception as e:
                # 序列化端恒写合法 .value；异常只来自损坏/版本漂移数据。
                # 静默降级会改变意图语义（OVERRIDE→APPEND）——fail-fast 显式暴露。
                raise ValueError(f"deserialize intent mode {data.get('mode')!r} invalid: {e!r}") from e
            try:
                role = IntentRole(data.get("role", "block"))
            except Exception as e:
                raise ValueError(f"deserialize intent role {data.get('role')!r} invalid: {e!r}") from e
            segments_raw = data.get("segments") or []
            segments = [self._deserialize_value(s) for s in segments_raw]
            obj = IbIntent(
                ib_class=ib_class,
                content=data.get("content", ""),
                segments=segments,
                mode=mode,
                tag=data.get("tag"),
                source_uid=data.get("source_uid"),
                role=role,
                pop_top=data.get("pop_top", False),
            )
            self.instance_cache[uid] = obj

        else:
            obj = IbObject(ib_class)
            self.instance_cache[uid] = obj
            obj.fields = {k: self._deserialize_value(v) for k, v in data.get("fields", {}).items()}
            
        return obj
