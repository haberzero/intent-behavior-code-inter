"""
core/kernel/axioms/primitives/narrow_model.py

NarrowModelAxiom —— 推理时窄模型值类型的公理声明（类型名 / 方法面 / 能力）。

``narrow_model`` = 一等内核原生**不可变**值类型（``world_model.bind_artifact``
的返回值）：**冻结的 KG 嵌入向量空间模型**（试用方侧离线训练成工件，IBCI
推理时加载）——纯推理、零训练。主架构 TransE（``f(s,r,o)=‖e_s + r_r − e_o‖``，
距离越小越优）。

- 方法面：``score``/``topk``（推理面，内容信号非判定——D1：判定走确定性路径）
  + 元数据查询面（name/dim/entities/relations/architecture/content_hash）。
- 无字段 attribute 面（嵌入/词表 = 工件内部结构，经方法面查询；不作字段
  attribute——与 knowledge 的 facts/vocab 内部结构同纪律）。
- 无运算符面（内容信号对比 = 调用方对 score 值做普通比较）。
- 转换面：``can_convert_from`` 仅自身——**无隐式构造通道**（模型必经
  ``world_model.bind_artifact`` 加载门，同 quoted 仅经 meta.quote 产出）。
"""

from __future__ import annotations

from typing import Dict, Optional

from core.kernel.axioms.primitives.base import BaseAxiom, _m
from core.kernel.spec.type_ref import TypeRef


class NarrowModelAxiom(BaseAxiom):
    has_converter_cap = True

    @property
    def name(self) -> str:
        return "narrow_model"

    def get_method_specs(self) -> Dict[str, "MemberSpec"]:
        return {
            # 推理面（TransE 纯算术；内容信号，非判定）
            "score":   _m("score",   params=["str", "str", "str"], ret="float"),
            "topk":    _m("topk",    params=["str", "str", "int"], ret="list"),
            # 元数据查询面
            "name":            _m("name",            ret="str"),
            "dim":             _m("dim",             ret="int"),
            "entities":        _m("entities",        ret="list"),
            "relations":       _m("relations",       ret="list"),
            "architecture":    _m("architecture",    ret="str"),
            "content_hash":    _m("content_hash",    ret="str"),
            # 转换/提示词
            "cast_to":         _m("cast_to",         params=["any"], ret="any"),
            "__to_prompt__":   _m("__to_prompt__",   ret="str"),
        }

    def get_operators(self) -> Dict[str, str]:
        # 内容信号面无运算符语义（score 值对比 = 调用方对 float 做普通比较）
        return {}

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        return None

    def can_convert_from(self, source_type_name: str) -> bool:
        # 仅自身：模型必经 world_model.bind_artifact 加载门（无隐式构造通道）
        return source_type_name == "narrow_model"

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head == "narrow_model"
