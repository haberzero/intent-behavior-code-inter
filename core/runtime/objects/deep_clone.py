"""
core/runtime/objects/deep_clone.py

通用的 IbObject 深克隆辅助。

历史
----
原实现集中在 ``LLMExceptFrame._try_deep_clone``，仅服务于 llmexcept 快照。
随着 snapshot 语义被澄清为「定义时深克隆、调用时再克隆、全过程无状态可重入」，
snapshot 路径也需要同样的深克隆能力。把它抽到独立模块以避免循环依赖与重复实现。

语义约束
--------
* 不可变原语（None、int/float/str/bool）—— 直接复用引用（值语义等价）。
* 容器（list/tuple/dict）—— 递归深克隆元素；任意元素无法克隆即放弃整个容器，返回 None。
* 用户自定义 ``IbObject`` 实例 —— 递归克隆字段；无法克隆的字段被跳过（保留原引用）。
* 不可克隆类型（函数 / 行为 / 原生封装）—— 返回 None，由调用方决定回退策略。
* 通过 ``memo`` 字典处理环形引用。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core.runtime.objects.kernel import IbObject as KernelIbObject
from core.runtime.objects.kernel import IbValue, IbNone


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

    # 不可变原语：引用复用即可
    if isinstance(val, IbNone) or (
        isinstance(val, IbValue) and val.ib_class.name in ("int", "float", "str", "bool")
    ):
        return val

    # list / tuple：递归克隆 elements
    if isinstance(val, IbValue) and val.ib_class.name in ("list", "tuple"):
        new_elements: list = []
        placeholder = type(val)(new_elements, val.ib_class)
        memo[val_id] = placeholder
        for elem in val.elements:
            cloned_elem = try_deep_clone(elem, memo)
            if cloned_elem is None:
                return None
            new_elements.append(cloned_elem)
        if val.ib_class.name == "tuple":
            placeholder.elements = tuple(new_elements)
        return placeholder

    # dict：递归克隆所有键值对
    if isinstance(val, IbValue) and val.ib_class.name == "dict":
        new_fields: dict = {}
        placeholder_dict = type(val)(new_fields, val.ib_class)
        memo[val_id] = placeholder_dict
        for k, v in val.fields.items():
            cloned_v = try_deep_clone(v, memo)
            if cloned_v is None:
                return None
            new_fields[k] = cloned_v
        return placeholder_dict

    # ``IbIntentContext`` Python 值（``intent_context`` 实例的 ``_ctx`` 字段）：
    # 调用 ``fork()`` 得到值快照。PT-2.1：使 ``intent_context`` 作为类字段
    # 参与 llmexcept 快照/恢复时获得正确的"独立副本"语义——retry body 内对
    # ctx 的修改不会污染保存的快照。
    #
    # 用鸭子类型（``hasattr(val, "fork")`` + ``hasattr(val, "get_active_intents")``）
    # 而非 ``isinstance(IbIntentContext)`` 以避免循环依赖。
    if hasattr(val, "fork") and hasattr(val, "get_active_intents") and hasattr(val, "set_intent_top"):
        forked = val.fork()
        memo[val_id] = forked
        return forked

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
