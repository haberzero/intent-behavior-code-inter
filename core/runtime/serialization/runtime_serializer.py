import json
from typing import Dict, Any, List, Optional, Union, Callable, Mapping
from core.base.serialization import BaseFlatSerializer
from core.base.enums import StorageModel
from core.base.uid import rt_scope_uid, rt_intent_uid, rt_intent_ctx_uid, rt_instance_uid
from core.runtime.interfaces import IExecutionContext, IStateProvider, Scope, RuntimeSymbol, IObjectFactory, RuntimeContext
from core.runtime.objects.kernel import IbObject, IbValue, IbClass, IbModule, IbFunction, IbNativeObject, IbNativeFunction, IbBoundMethod
from core.runtime.objects.primitives import IbOptional
from core.runtime.objects.intent_node import IntentNode
from core.runtime.objects.intent import IbIntent
from core.runtime.objects.intent_context import IbIntentContext
from core.runtime.objects.cell import IbCell
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
            
        uid = rt_intent_uid()
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
            
        uid = rt_scope_uid()
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
        # Cell 变量（被内层闭包捕获、已提升）的当前值以 IbCell 为准（与
        # ScopeImpl.get 语义一致：cell 是读写的单一真相源）。
        is_cell = getattr(sym, "cell", None) is not None
        if is_cell and not sym.cell.is_empty():
            value = sym.cell.get()
        else:
            value = sym.value
        return {
            "name": sym.name,
            "value": self._process_value(value),
            "is_const": sym.is_const,
            "declared_type": str(sym.declared_type) if sym.declared_type else None,
            "is_cell": is_cell,
        }

    def _serialize_closure(self, closure: Dict[str, Any], capture_mode: Optional[str]) -> List[Dict[str, Any]]:
        """序列化闭包表（``{sym_uid: (name, slot)}``）。

        - ``cell`` 模式（lambda）：slot 为共享 ``IbCell``，序列化其当前值。
          值在作用域符号中同样可获，但此处冗余携带——闭包持有者可能已离开
          cell 所有者作用域（公理 LT-2 堆语义），仅靠作用域树无法重建该 cell。
        - ``value`` 模式（snapshot）：slot 为定义时刻深克隆种子，直接序列化。
        """
        is_snapshot = capture_mode == "snapshot"
        entries: List[Dict[str, Any]] = []
        for sym_uid, (name, slot) in closure.items():
            if is_snapshot:
                entries.append({
                    "sym_uid": sym_uid,
                    "name": name,
                    "mode": "value",
                    "value": self._process_value(slot) if slot is not None else None,
                })
                continue
            if isinstance(slot, IbCell) and not slot.is_empty():
                cell_value = self._process_value(slot.get())
            else:
                cell_value = self._process_value(slot) if slot is not None else None
            entries.append({
                "sym_uid": sym_uid,
                "name": name,
                "mode": "cell",
                "value": cell_value,
            })
        return entries

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

        uid = rt_intent_ctx_uid()
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

        uid = rt_instance_uid()
        self.memo[obj_id] = uid

        data = {
            "uid": uid,
            # [Module Identity] 存 qualified 类名（geo.Box / geo.Box[int]）——
            # 跨引擎 round-trip 恢复时按运行期类表 qualified 键重绑（内置/入口类
            # qualified == 裸名，零影响）。
            "class_name": obj.ib_class.qualified_name,
        }
        self._collect_instance_meta(obj, data)
        # 直接形态（命中即写池并返回）：类引用 / 瞬态占位 / 磁盘描述符。
        for direct in (
            self._collect_class_ref,
            self._collect_transient,
            self._collect_disk_backed,
        ):
            if direct(obj, data, uid):
                return uid
        # 按类型分派填充 _type 与各类型字段（单一类型一个具名 collector）。
        self._dispatch_instance_kind(obj, data)
        self.instance_pool[uid] = data
        return uid

    def _collect_instance_meta(self, obj: IbObject, data: dict) -> None:
        """公共元数据：type_ref / value_meta（IbValue 专用）。"""
        if isinstance(obj, IbValue):
            type_ref = obj.type_ref
            data["type_ref"] = str(type_ref) if type_ref is not None else None
            # 可调用实例（behavior/fn_callable）的完整状态由专用分支字段承载；
            # meta 冗余拷贝非 JSON 值，专用字段才是单一事实来源，不重复写入。
            if obj.meta and obj.ib_class.name not in ("behavior", "fn_callable"):
                data["value_meta"] = dict(obj.meta)

    def _collect_class_ref(self, obj: IbObject, data: dict, uid: str) -> bool:
        """类元对象 → 类引用（类名），反序列化重绑定 registry 真实类。"""
        if not isinstance(obj, IbClass):
            return False
        data["_type"] = "class_ref"
        data["name"] = obj.qualified_name
        self.instance_pool[uid] = data
        return True

    def _collect_transient(self, obj: IbObject, data: dict, uid: str) -> bool:
        """瞬态对象 → 纯状态存根（不递归运行时句柄）。"""
        if isinstance(obj, IbClass) or not hasattr(obj, "__transient_state__"):
            return False
        state = obj.__transient_state__()
        data["_type"] = "transient"
        data["state"] = {k: self._process_value(v) for k, v in state.items()}
        self.instance_pool[uid] = data
        return True

    def _collect_disk_backed(self, obj: IbObject, data: dict, uid: str) -> bool:
        """磁盘型对象 → 路径描述符（不物化字节）。"""
        if not isinstance(obj, IbValue):
            return False
        spec = obj.ib_class.spec
        if spec is None or spec.storage_model is not StorageModel.DISK_BACKED:
            return False
        data["_type"] = "disk_backed"
        descriptor = obj.receive("__to_descriptor__", [])
        # 协议返回不保证为 IbObject：鸭子拆箱（receive 可返回第三方/原生描述符）
        if hasattr(descriptor, "to_native"):
            descriptor = descriptor.to_native()
        data["descriptor"] = descriptor
        self.instance_pool[uid] = data
        return True

    def _dispatch_instance_kind(self, obj: IbObject, data: dict) -> None:
        """按类型分派序列化字段（单一类型一个具名 collector）。"""
        cls_name = obj.ib_class.name
        # 特化类名（list[int]/Box[int]）沿 spec 基类名分派值层 kind——
        # 内置泛型特化类与用户类特化类均复用基类 collector（
        # 值层身份保真后序列化不落入 object 兜底）。
        base_name = self._value_base_name(obj)
        if isinstance(obj, IbValue) and base_name == "None":
            self._collect_none(data)
        elif isinstance(obj, IbNativeFunction):
            self._collect_native_func(obj, data)
        elif isinstance(obj, IbNativeObject):
            self._collect_native(obj, data, cls_name)
        elif isinstance(obj, IbValue) and base_name in ("int", "float", "str", "bool"):
            self._collect_primitive(obj, data)
        elif isinstance(obj, IbValue) and base_name == "list":
            self._collect_list(obj, data)
        elif isinstance(obj, IbValue) and base_name == "tuple":
            self._collect_tuple(obj, data)
        elif isinstance(obj, IbValue) and base_name == "dict":
            self._collect_dict(obj, data)
        elif isinstance(obj, IbValue) and base_name == "Optional":
            self._collect_optional(obj, data)
        elif base_name == "thread_result" and not isinstance(obj, IbClass):
            self._collect_thread_result(obj, data)
        elif isinstance(obj, IbModule):
            self._collect_module(obj, data)
        elif isinstance(obj, IbBoundMethod):
            self._collect_bound_method(obj, data)
        elif isinstance(obj, IbValue) and base_name == "behavior":
            self._collect_behavior(obj, data)
        elif isinstance(obj, IbValue) and base_name == "fn_callable":
            self._collect_fn_callable(obj, data)
        elif base_name == "intent_context":
            self._collect_intent_context_wrapper(obj, data)
        elif isinstance(obj, IbIntent):
            self._collect_intent(obj, data)
        else:
            self._collect_object(obj, data)

    @staticmethod
    def _value_base_name(obj: IbObject) -> str:
        """值对象的 kind 基类名（特化类沿 spec 基名，普通类即自身名）。

        特化类（``list[int]`` / ``Box[int]``）的 ``ib_class.name`` 含方括号，
        序列化分派须按基类名（``list`` / ``Box``）路由——值层 kind 判定与
        ``IbClass._impl_cls``（沿 base 名解析实现类）同构。
        """
        spec = getattr(obj.ib_class, "spec", None)
        if spec is not None:
            base = spec.get_base_name()
            if base:
                return base
        return obj.ib_class.name

    def _collect_none(self, data: dict) -> None:
        data["_type"] = "none"

    def _collect_native_func(self, obj, data):
        data["_type"] = "native_func"
        data["name"] = obj._name
        data["unbox"] = obj.unbox_args
        data["is_method"] = obj.is_method
        if obj.logic_id:
            data["logic_id"] = obj.logic_id

    def _collect_native(self, obj, data, cls_name):
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

    def _collect_primitive(self, obj, data):
        data["_type"] = "primitive"
        data["value"] = self._process_value(obj.to_native())

    def _collect_list(self, obj, data):
        data["_type"] = "list"
        data["elements"] = [self._process_value(e) for e in obj.elements]

    def _collect_tuple(self, obj, data):
        data["_type"] = "tuple"
        data["elements"] = [self._process_value(e) for e in obj.elements]

    def _collect_dict(self, obj, data):
        data["_type"] = "dict"
        data["fields"] = {str(k): self._process_value(v) for k, v in obj.fields.items()}

    def _collect_optional(self, obj, data):
        data["_type"] = "optional"
        data["is_some"] = obj._is_some
        data["inner"] = self._process_value(obj.payload) if obj._is_some else None

    def _collect_thread_result(self, obj, data):
        from core.runtime.objects.thread import ThreadStatus
        data["_type"] = "thread_result"
        data["status"] = obj._status
        data["value"] = self._process_value(obj.payload) if obj._status == ThreadStatus.DONE else None
        data["error"] = self._process_value(obj._error) if obj._error is not None else None

    def _collect_module(self, obj, data):
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

    def _collect_bound_method(self, obj, data):
        data["_type"] = "bound_method"
        data["receiver_uid"] = self._collect_instance(obj.receiver)
        data["method_uid"] = self._collect_instance(obj.method)

    def _collect_behavior(self, obj, data):
        data["_type"] = "behavior"
        data["node_uid"] = obj.node
        # captured_intents 协议：None 或 IbIntentContext（非可迭代）。
        # 完整序列化意图上下文（持久栈/涂抹/排他槽），反序列化时经
        # _get_intent_context 重建共享身份（契约：None 或 IbIntentContext uid）。
        ci = obj.captured_intents
        if ci is None:
            data["captured_intents"] = None
        elif isinstance(ci, IbIntentContext):
            data["captured_intents"] = self._collect_intent_context(ci)
        else:
            raise TypeError(
                "Unexpected captured_intents type "
                f"{type(ci).__name__} (contract requires None or IbIntentContext)"
            )
        # expected_type 在运行期由调用点经 node_to_type 侧表解析，字段本身仅元数据。
        et = obj.expected_type
        data["expected_type"] = str(et) if et is not None else None
        data["capture_mode"] = obj.capture_mode
        if obj.params_uids:
            data["params_uids"] = list(obj.params_uids)
        if obj.param_types:
            data["param_types"] = list(obj.param_types)
        if obj.return_type is not None:
            data["return_type"] = obj.return_type
        data["closure"] = self._serialize_closure(obj.closure, obj.capture_mode)

    def _collect_fn_callable(self, obj, data):
        data["_type"] = "fn_callable"
        data["node_uid"] = obj.node_uid
        data["capture_mode"] = obj.capture_mode
        if obj.params_uids:
            data["params_uids"] = list(obj.params_uids)
        if obj.body_uid:
            data["body_uid"] = obj.body_uid
        if obj.param_types:
            data["param_types"] = list(obj.param_types)
        if obj.return_type is not None:
            data["return_type"] = obj.return_type
        data["closure"] = self._serialize_closure(obj.closure, obj.capture_mode)

    def _collect_intent_context_wrapper(self, obj, data):
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

    def _collect_intent(self, obj, data):
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

    def _collect_object(self, obj, data):
        data["_type"] = "object"
        data["fields"] = {k: self._process_value(v) for k, v in obj.fields.items()}


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
        # 闭包 cell 待重链登记：[(闭包持有对象, sym_uid)]。作用域与实例全部
        # 恢复后经 ``_relink_cells`` 按 sym_uid 重链到恢复作用域树中的共享 cell。
        self._pending_cell_relinks: List[tuple] = []

    def deserialize_context(self, data: Dict[str, Any]) -> RuntimeContext:
        """从字典数据重建运行时上下文"""
        self._pending_cell_relinks = []
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

        # 闭包 cell 重链 post-pass：作用域树与全部可达实例恢复完成后执行。
        self._relink_cells()

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
            # Cell 变量（is_cell）经 promote_to_cell 语义重建 IbCell：cell 值
            # 来自符号当前值（序列化端以 cell 值为准），供闭包 post-pass 重链共享。
            if sym_data.get("is_cell"):
                scope.promote_to_cell(suid)

        return scope

    def _deserialize_closure(self, data: Dict[str, Any]) -> tuple:
        """从序列化闭包表重建 ``{sym_uid: (name, slot)}``，返回 (closure, pending_uids)。

        - ``value``（snapshot）：种子直接重建；调用路径每次再深克隆。
        - ``cell``（lambda）：先以携带值重建**自包含** IbCell（保证恢复即可用），
          同时登记待重链 sym_uid——post-pass 若在恢复的作用域树中找到该符号的
          共享 cell，则替换为共享 cell（保持外层赋值可见与多闭包共享同步）。
        """
        closure: Dict[str, Any] = {}
        pending_uids: List[str] = []
        for entry in data.get("closure") or []:
            sym_uid = entry["sym_uid"]
            name = entry.get("name", "")
            if entry.get("mode", "cell") == "value":
                closure[sym_uid] = (name, self._deserialize_value(entry.get("value")))
            else:
                val = self._deserialize_value(entry.get("value"))
                closure[sym_uid] = (name, IbCell(val) if val is not None else IbCell())
                pending_uids.append(sym_uid)
        return closure, pending_uids

    def _relink_cells(self) -> None:
        """闭包 cell 重链 post-pass：按 sym_uid 共享恢复作用域树中的 IbCell。

        修复档位 A 的两个退化：
        - 外层重赋值不可见：闭包自建 cell 与作用域符号 cell 分家；
        - 多闭包共享分叉：同一 sym_uid 的多个闭包各自持有独立 cell。
        仅当作用域树中存在持有该 sym_uid 的作用域时才重链；闭包捕获的 cell
        来自已退出作用域（不在恢复树中）时保留自包含 cell（公理 LT-2 语义）。
        """
        for obj, sym_uid in self._pending_cell_relinks:
            entry = obj.closure.get(sym_uid)
            if not isinstance(entry, tuple) or len(entry) != 2:
                continue
            name, slot = entry
            if not isinstance(slot, IbCell):
                continue
            owning = self._find_owning_scope(sym_uid)
            if owning is None:
                continue
            shared = owning.promote_to_cell(sym_uid)
            if shared is not None and shared is not slot:
                obj.closure[sym_uid] = (name, shared)

    def _find_owning_scope(self, sym_uid: str) -> Optional[Scope]:
        """在恢复的作用域树中查找持有 sym_uid 符号的作用域（不含父递归）。"""
        for scope in self.scope_cache.values():
            if sym_uid in scope.get_all_symbols_by_uid():
                return scope
        return None

    def _hydrate_specialized_class(self, cls_name: str):
        """按需水化特化类（list[int]）——反序列化 round-trip 用。

        从 metadata registry 解析特化 spec，沿基类名（``list``）create_subclass，
        特化类父链指向基类（方法继承 + is_assignable 继承链）。

        跨引擎 round-trip：目标引擎 spec_reg 可能无该特化（未编译），此时从
        序列化携带的 ``type_pool`` 重建 spec（经 ArtifactRehydrator 统一水化），
        再 create_subclass——特化身份跨引擎保真。
        """
        spec = None
        spec_reg = self.registry.get_metadata_registry() if hasattr(self.registry, "get_metadata_registry") else None
        if spec_reg is not None:
            spec = spec_reg.resolve(cls_name)
        if spec is None:
            spec = self._rehydrate_type_pool_spec(cls_name)
        if spec is None:
            return None
        base_name = spec.get_base_name()
        # [Module Identity] 基类按 module 感知查找（geo.Box[int] 的父 = "geo.Box"），
        # create_subclass 父名用 qualified——继承链对齐 qualified 键。
        if not base_name:
            return None
        parent_class = self.registry.get_class(base_name, module=spec.module_path)
        if parent_class is None:
            return None
        # [Module Identity] 父名 = 基类 qualified（geo.Box[int] 的父 = "geo.Box"），
        # 继承链对齐 qualified 键（内置/入口基类 qualified == 裸名，零影响）。
        parent_name = parent_class.qualified_name
        try:
            return self.registry.create_subclass(cls_name, spec, parent_name=parent_name)
        except Exception:
            return None

    def _rehydrate_type_pool_spec(self, cls_name: str):
        """从序列化 type_pool 重建特化 spec（跨引擎反序列化用）。

        ``self.type_pool``（``deserialize_context`` 已设）含编译产物全部类型；
        经 ArtifactRehydrator 按 UID 水化目标 spec。目标 spec 不在池中返回 None。
        [Module Identity] 按 (module_path, name) 联合匹配 qualified 类名
        （修 #2 按 name 匹配——跨引擎多模块同名特化不误选）。
        """
        type_pool = getattr(self, "type_pool", None)
        if not type_pool:
            return None
        spec_reg = self.registry.get_metadata_registry() if hasattr(self.registry, "get_metadata_registry") else None
        if spec_reg is None:
            return None

        def _qualified(data: Mapping[str, Any]) -> str:
            mp = data.get("module_path")
            nm = data.get("name")
            return f"{mp}.{nm}" if mp and nm else (nm or "")

        uid = next((u for u, d in type_pool.items() if _qualified(d) == cls_name), None)
        if uid is None:
            return None
        try:
            from core.runtime.loader.artifact_rehydrator import ArtifactRehydrator
            reh = ArtifactRehydrator(type_pool, spec_reg)
            return reh.hydrate(uid)
        except Exception:
            return None

    def _create_container_obj(self, ib_class, kind: str, seed):
        """按特化类构造容器值对象（round-trip 特化保真）。

        ``ib_class`` 为特化类（``list[int]``）时用其构造（type_ref 带实参）；
        基类/None 回落 ``factory.create_list/tuple/dict``（既有行为）。
        """
        if ib_class is not None and "[" in getattr(ib_class, "name", ""):
            from core.runtime.objects.primitives import IbList, IbTuple, IbDict
            if kind == "list":
                return IbList([], ib_class)
            if kind == "tuple":
                return IbTuple((), ib_class)
            if kind == "dict":
                return IbDict({}, ib_class)
        if self.factory is None:
            raise RuntimeError("RuntimeDeserializer: ObjectFactory is required.")
        if kind == "list":
            return self.factory.create_list([])
        if kind == "tuple":
            return self.factory.create_tuple(())
        if kind == "dict":
            return self.factory.create_dict({})
        raise RuntimeError(f"Unknown container kind: {kind}")

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
            # 为引用（仅当确实是本池中的引用 UID，避免用户数据撞前缀被误判）。
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
        if ib_class is None and cls_name and "[" in cls_name:
            # 特化类（list[int]）round-trip：运行时未注册时按需水化——
            # 从 metadata registry 解析特化 spec，沿基类（list）create_subclass。
            # 与 IbClass._specialize 机制同构（单一权威水化路径）。
            ib_class = self._hydrate_specialized_class(cls_name)
        
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
            obj = self._create_container_obj(ib_class, "list", [])
            self.instance_cache[uid] = obj 
            obj.elements = [self._deserialize_value(e) for e in data.get("elements", [])]

        elif _type == "tuple":
            # Cache an empty IbTuple first to break potential circular references,
            # then fill elements (mirroring the cache-before-recurse pattern used for IbList).
            obj = self._create_container_obj(ib_class, "tuple", ())
            self.instance_cache[uid] = obj
            obj.elements = tuple(self._deserialize_value(e) for e in data.get("elements", []))
            
        elif _type == "dict":
            # Cache an empty IbDict first to break potential circular references,
            # then fill fields (mirroring the cache-before-recurse pattern used for IbList/IbTuple).
            obj = self._create_container_obj(ib_class, "dict", {})
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
            ci_raw = data.get("captured_intents")
            if ci_raw is None:
                captured = None
            elif isinstance(ci_raw, str):
                captured = self._get_intent_context(ci_raw)
            else:
                raise TypeError(
                    "Unexpected captured_intents payload "
                    f"{type(ci_raw).__name__} (contract requires None or intent_context uid)"
                )
            closure, pending_uids = self._deserialize_closure(data)
            obj = self.factory.create_behavior(
                data["node_uid"], captured, data.get("expected_type"),
                capture_mode=data.get("capture_mode"),
                params_uids=data.get("params_uids"),
                closure=closure,
                param_types=data.get("param_types"),
                return_type=data.get("return_type"),
            )
            self.instance_cache[uid] = obj
            for suid in pending_uids:
                self._pending_cell_relinks.append((obj, suid))

        elif _type == "fn_callable":
            # 重建完整 fn_callable（node/closure/params/body 保真）并登记闭包
            # cell 重链——不得落入 else 展开为空 IbObject。
            closure, pending_uids = self._deserialize_closure(data)
            obj = self.factory.create_fn_callable(
                data["node_uid"],
                capture_mode=data.get("capture_mode", "lambda"),
                params_uids=data.get("params_uids"),
                body_uid=data.get("body_uid"),
                closure=closure,
                param_types=data.get("param_types"),
                return_type=data.get("return_type"),
            )
            self.instance_cache[uid] = obj
            for suid in pending_uids:
                self._pending_cell_relinks.append((obj, suid))

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
