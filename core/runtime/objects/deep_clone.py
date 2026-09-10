"""
core/runtime/objects/deep_clone.py

通用的 IbObject 深克隆辅助。

snapshot 路径也需要同样的深克隆能力，抽到独立模块以避免循环依赖与重复实现。

语义约束
--------
* 不可变原语（None、int/float/str/bool）—— 直接复用引用（值语义等价）。
* 容器（list/tuple/dict）—— 递归深克隆元素；任意元素无法克隆即放弃整个容器，返回 None。
* 用户自定义 ``IbObject`` 实例 —— 递归克隆字段；无法克隆的字段被跳过（保留原引用）。
* 不可克隆类型（函数 / 行为 / 原生封装）—— 返回 None，由调用方决定回退策略。
* 通过 ``memo`` 字典处理环形引用。
"""
from __future__ import annotations

import copy
from typing import Any, Dict, Optional

from core.base.enums import StorageModel
from core.runtime.objects.kernel import IbObject as KernelIbObject
from core.runtime.objects.kernel import IbValue, IbNone


def _clone_native_struct(struct: Any) -> Any:
    """全原生结构深拷贝（dict/list/str/int/float/bool/None——无 IbObject 成员）。

    knowledge KB 面（facts/vocab）的克隆通道：KB 面记录全为原生值（fact 字段
    字符串 + 事件链 + 词表记录），无嵌套 IbObject / 无环形引用——``copy.deepcopy``
    即正确且完整的克隆语义（防两个克隆共享结构被单方变异）。
    """
    return copy.deepcopy(struct) if struct is not None else struct


def _value_base_name(val: Any) -> str:
    """值对象 kind 基类名（特化类沿 spec 基名，普通类即自身名）。

    与 ``runtime_serializer._value_base_name`` / ``is_sequence_value`` 同构：
    内置泛型特化值（``list[int]``）的 ``ib_class.name`` 含方括号，容器/原语
    分派须按基类名判定。
    """
    ib_class = getattr(val, "ib_class", None)
    spec = getattr(ib_class, "spec", None)
    if spec is not None:
        base = spec.get_base_name()
        if base:
            return base
    name = getattr(ib_class, "name", "")
    return name


