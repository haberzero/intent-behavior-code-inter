from typing import Any, Dict, List, Optional

from ..kernel import IbObject, IbValue, IbClass, IbNone
from ..kernel.base import unbox
from ..ib_type_mapping import register_ib_type
from core.kernel.issue import InterpreterError


def wrap_optional(value: Any, declared_type: Any, registry: Any) -> Any:
    """Optional 值统一包装权威（单一绑定入口）。

    ``declared_type`` 为 Optional 类型（IbSpec 或解析后 spec）时，把非
    ``IbOptional`` 值包装进 ``IbOptional``（空值 → ``is_some=False``，
    非空 → ``is_some=True``）；否则原样返回。幂等：已是 ``IbOptional``
    不重复包装。

    **单一权威源**：局部变量/函数参数/返回/类字段/容器元素的 Optional 值
    创建一律经本函数，杜绝"同一 Optional 类型在不同路径产生 IbOptional 与
    裸 IbNone 两种空值表示"的表示分叉（统一 Optional 值模型根治）。
    """
    from core.kernel.spec.base import TypeKind

    if declared_type is None:
        return value
    if getattr(declared_type, "kind", None) != TypeKind.OPTIONAL.value:
        return value
    if isinstance(value, IbOptional):
        return value
    if registry is None:
        return value
    optional_class = (
        registry.get_class(declared_type.name) or registry.get_class("Optional")
    )
    if optional_class is None:
        return value
    is_some = not isinstance(value, IbNone)
    return IbOptional(optional_class, value, is_some)


def is_none_value(value: Any) -> bool:
    """值是否为 None 语义（统一判空权威）。

    ``is None``/``is not None`` 的 None 分支据此判定：裸 ``IbNone`` 与
    空 ``IbOptional``（``is_some=False``）均为 None。与 ``== None`` 对齐。
    """
    if isinstance(value, IbNone):
        return True
    if isinstance(value, IbOptional):
        return not value._is_some
    return False


@register_ib_type("Optional")
class IbOptional(IbValue):
    """
    IBC-Inter 的 Optional[T] 运行时值对象。

    包装一个内层值（可能为空）。``is_some`` 标志记录是否持有值：
    - ``is_some=True``   → 持有值（内层值为 ``payload``）
    - ``is_some=False``  → 空（``payload`` 为 None，语义上是 None）

    单承载：内层值统一存 ``payload``，不再重复存 ``_inner`` 槽（双写真相）。
    ``_is_some`` 为元数据保留。

    方法表面（``is_some``/``unwrap``/``or_else``）由 ``OptionalAxiom`` 声明，
    经 ``primitive_initializer`` 的 axiom-driven auto-bind 自动绑定到语言层。
    """
    __slots__ = ('_is_some',)

    def __init__(self, ib_class: IbClass, inner: Optional[IbObject], is_some: bool):
        super().__init__(ib_class, payload=inner)
        self._is_some = is_some

    # ------------------------------------------------------------------ #
    # 方法表面（OptionalAxiom.get_method_specs 声明）                    #
    # ------------------------------------------------------------------ #

    def is_some(self) -> IbObject:
        """返回是否持有值（bool）。"""
        return self.ib_class.registry.box(self._is_some)

    def is_none(self) -> IbObject:
        """返回是否为空（bool）——``is_some`` 的对称判空 API。"""
        return self.ib_class.registry.box(not self._is_some)

    def unwrap(self) -> IbObject:
        """返回内层值；空 Optional 时 fail-fast 抛错。"""
        if not self._is_some:
            raise InterpreterError(
                "unwrap() called on an empty Optional"
            )
        return self.payload

    def or_else(self, default: IbObject) -> IbObject:
        """持有值时返回内层值，否则返回默认值。"""
        if self._is_some:
            return self.payload
        return default

    # ------------------------------------------------------------------ #
    # 值协议                                                            #
    # ------------------------------------------------------------------ #

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        if not self._is_some:
            return None
        return self.payload.to_native(memo) if isinstance(self.payload, IbObject) else self.payload

    def __to_prompt__(self) -> str:
        if not self._is_some:
            return "null"
        return str(self.payload.__to_prompt__()) if hasattr(self.payload, "__to_prompt__") else str(self.payload)

    def to_bool(self) -> IbObject:
        """空 Optional 视为 False；持有值则按内层值判定。"""
        if not self._is_some:
            return self.ib_class.registry.box(False)
        return self.payload.to_bool() if isinstance(self.payload, IbObject) else self.ib_class.registry.box(True)

    def cast_to(self, target_class: Any) -> IbObject:
        if target_class.name == "str":
            return self.ib_class.registry.box(self.__to_prompt__())
        if target_class.name in ("Optional", "any"):
            return self
        if not self._is_some:
            return self
        if target_class.name == "bool":
            return self.to_bool()
        return self.payload.cast_to(target_class) if isinstance(self.payload, IbObject) else self

    def receive(self, message: str, args: List[IbObject]) -> IbObject:
        if message == "__eq__":
            right = args[0] if args else None
            return self.ib_class.registry.box(self._eq(right))
        if message == "__ne__":
            right = args[0] if args else None
            return self.ib_class.registry.box(not self._eq(right))
        return super().receive(message, args)

    def _eq(self, other: Any) -> bool:
        if not self._is_some:
            return isinstance(other, IbNone) or (
                isinstance(other, IbOptional) and not other._is_some
            )
        if isinstance(other, IbOptional):
            if not other._is_some:
                return False
            return unbox(self.payload) == unbox(other.payload)
        return unbox(self.payload) == unbox(other)

    def serialize_for_debug(self) -> Dict[str, Any]:
        return {
            "type": self.get_type_name(),
            "is_some": self._is_some,
            "value": (
                self.payload.serialize_for_debug() if isinstance(self.payload, IbObject) else None
            ),
        }

    def __repr__(self):
        if self._is_some:
            return f"Optional({self.payload!r})"
        return "Optional(None)"