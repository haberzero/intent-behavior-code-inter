"""
core/kernel/spec/type_ref.py

TypeRef — 类型系统的"地址"层。

TypeRef 是纯不可变值，代表对一个类型的引用。它只持有类型的"地址"
（名字 + 泛型实参 + 模块限定），不包含任何成员信息或运行逻辑。

设计原则（来自 IBCI_TYPE_SYSTEM_FROM_ZERO_ARCHITECTURE.md §1.1）：
  - 可哈希：能作为 dict key、放入 set
  - 递归结构化：list[dict[str,int]] 直接通过 args 表达，不靠字符串拼接
  - 不依赖注册表：构造 TypeRef 无需任何全局状态
  - 可序列化：纯数据，无函数引用

[INFO] 兼容策略：
  - TypeRef 与现有 IbSpec 体系并存，不替换
  - from_name() / from_spec() 提供从旧表示到 TypeRef 的桥接
  - IbSpec / MemberSpec 上的 .type_ref 属性通过本模块构造 TypeRef
  - SpecRegistry.resolve_typeref() 接受 TypeRef 并委托现有 resolve() 逻辑
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .base import IbSpec


# ------------------------------------------------------------------ #
# TypeRef                                                              #
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class TypeRef:
    """
    不可变、可哈希的类型引用。

    字段
    ----
    head    : 基础类型名，例如 "int"、"list"、"MyClass"
    args    : 泛型实参元组，空元组表示非泛型类型
    module  : 跨模块限定符（模块路径），None 表示内置或当前模块

    派生属性（非字段，通过 property 计算）
    ----------------------------------------
    canonical_name  : 标准化名称字符串，例如 "list[dict[str,int]]"
    qualified_name  : 含模块前缀的完整名称，例如 "mymod.MyClass"

    示例
    ----
    int              → TypeRef("int")
    list[int]        → TypeRef("list", (TypeRef("int"),))
    dict[str,int]    → TypeRef("dict", (TypeRef("str"), TypeRef("int")))
    mymod.Foo        → TypeRef("Foo", (), module="mymod")
    """

    head: str
    args: Tuple["TypeRef", ...] = field(default_factory=tuple)
    module: Optional[str] = None

    # -------------------------------------------------------------- #
    # Derived properties                                               #
    # -------------------------------------------------------------- #

    @property
    def canonical_name(self) -> str:
        """标准化类型名（不含模块前缀）。"""
        if self.args:
            inner = ",".join(a.canonical_name for a in self.args)
            return f"{self.head}[{inner}]"
        return self.head

    @property
    def qualified_name(self) -> str:
        """含模块前缀的完整类型名。"""
        cn = self.canonical_name
        if self.module:
            return f"{self.module}.{cn}"
        return cn

    # -------------------------------------------------------------- #
    # Factory helpers                                                  #
    # -------------------------------------------------------------- #

    @classmethod
    def of(cls, name: str, module: Optional[str] = None) -> "TypeRef":
        """
        从纯名字字符串构造非泛型 TypeRef。

        用于从旧的 name/module 字符串对桥接到 TypeRef。
        """
        return cls(head=name, args=(), module=module)

    @classmethod
    def generic(
        cls,
        head: str,
        *args: "TypeRef",
        module: Optional[str] = None,
    ) -> "TypeRef":
        """
        构造泛型 TypeRef，例如 TypeRef.generic("list", TypeRef.of("int"))。
        """
        return cls(head=head, args=args, module=module)

    @classmethod
    def from_spec(cls, spec: "IbSpec") -> "TypeRef":
        """
        桥接方法：从现有 IbSpec 构造对应的 TypeRef。

        [INFO] 兼容层：利用各子类上的类型名字段构造结构化 TypeRef。
        不导入 IbSpec 子类（避免循环），通过 get_base_name() 和
        hasattr 检测字段。
        """
        base = spec.get_base_name()

        # ListSpec: element_type_name
        if base == "list" and hasattr(spec, "element_type_name"):
            elem_name: str = getattr(spec, "element_type_name", "any")
            elem_mod: Optional[str] = getattr(spec, "element_type_module", None)
            if elem_name != "any":
                return cls(
                    head="list",
                    args=(cls.of(elem_name, elem_mod),),
                    module=spec.module_path,
                )
            return cls(head="list", args=(), module=spec.module_path)

        # TupleSpec: element_type_name
        if base == "tuple" and hasattr(spec, "element_type_name"):
            elem_name = getattr(spec, "element_type_name", "any")
            elem_mod = getattr(spec, "element_type_module", None)
            if elem_name != "any":
                return cls(
                    head="tuple",
                    args=(cls.of(elem_name, elem_mod),),
                    module=spec.module_path,
                )
            return cls(head="tuple", args=(), module=spec.module_path)

        # DictSpec: key_type_name + value_type_name
        if base == "dict" and hasattr(spec, "key_type_name"):
            key_name: str = getattr(spec, "key_type_name", "any")
            key_mod: Optional[str] = getattr(spec, "key_type_module", None)
            val_name: str = getattr(spec, "value_type_name", "any")
            val_mod: Optional[str] = getattr(spec, "value_type_module", None)
            return cls(
                head="dict",
                args=(cls.of(key_name, key_mod), cls.of(val_name, val_mod)),
                module=spec.module_path,
            )

        # DeferredSpec / BehaviorSpec: value_type_name
        if base in ("deferred", "behavior") and hasattr(spec, "value_type_name"):
            val_name = getattr(spec, "value_type_name", "auto")
            val_mod = getattr(spec, "value_type_module", None)
            if val_name not in ("auto", "any", None, ""):
                return cls(
                    head=base,
                    args=(cls.of(val_name, val_mod),),
                    module=spec.module_path,
                )
            return cls(head=base, args=(), module=spec.module_path)

        # OptionalSpec: wrapped_type_name
        if base == "Optional" and hasattr(spec, "wrapped_type_name"):
            wrapped_name = getattr(spec, "wrapped_type_name", "any")
            wrapped_mod = getattr(spec, "wrapped_type_module", None)
            return cls(
                head="Optional",
                args=(cls.of(wrapped_name, wrapped_mod),),
                module=spec.module_path,
            )

        # Default: 使用 spec.name（包含已编码的类型名，如 "list[int]"）
        # 但 head 应该是干净的基础名，对于已编码的泛型名字使用 base
        return cls(head=spec.name, args=(), module=spec.module_path)

    # -------------------------------------------------------------- #
    # Substitution (for generic instantiation)                         #
    # -------------------------------------------------------------- #

    def substitute(self, mapping: dict) -> "TypeRef":
        """
        递归替换类型形参。

        mapping 是 {形参名: TypeRef} 的字典，例如 {"T": TypeRef.of("int")}。
        用于泛型特化：list[T].__getitem__ → TypeRef("T").substitute({"T": int_ref}) → TypeRef("int")

        返回新 TypeRef（不可变，原值不变）。
        """
        # 直接命中：当前 head 是一个形参名
        if not self.args and self.head in mapping:
            return mapping[self.head]
        # 无泛型实参且不是形参：原样返回
        if not self.args:
            return self
        # 递归替换 args
        new_args = tuple(a.substitute(mapping) for a in self.args)
        if new_args == self.args:
            return self
        return TypeRef(head=self.head, args=new_args, module=self.module)

    # -------------------------------------------------------------- #
    # Helpers                                                          #
    # -------------------------------------------------------------- #

    def is_generic(self) -> bool:
        """True if this TypeRef has type arguments (is a generic instantiation)."""
        return bool(self.args)

    def is_builtin(self) -> bool:
        """True if this TypeRef has no module qualifier (built-in or current module)."""
        return self.module is None

    def with_module(self, module: Optional[str]) -> "TypeRef":
        """Return a copy with a different module qualifier."""
        if module == self.module:
            return self
        return TypeRef(head=self.head, args=self.args, module=module)

    # -------------------------------------------------------------- #
    # String representation                                            #
    # -------------------------------------------------------------- #

    def __str__(self) -> str:
        return self.qualified_name

    def __repr__(self) -> str:
        parts = [repr(self.head)]
        if self.args:
            parts.append(f"({', '.join(repr(a) for a in self.args)},)")
        if self.module is not None:
            parts.append(f"module={self.module!r}")
        return f"TypeRef({', '.join(parts)})"
