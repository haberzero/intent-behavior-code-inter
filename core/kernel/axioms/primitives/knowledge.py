"""
core/kernel/axioms/primitives/knowledge.py

KnowledgeAxiom —— 已验证知识注册表类型的公理声明。

knowledge = 一等内置值类型（语言自动机的知识层/D 纸带）：
- 容器约定与 dict 同构（keys/len）+ 铁律额外项（store/get/amend/history）；
- 无运算符面（知识操作 = 显式方法调用，无算术/比较语义）；
- 值语义要点：知识库可变（引用语义容器），条目值冻结（深克隆快照）。
"""

from __future__ import annotations

from typing import Dict, Optional

from core.kernel.axioms.primitives.base import BaseAxiom, _m
from core.kernel.spec.member import MethodMemberSpec
from core.kernel.spec.type_ref import TypeRef


class KnowledgeAxiom(BaseAxiom):
    has_converter_cap = True

    @property
    def name(self) -> str:
        return "knowledge"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            # store 第 4 参 provenance（来源标记，可选）/ history 第 2 参 kind
            # （事件类型过滤，可选）——内建方法声明最大参数列、运行期接受更少、
            # 编译期绑定非严格（str.find from_idx 先例）。
            "store":    _m("store",    params=["str", "any", "any", "str"], ret="void"),
            "get":      _m("get",      params=["str"], ret="any"),
            "amend":    _m("amend",    params=["str", "any", "str"], ret="void", mutating=True),
            "history":  _m("history",  params=["str", "str"], ret="list"),
            "export":   _m("export",   ret="dict"),
            "keys":     _m("keys",     ret="list"),
            "len":      _m("len",      ret="int"),
            "cast_to":  _m("cast_to",  params=["any"], ret="any"),
            # ---- 词表面（治理 allowlist——KB 元规则；全确定性零 LLM）----
            # register_word 后两参（members/entries）可选，同 store 先例。
            "register_word":    _m("register_word",    params=["str", "str", "bool", "list", "dict"], ret="void", mutating=True),
            "register_relation": _m("register_relation", params=["str", "str", "bool", "bool"], ret="void", mutating=True),
            "register_world":   _m("register_world",   params=["str", "str", "int"], ret="void", mutating=True),
            # word/relation/world 未注册 = null 合法态 → ret any（同 get 先例）
            "word":             _m("word",             params=["str"], ret="any"),
            "relation":         _m("relation",         params=["str"], ret="any"),
            "world":            _m("world",            params=["str"], ret="any"),
            "words":            _m("words",            ret="list"),
            "relations":        _m("relations",        ret="list"),
            "worlds":           _m("worlds",           ret="list"),
            # ---- 事实面（append-only 事实日志——KB 单一权威源；内建治理门）----
            # add_fact 后两参（source/status）可选，同 store 先例。
            "add_fact":   _m("add_fact",   params=["str", "str", "str", "str", "str", "str"], ret="str", mutating=True),
            # get_fact 未知 id = null 合法态 → ret any（同 get 先例）
            "get_fact":   _m("get_fact",   params=["str"], ret="any"),
            "facts":      _m("facts",      ret="list"),
            "fact_len":   _m("fact_len",   ret="int"),
            # ---- 查找面（图平面 active 视图，全确定性零 LLM）----
            "lookup_pair":  _m("lookup_pair",  params=["str", "str"], ret="list"),
            "exists":       _m("exists",       params=["str", "str", "str", "str"], ret="bool"),
            "all_in_world": _m("all_in_world", params=["str"], ret="list"),
            "by_source":    _m("by_source",    params=["str"], ret="list"),
            "by_subject":   _m("by_subject",   params=["str"], ret="list"),
            "contradicts":  _m("contradicts",  params=["str", "str", "str"], ret="bool"),
            "transitive":   _m("transitive",   params=["str", "str"], ret="list"),
            # ---- 对比/展开面（5 层对比的确定性 4 层 + 按需确定性展开）----
            "expand":       _m("expand",       params=["str"], ret="dict"),
            "same_word":    _m("same_word",    params=["str", "str"], ret="bool"),
            "compare":      _m("compare",      params=["str", "str"], ret="dict"),
            # ---- 审计面（墓碑/版本化——append-only 纪律 + reason 强制）----
            "retract":      _m("retract",      params=["str", "str"], ret="void", mutating=True),
            "amend_fact":   _m("amend_fact",   params=["str", "str", "str"], ret="void", mutating=True),
            "source":       _m("source",       params=["str"], ret="str"),
            "history_fact": _m("history_fact", params=["str"], ret="list"),
            # ---- 向量面（词嵌入——内容信号非判定；D1 判定走图平面）----
            "set_embedding":  _m("set_embedding",  params=["str", "vector"], ret="void", mutating=True),
            "embedding":      _m("embedding",      params=["str"], ret="vector"),
            "has_embedding":  _m("has_embedding",  params=["str"], ret="bool"),
            "embedding_dim":  _m("embedding_dim",  ret="int"),
            "embed_search":   _m("embed_search",   params=["vector", "int"], ret="list"),
        }

    def get_operators(self) -> Dict[str, str]:
        return {}

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        # 知识面无运算符语义（操作 = 显式方法调用）
        return None

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name in ("knowledge", "str")

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head == "knowledge"
