"""
core/kernel/axioms/primitives/quoted.py

QuotedAxiom —— quote/eval 数据侧值类型的公理声明（类型名 / 字段面 / 能力）。

quoted = 一等内核原生**不可变**值类型（``meta.quote`` 的返回值）：**被提及的
表达式**——经子引擎 compile-only 验证门冻结的自包含源串（数据/命令二元的
数据形态：可查询 / 可打印其自身 / 可精确对比）。

- 字段面 = 单字段 ``source: str``（``MemberSpec(kind="field")``，attribute
  访问 ``q.source``，run_result 三字段先例）；无运算符面（精确对比 = 调用方
  对 ``q.source`` 做 str ==——与 run_result 同纪律：判定门由调用方普通 IBCI
  代码表达）；无 call 能力（提及/使用的切换必经显式 ``meta.eval``——二元性
  的结构保证）。
- 值语义：不可变（无修改面）；按 source 值相等。
- 转换面：``can_convert_from`` 仅自身——**str→quoted 不成立**（源串必须经
  ``meta.quote`` 验证门成为良构值，无隐式转换通道）；``cast_to str`` =
  source 完整源串（数据面忠实呈现）。
- 命名与 ``behavior``/``fn_callable``（AST node uid 绑定的不可移植可调用）
  区分：quoted 是自包含数据值（可序列化/可跨引擎），非可调用——不同概念
  不同名。
"""

from __future__ import annotations

from typing import Dict, Optional

from core.kernel.axioms.primitives.base import BaseAxiom, _m
from core.kernel.spec.member import MemberSpec
from core.kernel.spec.type_ref import TypeRef


class QuotedAxiom(BaseAxiom):
    has_converter_cap = True

    @property
    def name(self) -> str:
        return "quoted"

    def get_method_specs(self) -> Dict[str, MemberSpec]:
        return {
            # 单字段（record 固定面）：source = 被提及表达式的完整源串
            "source": MemberSpec(name="source", kind="field", type_ref=TypeRef.of("str")),
            "cast_to":       _m("cast_to",       params=["any"], ret="any"),
            "__to_prompt__": _m("__to_prompt__", ret="str"),
        }

    def get_operators(self) -> Dict[str, str]:
        # 数据值面无运算符语义（精确对比 = 调用方对 source 做 str ==）
        return {}

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        return None

    def can_convert_from(self, source_type_name: str) -> bool:
        # 仅自身：str→quoted 必须经 meta.quote 验证门（无隐式转换面）
        return source_type_name == "quoted"

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head == "quoted"
