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
                "unwrap() called on an empty Optional",
                error_code="RUN_ATTRIBUTE_ERROR",
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
        """统一委托链（Optional[T] 是 T 的透明包装：T 的成员/方法经此透传，
        Optional 专属方法 unwrap/is_some/is_none/or_else 回退 vtable）。

        - 协议处理器（__eq__/__ne__/__getattr__/__call__ 等 Optional 专属语义）
          先于委托；处理器返回 None 表示无专属行为，继续委托链。
        - 持有值：委托内层值（容器协议 len/下标/迭代/成员访问透传）。
          __getattr__ 委托的"未命中"（内层 _default_getattr fail-fast 抛
          InterpreterError）须回退 Optional 自身方法；其它消息委托抛
          InterpreterError 是内层方法体的真实错误，必须传播不吞。
        """
        # 1. Optional 专属协议处理器（返回 None 继续委托链）
        if message in self._protocol_message_names():
            handler = getattr(self, f"_dispatch_{message.strip('_')}", None)
            if handler is not None:
                result = handler(message, args)
                if result is not None:
                    return result
        # 2. 委托内层值（容器协议 len/下标/迭代/成员访问透传）。
        #    __getattr__ 已在 _dispatch_getattr 内完成内层委托——此处跳过，
        #    避免双重委托（内层 __getattr__ 副作用/开销重复执行）。
        if message != "__getattr__" and self._is_some and isinstance(self.payload, IbObject):
            try:
                return self.payload.receive(message, args)
            except AttributeError:
                pass
            except InterpreterError:
                if message != "__getattr__":
                    raise
        # 3. Optional 自身/父链 vtable（unwrap/is_some/is_none/or_else/to_bool/
        #    cast_to/__to_prompt__）。
        method = self.ib_class.lookup_method(message)
        if method is not None:
            return method.call(self, args)
        # 4. 空值：协议操作 fail-fast（明确诊断，不静默——空 Optional 上
        #    len/下标/成员访问等操作无意义，报错优于返回错误值）。
        if not self._is_some:
            raise InterpreterError(
                f"Operation '{message}' is not available on an empty Optional",
                error_code="RUN_ATTRIBUTE_ERROR",
            )
        # 5. 非空但内层与自身均无此成员：基类语义（AttributeError → 诊断码）。
        return super().receive(message, args)

    def _dispatch_eq(self, message: str, args: List[IbObject]) -> IbObject:
        """``__eq__`` 协议：空 Optional 与 None/空 Optional 相等；有值比较内层。"""
        right = args[0] if args else None
        return self.ib_class.registry.box(self._eq(right))

    def _dispatch_ne(self, message: str, args: List[IbObject]) -> IbObject:
        """``__ne__`` 协议：``__eq__`` 取反。"""
        right = args[0] if args else None
        return self.ib_class.registry.box(not self._eq(right))

    def _dispatch_call(self, message: str, args: List[IbObject]):
        """无 Optional 专属调用语义：委托链处理（显式关闭基类默认 __call__ 处理器）。"""
        return None

    def _dispatch_cast_to(self, message: str, args: List[IbObject]):
        """无 Optional 专属转换语义：委托链处理（内层优先，显式关闭基类默认处理器）。"""
        return None

    def _dispatch_getattr(self, message: str, args: List[IbObject]):
        """``__getattr__``：委托内层（有值）→ Optional 自身绑定方法 → 空值 fail-fast。

        有值且无此成员时返回 None → 骨架继续（vtable ``__getattr__`` → 基类
        fail-fast，与原语义一致）。
        """
        if len(args) == 0:
            return None
        if self._is_some and isinstance(self.payload, IbObject):
            try:
                return self.payload.receive(message, args)
            except AttributeError:
                pass
            except InterpreterError:
                pass  # 内层属性未命中 → 回退 Optional 自身（原语义）
        attr_name = args[0].to_native()
        method = self.ib_class.lookup_method(attr_name)
        if method is not None:
            from ..kernel.functions import IbBoundMethod

            return IbBoundMethod(self, method)
        if not self._is_some:
            raise InterpreterError(
                f"Operation '{message}' is not available on an empty Optional",
                error_code="RUN_ATTRIBUTE_ERROR",
            )
        return None

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