from typing import Dict, Any, List, Optional, Mapping, Tuple

from core.kernel.issue import InterpreterError
from core.kernel.spec.type_ref import TypeRef as _TypeRef
from core.runtime.observability.diagnostics import kernel_diagnostic
from core.base.diagnostics.codes import (
    KDIAG_PROTOCOL_TO_PROMPT_FALLBACK,
    KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK,
)

from ..ib_type_mapping import register_ib_type


@register_ib_type("any")
@register_ib_type("auto")
@register_ib_type("callable")
@register_ib_type("void")
@register_ib_type("bound_method")
class IbObject:
    """
    IBC-Inter 对象基类 (一切皆对象)。
    模拟汇编层面的内存布局：持有一个指向 IbClass 的引用 (vptr) 和一个存储实例属性的字典。
    """
    __slots__ = ('ib_class', 'fields')

    def __init__(self, ib_class: 'IbClass'):
        self.ib_class = ib_class
        self.fields: Mapping[str, Any] = {}

    @classmethod
    def _create_blank(cls, ib_class: 'IbClass') -> 'IbObject':
        """值对象类型化实例构造钩子（统一值对象机制）。

        默认返回普通 ``IbObject``（即 ``instantiate`` 既有行为）。值对象实现类
        覆写返回其类型化空实例（如 ``IbThread._create_blank``），使
        ``ClassName(...)`` 语言构造产生真实实现类实例而非字段空壳。
        协议驱动：是否类型化实例由实现类自身决定，不经调用方标志位分支。
        """
        return IbObject(ib_class)

    def receive(self, message: str, args: List['IbObject']) -> 'IbObject':
        """
        统一消息传递接口。
        所有属性访问和方法调用都通过此入口分发。
        """
        from .functions import IbBoundMethod, IbFunction
        from .ib_class import IbClass

        # 下沉至公理层能力探测
        # 针对 __call__ 消息，检查类型公理是否声明了调用能力
        if message == '__call__':
            spec_reg = self.ib_class.registry.get_metadata_registry()
            if spec_reg and self.ib_class.spec:
                call_cap = spec_reg.get_call_cap(self.ib_class.spec)
                if call_cap:
                    # 函数家族（IbFunction 子类：用户函数/原生函数/绑定方法/LLM 函数）
                    # 直接走 Python .call（isinstance 精确判别，替代 hasattr 探测）。
                    if isinstance(self, IbFunction):
                        return self.call(self.ib_class.registry.get_none(), args)
            # 用户类实例 + 用户定义的 __call__ 协议方法：返回 CPSDrivable drive，
            # VM 经 cps_drive 帧内驱动（UserFunctionCall trampoline，EXEC-1 根治）。
            # 不再落回 method.call → 嵌套调度器（深递归 Python 栈 + Waitable 死锁）。
            # receive 保持唯一协议分派入口（返回 drive，非 VM 侧特判）。
            method = self.ib_class.lookup_method('__call__')
            if method is not None:
                from .ib_class import _UserCallDrive
                from .user_functions import IbUserFunction
                if isinstance(method, IbUserFunction):
                    return _UserCallDrive(method, args, self)

        if message == '__getattr__' and len(args) > 0:
            attr_name = args[0].to_native()
            # 优先查找实例字段
            if attr_name in self.fields:
                return self.fields[attr_name]
            # 降级查找类方法
            method = self.ib_class.lookup_method(attr_name)
            if method:
                return IbBoundMethod(self, method)

        # 2. 正常消息路由：查找类方法
        method = self.ib_class.lookup_method(message)
        if method:
            return method.call(self, args)

        # [cast_to Hook] 处理类型转换消息
        if message == 'cast_to':
            if not args:
                raise InterpreterError("cast_to requires exactly one argument: target class")

            target_class = args[0]
            target_name = getattr(target_class, 'name', None)
            if not target_name:
                raise InterpreterError("cast_to argument must be an IbClass")

            # 同一类型转换：直接返回自身
            if self.ib_class.name == target_name:
                return self

            # 向上转型（upcast）：目标类型是当前类的祖先，直接返回自身（安全且语义正确）
            if isinstance(target_class, IbClass) and self.ib_class.is_assignable_to(target_class):
                return self

            # __to_prompt__ 协议产出 str；仅当目标类型可接受 str 时此路径有效
            spec_reg = self.ib_class.registry.get_metadata_registry()
            target_spec = getattr(target_class, 'spec', None)
            str_spec = spec_reg.resolve("str") if spec_reg else None
            if str_spec and target_spec and spec_reg.is_assignable(str_spec, target_spec):
                to_prompt_method = self.ib_class.lookup_method('__to_prompt__')
                if to_prompt_method:
                    try:
                        prompt_result = to_prompt_method.call(self, [])
                        # Unwrap if it's an IbObject
                        prompt_result = unbox(prompt_result)
                        return self.ib_class.registry.box(prompt_result)
                    except Exception as e:
                        kernel_diagnostic(
                            code=KDIAG_PROTOCOL_TO_PROMPT_FALLBACK,
                            detail={
                                "context": "cast",
                                "type": self.ib_class.name,
                                "target": target_name,
                                "error": repr(e),
                            },
                            message=(
                                f"cast via __to_prompt__ failed for "
                                f"{self.ib_class.name}->{target_name}: {e!r}"
                            ),
                        )

            # 无法执行类型转换，抛出明确错误
            raise InterpreterError(
                f"TypeError: Cannot cast '{self.ib_class.name}' to '{target_name}'. "
                f"Type '{self.ib_class.name}' does not implement type conversion."
            )

        raise AttributeError(f"Object of type '{self.ib_class.name}' has no method '{message}'")

    def __to_prompt__(self) -> str:
        """
        响应 Spec 协议：定义对象在 LLM 视角下的表现形式。
        """
        try:
            res = self.receive('__to_prompt__', [])
            return str(res.value) if hasattr(res, 'value') else str(res)
        except (AttributeError, InterpreterError):
            return f"<Instance of {self.ib_class.name}>"

    def __from_prompt__(self, raw_response: str) -> Tuple[bool, Any]:
        """
        Parse a value from raw LLM output text.
        Delegates to the spec's axiom from_prompt capability.
        """
        try:
            spec_reg = self.ib_class.registry.get_metadata_registry()
            if spec_reg and self.ib_class.spec:
                if not spec_reg.satisfies_protocol(self.ib_class.spec, "from_prompt"):
                    return (False, f"无法将 '{raw_response}' 解析为 {self.ib_class.name} 类型")
                cap = spec_reg.get_from_prompt_cap(self.ib_class.spec)
                if cap:
                    return cap.from_prompt(raw_response, self.ib_class.spec)
        except Exception as e:
            kernel_diagnostic(
                code=KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK,
                detail={
                    "context": "parse",
                    "type": self.ib_class.name,
                    "error": repr(e),
                },
                message=f"__from_prompt__ parse failed for {self.ib_class.name}: {e!r}",
            )
        return (False, f"无法将 '{raw_response}' 解析为 {self.ib_class.name} 类型")

    def __outputhint_prompt__(self) -> str:
        """
        返回期望的 LLM 输出格式描述。
        优先尝试通过 vtable 调用用户定义的 __outputhint_prompt__ 方法，
        没有时退回到默认描述。
        """
        try:
            res = self.receive('__outputhint_prompt__', [])
            return str(res.to_native()) if isinstance(res, IbObject) else str(res)
        except (AttributeError, InterpreterError):
            pass
        return f"请返回一个 {self.ib_class.name} 类型的值"

    # ---  基础协议实现 ---
    def __not__(self) -> 'IbObject':
        """逻辑非运算协议"""
        # 使用 vtable to_bool 判定并取反，返回 bool 类型
        bool_val = self.receive('to_bool', []).to_native()
        return self.ib_class.registry.box(False if bool_val else True)

    def serialize_for_debug(self) -> Mapping[str, Any]:
        """
        为 IDBG 等调试组件提供的序列化方法。
        将 IbObject 转换为 Python 原生字典。
        """
        res = {k: (v.serialize_for_debug() if isinstance(v, IbObject) else v)
                   for k, v in self.fields.items()}
        res["__type__"] = self.ib_class.name
        res["__repr__"] = self.__repr__()
        return res

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        return self

    def __repr__(self):
        return f"<{self.ib_class.name} object at {hex(id(self))}>"


