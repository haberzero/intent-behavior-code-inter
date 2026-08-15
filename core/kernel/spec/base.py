"""
core/kernel/spec/base.py

IbSpec — the zero-dependency, pure-data foundation of the IBCI type system.

Design principles:
  • No _registry, no _axiom, no runtime state of any kind.
  • Every IbSpec is a plain value record: identity lives in (module_path, name).
  • Capability queries (callable? iterable? which operator result?) go through
    SpecRegistry, which delegates to AxiomRegistry.  Specs themselves are mute.
  • The symbol ↔ type circular dependency is broken by storing member info as
    MemberSpec (pure strings), not as Symbol objects.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar, Dict, List, Optional, TYPE_CHECKING

from core.base.enums import Provenance, StorageModel, Visibility

from .type_ref import TypeRef as _TypeRef

if TYPE_CHECKING:
    from .member import MemberSpec, ParamDescriptor
    from .type_ref import TypeRef


# Sentinel TypeRef used as a default placeholder for optional type fields
# that have not been explicitly set.
# "any" is the universal top type used when no specific type constraint is declared.
_ANY_REF = _TypeRef.of("any")


def _typeref_has_any_arg(ref) -> bool:
    """TypeRef 或其泛型实参中是否含 ``any``（head=="any" 或递归嵌套）。

    结构化逐实参判定，避免 name 字符串子串误命中（``Company`` 等类型名含
    "any" 子串的假阳性——`spec_has_any_generic_arg` 的 P1 整改）。
    """
    if ref is None:
        return False
    if getattr(ref, "head", None) == "any":
        return True
    if not getattr(ref, "args", None):
        return False
    return any(_typeref_has_any_arg(a) for a in ref.args)


def spec_has_any_generic_arg(spec: Optional["IbSpec"]) -> bool:
    """spec 的泛型实参中是否含 ``any``（T 降级占位或显式 any 通配）。

    模板上下文中类型参数占位经解析可能降级为 ``Box[any]``（T→any），与保留的
    ``Box[T]`` 不对称；``any`` 是动态通配，无法静态拒绝——含 any 的实参比较应
    延后（CALLABLE_SIG 签名模型根治：不误拒模板字段/参数赋值）。

    按 spec 的结构化泛型承载字段（type_args / element_type / key+value /
    positional / value_type / wrapped_type）逐实参判定，不依赖 name 子串。
    """
    if spec is None:
        return False
    kind = getattr(spec, "kind", None)
    args = []
    if kind == TypeKind.LIST.value:
        args = [getattr(spec, "element_type", None)]
    elif kind == TypeKind.DICT.value:
        args = [getattr(spec, "key_type", None), getattr(spec, "value_type", None)]
    elif kind == TypeKind.TUPLE.value:
        positional = getattr(spec, "positional_element_types", None) or []
        args = list(positional) if positional else [getattr(spec, "element_type", None)]
    elif kind == TypeKind.CLASS.value:
        args = list(getattr(spec, "type_args", None) or [])
    elif kind in (
        TypeKind.THREAD.value, TypeKind.THREAD_RESULT.value, TypeKind.CHANNEL.value,
        TypeKind.SLOT.value, TypeKind.GENERATOR.value, TypeKind.CALLABLE_INSTANCE.value,
        TypeKind.OPTIONAL.value,
    ):
        args = [getattr(spec, "value_type", None), getattr(spec, "wrapped_type", None)]
    # PRIMITIVE/FUNCTION/BOUND_METHOD/MODULE/TYPE_PARAM 等无泛型实参 → False
    return any(_typeref_has_any_arg(a) for a in args if a is not None)


class TypeKind(str, Enum):
    PRIMITIVE = "primitive"
    FUNCTION = "function"
    CLASS = "class"
    PROTOCOL = "protocol"
    LIST = "list"
    TUPLE = "tuple"
    DICT = "dict"
    OPTIONAL = "optional"
    BOUND_METHOD = "bound_method"
    MODULE = "module"
    # CALLABLE_INSTANCE unifies the former FN_CALLABLE + BEHAVIOR kinds.
    # A callable instance is a typed value created by `lambda`/`snapshot` (fn_callable
    # expression) or by `@~...~` (LLM behavior).  At the TYPE level both share the
    # same kind; the runtime dispatch differentiation (regular AST re-evaluation
    # vs LLM invocation) is encoded by the spec's ``name``/``_axiom_name``
    # ("fn_callable" vs "behavior") and by the runtime value's payload.
    # The capture mode (lambda vs snapshot) is a property of the VALUE
    # (``IbFnCallable.capture_mode`` / ``IbBehavior.capture_mode``) and of the
    # creating AST node (``IbLambdaExpr.capture_mode``); it is NOT a property of
    # the type.
    CALLABLE_INSTANCE = "callable_instance"
    CALLABLE_SIG = "callable_sig"
    LAZY = "lazy"
    # 并发/通信类型（task/signal 类型已删除）
    THREAD = "thread"       # 线程句柄（thread[T]，join 返回 thread_result）
    CHANNEL = "channel"     # 数据流通道（元素类型泛型）
    SLOT = "slot"           # 共享状态槽（值类型泛型）
    SUBSCRIBER = "subscriber"  # pubsub 订阅者消费者端点
    THREAD_RESULT = "thread_result"  # 线程结果容器（值类型泛型，thread_result[T]）
    GENERATOR = "generator"  # 惰性生成器（含 yield 函数调用产出，元素类型泛型 generator[T]）
    TYPE_PARAM = "type_param"  # 用户类泛型类型参数占位（class Box[T] 的 T，非实体类型）


@dataclass(eq=False)
class IbSpec:
    """
    Pure-data description of an IBCI type.

    This is the single source of truth for type identity during both
    compile time and run time.  It intentionally carries no behaviour —
    all capability queries are answered by SpecRegistry (which consults
    AxiomRegistry).

    Naming conventions
    ------------------
    name          : simple (unqualified) name, e.g. ``"int"``, ``"MyClass"``
    module_path   : dotted module qualifier, e.g. ``"my_module"`` or None
    qualified_name: ``f"{module_path}.{name}"`` when module_path is set

    Axiom override
    --------------
    ``_axiom_name`` lets special types (e.g. user-defined Enum subclasses)
    redirect axiom lookups to a different axiom key.  Normally this is None
    and axiom lookups use ``name``.
    """

    name: str = ""
    module_path: Optional[str] = None
    kind: str = TypeKind.PRIMITIVE.value
    provenance: Provenance = Provenance.USER_DEFINED
    visibility: Visibility = Visibility.IMPORT_GATED
    storage_model: StorageModel = StorageModel.MEMORY_BACKED

    # Members are MemberSpec objects (pure data, no Symbol references).
    # Populated by the compiler's collector/resolver passes and by axiom
    # method declarations during SpecRegistry bootstrap.
    members: Dict[str, "MemberSpec"] = field(default_factory=dict)

    # Optional override: the axiom key used for capability lookups.
    # Leave as None to use ``name``.
    _axiom_name: Optional[str] = field(default=None, repr=False, compare=False)

    # ------------------------------------------------------------------ #
    # Identity helpers                                                     #
    # ------------------------------------------------------------------ #

    @property
    def qualified_name(self) -> str:
        """Fully qualified name including module prefix (if any)."""
        if self.module_path:
            return f"{self.module_path}.{self.name}"
        return self.name

    def get_base_name(self) -> str:
        """
        The key used when looking up this spec's axiom in AxiomRegistry.
        Normally equals ``name``; overridable via ``_axiom_name``.
        """
        return self._axiom_name or self.name

    def get_references(self) -> dict:
        """
        Return a dict of cross-reference fields that point to other IbSpec
        objects (or lists of them).  Used by the serializer to walk the type
        graph without hard-coding isinstance checks.

        The default implementation returns an empty dict (no sub-spec refs).
        Subclasses that actually hold IbSpec references should override this.
        Since all concrete specs store type information as name-strings rather
        than live IbSpec objects, the base default is sufficient for most cases.
        """
        return {}

    def is_class(self) -> bool:
        """Return True if this spec describes a class type."""
        return self.kind == TypeKind.CLASS.value

    def is_kind(self, *kinds: str) -> bool:
        """Return True if spec.kind matches one of provided kinds."""
        return self.kind in kinds

    @property
    def is_disk_backed(self) -> bool:
        """Return True if this type uses the disk-backed storage model."""
        return self.storage_model is StorageModel.DISK_BACKED

    # ------------------------------------------------------------------ #
    # Cloning                                                              #
    # ------------------------------------------------------------------ #

    def clone(self) -> "IbSpec":
        """
        Shallow-copy this spec with an independent members dict.
        Since MemberSpec objects are themselves pure data, a shallow copy
        of the members dict is sufficient for isolation.
        """
        cloned = copy.copy(self)
        cloned.members = dict(self.members)
        return cloned

    # ------------------------------------------------------------------ #
    # Repr / str                                                           #
    # ------------------------------------------------------------------ #

    def __str__(self) -> str:
        return self.qualified_name

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


@dataclass(eq=False)
class TypeDef(IbSpec):
    """
    Unified type-definition data model.

    All former concrete *Spec subclasses (function / class / list / dict / tuple
    / optional / bound_method / module / callable_instance / callable_sig /
    lazy) are now folded into this single class — dispatch on the ``kind``
    field rather than ``isinstance``.

    Storage model
    -------------
    Type-reference fields are stored as :class:`TypeRef` (frozen, hashable,
    structurally recursive).  All access goes through the TypeRef API
    (``spec.return_type.head``, ``[t.head for t in spec.param_types]``, …);
    there are no flat-string accessors.
    """

    # -- Function-like signature (FUNCTION + BOUND_METHOD + CALLABLE_INSTANCE
    #    + CALLABLE_SIG kinds use these). ---------------------------------
    param_types: List["TypeRef"] = field(default_factory=list)
    return_type: "TypeRef" = field(default_factory=lambda: _ANY_REF.replace_head("void"))

    # 函数参数描述符（FUNCTION kind，用户函数 / LLM 函数）。
    # 与 ``param_types`` 并列：前者只存类型，后者携带名称/种类/默认值存在性，
    # 供语义层实参解析（位置 → 具名 → 默认填充 → varargs）与 vtable 声明复用。
    param_descriptors: List["ParamDescriptor"] = field(default_factory=list)

    # -- Class inheritance (CLASS kind) -----------------------------------
    parent_type: Optional["TypeRef"] = None

    # -- 用户类泛型类型参数（CLASS kind）-------------------------------
    # ``class Box[T]`` 的 ["T"]。特化 spec（如 "Box[int]"）type_params 置空。
    type_params: List[str] = field(default_factory=list)

    # -- 用户类泛型类型参数约束（CLASS kind）-------------------------
    # ``class Box[T: Greeter]`` 的 {"T": "Greeter"}。特化时要求实参满足
    # 对应协议，否则编译期拒绝。
    type_param_bounds: Dict[str, str] = field(default_factory=dict)

    # -- 用户类实现的协议（CLASS kind）-------------------------------
    # ``class Foo implements Bar`` 的 ["Bar"]。编译期用于协议满足校验；
    # 运行期目前不改变分派，但保留在类型描述中供序列化和未来动态分派使用。
    implements: List[str] = field(default_factory=list)

    # -- 用户类实现协议时的类型实参（CLASS kind）-----------------------
    # ``class Foo implements Container[int]`` 的 {"Container": ["int"]}。
    implements_args: Dict[str, List[str]] = field(default_factory=dict)

    # -- 用户类泛型特化实参（CLASS kind 特化 spec）---------------------
    # ``Box[int]`` 特化 spec 的实参 TypeRef 列表（["int"]），供结构化构造
    # （TypeRef.from_spec）与序列化 round-trip 保真。基类（模板）为空。
    type_args: List["TypeRef"] = field(default_factory=list)

    # 特化 spec 的原始基类名（"Box"）——name 为 "Box[int]"（含实参），
    # base_name 保留未特化形态供 from_spec 构造 head。
    base_name: Optional[str] = None

    # -- Container element / key / value types (LIST / TUPLE / DICT) -----
    element_type: "TypeRef" = field(default_factory=lambda: _ANY_REF)
    allowed_element_types: List["TypeRef"] = field(default_factory=list)
    # 元组的位置元素类型（`tuple[T1, T2, ...]`）。
    # 与 ``allowed_element_types`` 正交：
    # ``positional_element_types`` 是按位置异构的、定长有序列表，仅 TUPLE kind
    # 在元素数 ≥ 2 时使用；单类型元组 ``tuple[T]`` 仍走 ``element_type`` 单字段。
    positional_element_types: List["TypeRef"] = field(default_factory=list)
    key_type: "TypeRef" = field(default_factory=lambda: _ANY_REF)
    value_type: "TypeRef" = field(default_factory=lambda: _ANY_REF)

    # -- Optional[T] (OPTIONAL kind) -------------------------------------
    wrapped_type: "TypeRef" = field(default_factory=lambda: _ANY_REF)

    # -- Bound method receiver (BOUND_METHOD kind) -----------------------
    receiver_type: "TypeRef" = field(default_factory=lambda: _ANY_REF.replace_head(""))
    func_spec_name: str = ""

    # -- TypeDef fields ------------------------------------------------
    required_capabilities: List[str] = field(default_factory=list)

    # -- Module-only: names of types that an `import mod` statement also
    # brings into the importing module's scope (e.g. `import file` exposes
    # file_handle / audio / image / video).  Empty for non-module specs.
    exported_types: List[str] = field(default_factory=list)

    # -- Kind → base-name mapping (used by get_base_name) ----------------
    _KIND_BASE_NAMES: ClassVar[Dict[str, str]] = {}

    def get_base_name(self) -> str:
        """族名（axiom 查询键 / 值层 kind 分派）。

        优先级：
        1. ``_axiom_name``（fn_callable/behavior/thread 等特化 spec 重定向）。
        2. 用户类泛型特化 spec 的 ``base_name`` 字段（``Box[int]`` → ``"Box"``，
           与内置泛型特化经 ``_KIND_BASE_NAMES`` 返回族名一致——消除双轨不对称）。
        3. ``_KIND_BASE_NAMES``（内置 kind → 族名映射）。
        4. ``self.name`` 回落（非特化/普通类）。
        """
        if self._axiom_name:
            return self._axiom_name
        if self.base_name:
            return self.base_name
        return TypeDef._KIND_BASE_NAMES.get(self.kind, self.name)


TypeDef._KIND_BASE_NAMES = {
    TypeKind.LIST.value:          "list",
    TypeKind.TUPLE.value:         "tuple",
    TypeKind.DICT.value:          "dict",
    TypeKind.OPTIONAL.value:      "Optional",
    TypeKind.BOUND_METHOD.value:  "bound_method",
    TypeKind.MODULE.value:        "module",
    # NOTE: TypeKind.CALLABLE_INSTANCE is intentionally NOT mapped here.
    # Callable-instance prototypes ("fn_callable"/"behavior") rely on either the
    # spec's own ``name`` (for unparameterised prototypes) or on the
    # ``_axiom_name`` override (for parameterised variants like
    # ``fn_callable[int]``) to dispatch to the correct axiom.
    TypeKind.CALLABLE_SIG.value:  "callable_sig",
    TypeKind.LAZY.value:          "module",
    TypeKind.THREAD.value:        "thread",
    TypeKind.CHANNEL.value:       "chan",
    TypeKind.SLOT.value:          "slot",
    TypeKind.SUBSCRIBER.value:    "subscriber",
}
