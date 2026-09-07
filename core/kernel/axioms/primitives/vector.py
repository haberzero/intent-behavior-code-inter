"""
core/kernel/axioms/primitives/vector.py

VectorAxiom —— 词嵌入向量值类型的公理声明（类型名 / 方法面 / 能力）。

vector 是纯值类型（固定维度不可变、值语义、不可拆箱）：
- 方法面 = dim/dot/norm/cosine/scale/add/sub + 只读元素下标 + cast_to；
- 无运算符面（修改操作走方法，返回新 vector）；
- 无 LLM 文本解析面（向量经 embedding 服务产生，不经 LLM 输出解析）；
- 内存型存储模型（无 I/O 面）。
"""

from __future__ import annotations

from typing import Dict, Optional

from core.kernel.axioms.primitives.base import BaseAxiom, _m
from core.kernel.spec.type_ref import TypeRef


class VectorAxiom(BaseAxiom):
    has_subscript_cap = True
    has_converter_cap = True

    @property
    def name(self) -> str:
        return "vector"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "dim":      _m("dim",       ret="int"),
            "dot":      _m("dot",       params=["vector"], ret="float"),
            "norm":     _m("norm",      ret="float"),
            "cosine":   _m("cosine",    params=["vector"], ret="float"),
            "scale":    _m("scale",     params=["float"],  ret="vector"),
            "add":      _m("add",       params=["vector"], ret="vector"),
            "sub":      _m("sub",       params=["vector"], ret="vector"),
            "cast_to":  _m("cast_to",   params=["any"],    ret="any"),
            "__getitem__": _m("__getitem__", params=["int"], ret="float"),
            "__to_prompt__": _m("__to_prompt__", ret="str"),
        }

    def get_operators(self) -> Dict[str, str]:
        # 值语义相等/不等（逐元素精确相等）；无排序/算术运算符面
        # （修改操作走方法面，返回新 vector）
        return {"==": "__eq__", "!=": "__ne__"}

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        # 相等/不等跨类型合法（运行期返回 False/True，值语义 __eq__）；
        # 无排序/算术运算符面（修改操作走方法面，返回新 vector）。
        if op in ("==", "!="):
            return "bool"
        return None

    def resolve_item_type_name(self, key_type_name: str) -> Optional[str]:
        # 只读元素下标：v[0] → float
        if key_type_name == "int":
            return "float"
        return None

    def can_convert_from(self, source_type_name: str) -> bool:
        # 仅自身转换（list 不得隐式转 vector——显式 vec() 构造函数）
        return source_type_name == "vector"

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head == "vector"