class IbValue(IbObject):
    """
    Unified runtime value carrier.

    ``IbValue`` centralizes the data shape shared by all user-visible runtime
    values:
    - ``type_ref``: structured runtime type identity
    - ``payload``: native payload / container payload / callable payload
    - ``fields``: object-style instance fields when the value has them
    - ``meta``: extra runtime metadata for specialized values

    Concrete value types (``IbInteger``, ``IbString``, ``IbList``,
    ``IbDict``, ``IbFnCallable``, ``IbBehavior``, …) inherit from ``IbValue``
    and each carry their domain-specific behaviour (interning, native
    conversions, list operations, callable execution logic, …).  They are
    permanent type-implementation classes, not compatibility shims.

    Storage conventions:
    - Scalar types (int / float / str / bool) store their native value in
      ``payload``; the inherited ``value`` property provides a named alias.
    - Sequence types (list / tuple) store their element collection in
      ``payload`` and expose it via an ``elements`` property.
    - Dict stores its mapping via ``IbObject.fields`` (and mirrors it in
      ``payload``).
    - Callable instances (fn_callable / behavior) store the target node UID in
      ``payload`` and runtime state in ``meta``.
    """
    __slots__ = ('type_ref', 'payload', 'meta')

    def __init__(
        self,
        ib_class: 'IbClass',
        payload: Any = None,
        *,
        fields: Optional[Dict[str, Any]] = None,
        type_ref: Optional[Any] = None,
        meta: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(ib_class)
        if fields is not None:
            self.fields = fields
        if type_ref is not None:
            self.type_ref = type_ref
        else:
            spec = getattr(ib_class, "spec", None)
            self.type_ref = _TypeRef.from_spec(spec) if spec is not None else None
        self.payload = payload
        self.meta = dict(meta) if meta is not None else {}

    @property
    def value(self) -> Any:
        return self.payload

    @value.setter
    def value(self, new_value: Any) -> None:
        self.payload = new_value

    def get_type_name(self) -> str:
        if self.type_ref is not None and hasattr(self.type_ref, "head"):
            return self.type_ref.head
        return self.ib_class.name

    def is_type(self, *names: str) -> bool:
        return self.get_type_name() in names or self.ib_class.name in names

    def get_meta(self, key: str, default: Any = None) -> Any:
        return self.meta.get(key, default)

    def set_meta(self, key: str, value: Any) -> None:
        self.meta[key] = value

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        """
        Return the raw payload for scalar / already-native values.

        Container-like subclasses override this to recursively unwrap nested
        ``IbObject`` / ``IbValue`` members while preserving memoized cycle
        handling.
        """
        return self.payload

    def serialize_for_debug(self) -> Mapping[str, Any]:
        data: Dict[str, Any] = {"type": self.get_type_name(), "payload": self.payload}
        if self.fields:
            data["fields"] = {
                k: (v.serialize_for_debug() if isinstance(v, IbObject) else v)
                for k, v in self.fields.items()
            }
        if self.meta:
            data["meta"] = dict(self.meta)
        return data

    def __repr__(self):
        return f"<{self.get_type_name()} value payload={self.payload!r}>"


def unbox(value: Any) -> Any:
    """单一拆箱边界函数：IbObject 数据值 → 原生 Python；原生值原样透传。

    收敛全仓散落的 ``x.to_native() if hasattr(x, 'to_native') else x`` 双轨写法。
    **不含**可调用实例（behavior/fn_callable/callable）的特殊透传——那些是站点
    专属语义（如插件代理参数），由调用方按需另行判定。
    """
    if isinstance(value, IbObject):
        return value.to_native()
    return value


def is_sequence_value(value: Any) -> bool:
    """判断值是否为原生序列容器（list/tuple）。

    值层容器分派的单一判定入口：语义是"可直接取 ``.elements`` 的原生序列"，
    经值对象 kind 基类名判定（特化类 ``list[int]`` 沿 spec 基名 ``list``；
    与 ``runtime_serializer._value_base_name`` 同构）。非 ``IbValue`` 对象
    （内核结构、AST 节点等）一律 False。
    """
    if not isinstance(value, IbValue):
        return False
    ib_class = getattr(value, "ib_class", None)
    if ib_class is None:
        return False
    spec = getattr(ib_class, "spec", None)
    base = spec.get_base_name() if spec is not None else ib_class.name
    return base in ("list", "tuple")
