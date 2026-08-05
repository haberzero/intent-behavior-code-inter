"""
core/kernel/axioms/intent.py

IntentAxiom: 将 IbIntent 对象本身的行为约束纳入公理体系。

IbIntent 是 IbObject 的子类。本公理为类型系统提供 Intent 对象的属性
访问静态约束，并为运行时 vtable 提供形式化的方法声明。

设计：
- is_class() = True  — Intent 是类类型（有实例），不是原始值类型
- 无任何 capability —— Intent 对象不可调用、不可迭代、不可下标、不可运算
- get_method_specs() — 暴露 Intent 的公共读取接口
- is_compatible("Intent") → True

方法槽位：
  get_content() → str   返回意图内容字符串
  get_tag()     → str   返回意图标签（无标签时返回空字符串）
  get_mode()    → str   返回意图模式字符串 ("+", "!", "-")
"""
from __future__ import annotations

from core.kernel.axioms.primitives.base import BaseAxiom, _m


class IntentAxiom(BaseAxiom):
    """
    公理：Intent 类型（运行时意图对象）。

    * is_class() = True
    * 无任何 capability
    * is_compatible 仅接受 "Intent" 自身
    * get_parent_axiom_name() = "Object"
    """

    @property
    def name(self) -> str:
        return "Intent"

    def get_method_specs(self):
        return {
            "get_content": _m("get_content", ret="str"),
            "get_tag":     _m("get_tag",     ret="str"),
            "get_mode":    _m("get_mode",    ret="str"),
        }

    def is_class(self) -> bool:
        return True