def try_deep_clone(
    val: Any,
    memo: Optional[Dict[int, Any]] = None,
) -> Optional[Any]:
    """
    尝试深克隆一个 IbObject 实例。

    见模块 docstring；返回 ``None`` 表示该值不可克隆，调用方需自行决定回退。
    """
    if memo is None:
        memo = {}

    val_id = id(val)
    if val_id in memo:
        return memo[val_id]

    # 按类型级 storage_model 分发：磁盘型对象走协议级浅拷贝，不物化字节。
    # 只处理 IbValue 实例；类元对象（IbClass）不是克隆目标。
    ib_class = getattr(val, "ib_class", None)
    spec = getattr(ib_class, "spec", None)
    if isinstance(val, IbValue) and spec is not None and getattr(spec, "storage_model", None) is StorageModel.DISK_BACKED:
        return val.receive("__clone_ref__", [])

    # 不可变原语：引用复用即可（vector = 不可变值类型：固定维度 + 无修改
    # 面，克隆语义 = 原对象本身，与 int/str 同纪律）
    if isinstance(val, IbNone) or (
        isinstance(val, IbValue) and _value_base_name(val) in ("int", "float", "str", "bool", "vector", "run_result", "quoted")
    ):
        # vector / run_result / quoted = 不可变值类型（固定面 + 无修改方法面），
        # 克隆语义 = 原对象本身（引用复用，与 int/str 同纪律）
        return val

    # list / tuple：递归克隆 elements
    if isinstance(val, IbValue) and _value_base_name(val) in ("list", "tuple"):
        new_elements: list = []
        placeholder = type(val)(new_elements, val.ib_class)
        memo[val_id] = placeholder
        for elem in val.elements:
            cloned_elem = try_deep_clone(elem, memo)
            if cloned_elem is None:
                return None
            new_elements.append(cloned_elem)
        if _value_base_name(val) == "tuple":
            placeholder.elements = tuple(new_elements)
        return placeholder

    # dict：递归克隆所有键值对
    if isinstance(val, IbValue) and _value_base_name(val) == "dict":
        new_fields: dict = {}
        placeholder_dict = type(val)(new_fields, val.ib_class)
        memo[val_id] = placeholder_dict
        for k, v in val.fields.items():
            cloned_v = try_deep_clone(v, memo)
            if cloned_v is None:
                return None
            new_fields[k] = cloned_v
        return placeholder_dict

    # knowledge：可变容器（引用语义）——条目快照递归深克隆（store 入时 +
    # get 出时双克隆纪律的克隆面）；验证谓词引用共享（函数非值快照——
    # 水化/克隆后 amend 边界 fail-fast，属已知边界）；facts/vocab 全原生
    # 结构深拷贝（KB 面独立——防两个克隆共享事实日志被单方变异）；索引
    # 派生面不跨克隆存活（构造入口从事实日志重建）
    if isinstance(val, IbValue) and _value_base_name(val) == "knowledge":
        new_entries: dict = {}
        placeholder_k = type(val)(val.ib_class, payload={
            "entries": new_entries,
            "seq": val.payload["seq"],
            "facts": _clone_native_struct(val.payload.get("facts", {})),
            "vocab": _clone_native_struct(val.payload.get("vocab") or {}),
        })
        memo[val_id] = placeholder_k
        for k, entry in val.payload["entries"].items():
            cloned_value = try_deep_clone(entry["value"], memo)
            if cloned_value is None:
                return None
            cloned_events = []
            for ev in entry["events"]:
                cloned_ev = try_deep_clone(ev["value"], memo)
                if cloned_ev is None:
                    return None
                cloned_events.append(
                    {"seq": ev["seq"], "kind": ev["kind"], "value": cloned_ev, "reason": ev["reason"]}
                )
            new_entries[k] = {
                "value": cloned_value,
                "check": entry.get("check"),
                "check_name": entry["check_name"],
                "provenance": entry.get("provenance", ""),
                "events": cloned_events,
            }
        return placeholder_k

    # Optional：专分支克隆，保留 ``_is_some`` 槽（通用 IbValue 分支不复制
    # slot，克隆产物 ``_is_some`` 未初始化——统一 Optional 值模型下，Optional
    # 参与 llmexcept 快照/深克隆时须保真 is_some/is_none 语义）。payload 递归
    # 深克隆（空值 payload 为 None 直接复用）。
    if isinstance(val, IbValue) and _value_base_name(val) == "Optional":
        payload = val.payload
        cloned_payload = try_deep_clone(payload, memo) if payload is not None else None
        from core.runtime.objects.primitives.optional import IbOptional

        new_opt = IbOptional(val.ib_class, cloned_payload, val._is_some)
        memo[val_id] = new_opt
        return new_opt

    # ``IbIntentContext`` Python 值（``intent_context`` 实例的 ``_ctx`` 字段）：
    # 调用 ``fork()`` 得到值快照。使 ``intent_context`` 作为类字段
    # 参与 llmexcept 快照/恢复时获得正确的"独立副本"语义--retry body 内对
    # ctx 的修改不会污染保存的快照。
    #
    # 惰性 import + isinstance 精确判别（base.py:176 先例）：函数内局部导入
    # 既避免顶层循环依赖，又比三方法鸭子类型（hasattr fork/get_active_intents/
    # set_intent_top）精确——任何恰好含这三方法的对象不再被误判为意图上下文。
    from core.runtime.objects.intent_context import IbIntentContext

    if isinstance(val, IbIntentContext):
        forked = val.fork()
        memo[val_id] = forked
        return forked

    # ``EnvironmentState`` Python 值（``environment`` 实例的 ``_environment``
    # 字段）：fork 深拷贝快照（frames + 值双向隔离）——一等环境对象作为类
    # 字段/容器值参与深克隆时获得独立副本语义。
    from core.runtime.objects.environment import EnvironmentState

    if isinstance(val, EnvironmentState):
        forked = val.fork()
        memo[val_id] = forked
        return forked

    # 内存型 ``IbValue`` 子类（如 media / file_handle）：克隆 payload 与字段。
    if isinstance(val, IbValue):
        new_val = type(val).__new__(type(val))
        new_val.ib_class = val.ib_class
        new_val.type_ref = val.type_ref
        new_val.meta = dict(val.meta)
        memo[val_id] = new_val
        new_val.fields = {}
        cloned_payload = try_deep_clone(val.payload, memo) if val.payload is not None else None
        new_val.payload = cloned_payload if cloned_payload is not None else val.payload
        for fname, fval in val.fields.items():
            cloned_fval = try_deep_clone(fval, memo)
            if cloned_fval is not None:
                new_val.fields[fname] = cloned_fval
        return new_val

    # 用户自定义 IbObject 实例（type 严格为 KernelIbObject，不含内置子类）
    if type(val) is KernelIbObject:
        new_obj = KernelIbObject.__new__(KernelIbObject)
        new_obj.ib_class = val.ib_class
        new_obj.fields = {}
        memo[val_id] = new_obj
        for fname, fval in val.fields.items():
            cloned_fval = try_deep_clone(fval, memo)
            if cloned_fval is not None:
                new_obj.fields[fname] = cloned_fval
            # 无法克隆的字段保留原值引用（恢复时按原引用使用）
        return new_obj

    # 函数 / 行为 / 原生对象等：不可克隆
    return None


__all__ = ["try_deep_clone"]
