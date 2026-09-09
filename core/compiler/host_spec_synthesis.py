"""
core/compiler/host_spec_synthesis.py — 宿主绑定声明 → 成员 spec 合成（单一权威源）。

``import python "pkg" as lib: bind ...`` 声明 → IBCI 成员 spec 表
（MethodMemberSpec / MemberSpec）：用户侧编译路径（Scheduler 宿主 import 注入）
与内核 bootstrap 契约路径共用本合成逻辑（同源同构，不各写一套）；``bind class``
嵌套成员与模块成员同构，复用同一函数。

**成员合成规则**（确定性，声明驱动）：
- 方法成员（``bind f(params) -> ret``）：MethodMemberSpec——param_types = 逐参数
  注解（annotation_to_typeref 单一权威转换）；return_type = 返回注解（无返回注解 =
  void）；param_descriptors 与 param_types 同源同步（POSITIONAL_OR_KEYWORD）。
- 属性成员（``bind x -> type``）：MemberSpec（kind=field）——type_ref = 返回位注解
  （无注解 = any）。
- 重复 bind 同名成员：不入表，返回结构化校验错误（调用方经自身诊断通道上报——
  定位与消息属调用方语境）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from core.kernel.spec import (
    MemberSpec,
    MethodMemberSpec,
    ParamDescriptor,
    TypeRef,
)
from .semantic.passes._annotation_utils import annotation_to_typeref


@dataclass
class HostBindingDuplicate:
    """重复 bind 同名成员的结构化校验错误（调用方携定位上报）。"""

    member_name: str
    binding: Any


def synthesize_host_members(bindings: List[Any]) -> Tuple[Dict[str, Any], List[HostBindingDuplicate]]:
    """bind 声明 → 成员 spec 表。

    参数 ``bindings``：IbHostBinding 序列（成员声明；is_class 条目由调用方过滤）。
    返回 ``(members, duplicates)``：members = 声明名 → MemberSpec / MethodMemberSpec
    （首个声明入表）；duplicates = 未入表的同名条目（声明序）。
    """
    members: Dict[str, Any] = {}
    duplicates: List[HostBindingDuplicate] = []
    for m in bindings:
        if m.name in members:
            duplicates.append(HostBindingDuplicate(member_name=m.name, binding=m))
            continue
        if m.is_method:
            param_refs = [
                annotation_to_typeref(p.annotation)
                for p in m.params
            ]
            return_ref = (
                annotation_to_typeref(m.return_type)
                if m.return_type is not None else TypeRef.of("void")
            )
            # 描述符 type_ref 与 param_types 同源同步（避免读 descriptor.type_ref
            # 的消费方被静默降级 any）。
            descriptors = [
                ParamDescriptor(name=p.name, kind="POSITIONAL_OR_KEYWORD", type_ref=pref)
                for p, pref in zip(m.params, param_refs)
            ]
            members[m.name] = MethodMemberSpec(
                name=m.name,
                kind="method",
                param_types=param_refs,
                return_type=return_ref,
                param_descriptors=descriptors,
            )
        else:
            members[m.name] = MemberSpec(
                name=m.name,
                kind="field",
                type_ref=(
                    annotation_to_typeref(m.return_type)
                    if m.return_type is not None else TypeRef.of("any")
                ),
            )
    return members, duplicates
