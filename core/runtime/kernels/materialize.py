"""P2 typed 值通道物化——单一数据驱动转换表（kind → 对象模型）。

替代 engine 镜像的散落特判（quoted 保真物化 / 容器特化复刻 / 函数代理 /
declared 白名单双路径——审计 3.2 收敛）：物化 = kind + declared_type 查表，
engine 零语义判断（只做"调物化器 → 按 kind 决定写入路径"）。

- 数据 kind（int/float/str/bool/none/list/dict）= 原生值直通 + 容器特化绑定；
- quoted = IbQuoted 物化（源串全保真，kind 驱动——不再依赖 declared 特判）；
- vector = IbVector 物化（真实数据，替代 repr 显示串降级）；
- function = RustHostCallable（宿主 callable 统一协议——无状态执行）；
- knowledge/meta/error/host = 显示形态（KB 数据面未跨边界，E4/R2 后收敛）。

状态写入路径（define/materialize 双路径）按 kind 数据驱动，非 declared 白名单：
数据 kind → define_variable（VM 权威类型检查面同构）；非数据 kind →
materialize_variable（无检查面——函数/显示形态值不适用运行时类型检查）。
materialize_variable 旁路 = E4（函数值一等化）时随函数物化删除。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional


def bind_container_specialization(registry, value: Any, declared_type: Any) -> Any:
    """容器特化身份绑定（leaf._bind_container_specialization 同构 registry 面）：
    声明为内置容器特化的容器值 → ib_class 重绑水化特化类 + type_ref 结构化；
    嵌套容器元素经 spec.element_type 递归绑定。非容器/非特化声明 = 原样返回。

    原位于 engine（审计 3.2"特化复刻"）——移入物化层（物化逻辑归属单一面）。
    """
    if not isinstance(value, (list, dict)) or declared_type is None:
        return value
    spec_name = (
        getattr(declared_type, "qualified_name", None)
        or getattr(declared_type, "name", None)
    ) or ""
    container_kind = "list" if isinstance(value, list) else "dict"
    if spec_name.split("[", 1)[0].strip() != container_kind:
        return value
    spec_reg = registry.get_metadata_registry()
    if spec_reg is None:
        return value
    if "[" not in spec_name or spec_reg.resolve(spec_name) is None:
        return value
    specialized_cls = registry.get_class(spec_name)
    if specialized_cls is None:
        return value
    try:
        from core.runtime.objects.kernel import IbClass as _IbClass

        if not isinstance(specialized_cls, _IbClass):
            return value
        boxed = value if hasattr(value, "ib_class") else registry.box(value)
        if getattr(boxed, "ib_class", None) is None:
            return value
        boxed.ib_class = specialized_cls
        from core.kernel.spec.type_ref import TypeRef as _TypeRef

        boxed.type_ref = _TypeRef.from_spec(declared_type)
        # 嵌套元素递归（spec 元素类型 ref → 解析 → 绑定）
        elem_ref = getattr(declared_type, "element_type", None)
        if elem_ref is not None:
            elem_spec = spec_reg.resolve_typeref(elem_ref)
            if elem_spec is not None:
                elements = getattr(boxed, "elements", None)
                if elements is not None and isinstance(elements, list):
                    # 仅容器元素递归（标量元素装箱形态保持——解箱/回箱循环
                    # 会破坏元素装箱身份）
                    for i, elt in enumerate(list(elements)):
                        elt_base = (
                            getattr(getattr(elt, "ib_class", None), "name", "")
                            or ""
                        ).split("[", 1)[0]
                        if isinstance(elt, (list, dict)) or elt_base in ("list", "dict"):
                            native = (
                                elt
                                if isinstance(elt, (list, dict))
                                else _maybe_unbox(elt)
                            )
                            bound = bind_container_specialization(registry, native, elem_spec)
                            if bound is not None and bound is not elt:
                                elements[i] = bound
        return boxed
    except Exception:
        return value


def _maybe_unbox(v):
    """容器元素解箱（绑定面以原生值为操作面——box 幂等[已装箱原样返回]）。"""
    if hasattr(v, "to_native"):
        try:
            return v.to_native()
        except Exception:
            return v
    return v


class RustHostCallable:
    """宿主 .call 契约（P4 协议）：Rust 顶层函数值的可调用代理——经
    ``call_top_level_function`` 无状态执行（纯函数契约，DIVERGENCE 登记
    host_call_closure_state）。生命周期 = 对象持有（artifact 引用），无全局
    注册表无 unsafe（审计 3.6 会话 API 收敛）。

    ``__call__``（Python callable）→ registry.box 包装为 IbNativeFunction
    （.call 委托 py_func(*args)）——函数值状态读回 = 可调用对象（宿主
    ``obj.call(None, args)`` 契约成立）。
    """

    def __init__(self, kernel, artifact_json, name, registry):
        self._kernel = kernel
        self._artifact_json = artifact_json
        self._name = name
        self._registry = registry

    def __call__(self, *args):
        import json as _json

        payload = [
            a.to_native() if hasattr(a, "to_native") else a
            for a in args
        ]
        result_json, _out = self._kernel.call_top_level_function(
            self._artifact_json,
            self._name,
            _json.dumps(payload, ensure_ascii=False),
        )
        return _json.loads(result_json)


class StateMaterializer:
    """P2 typed 值通道物化（单一数据驱动转换表——kind → handler）。"""

    # 非数据/非原生 kind → 显示形态（KB 数据面未跨边界——R2 收敛）
    _DISPLAY_KINDS = {"meta", "error", "host"}

    def __init__(self, registry, interpreter=None, kernel=None, artifact_json=None):
        self._registry = registry
        self._interpreter = interpreter
        self._kernel = kernel
        self._artifact_json = artifact_json
        self._kind_handlers: Dict[str, Callable[[Any, Any], Any]] = {
            "int": self._as_is,
            "float": self._as_is,
            "str": self._as_is,
            "bool": self._as_is,
            "none": self._none,
            "list": self._list,
            "dict": self._dict,
            "quoted": self._quoted,
            "vector": self._vector,
            "knowledge": self._display,
            "function": self._function,
            "meta": self._display,
            "error": self._display,
            "host": self._none,
        }

    def materialize(self, kind, value, declared_type):
        handler = self._kind_handlers.get(kind) if kind is not None else None
        if handler is None:
            return value  # 未知 kind = 边界值原样（保守）
        return handler(value, declared_type)

    # -- 原生数据面 --
    def _as_is(self, v, dt):
        return v

    def _none(self, v, dt):
        return None

    def _display(self, v, dt):
        # 显示形态（repr 面——显式 kind，非隐式降级；KB/error 等数据面未
        # 跨边界时以显示形态暴露）
        return v

    def _list(self, v, dt):
        items = [
            self.materialize(
                e.get("kind") if isinstance(e, dict) else None,
                e.get("value") if isinstance(e, dict) else e,
                None,
            )
            for e in (v or [])
        ]
        return bind_container_specialization(self._registry, items, dt)

    def _dict(self, v, dt):
        out = {}
        for k, val in (v or {}).items():
            kk = (
                self.materialize(k.get("kind"), k.get("value"), None)
                if isinstance(k, dict)
                else k
            )
            out[kk] = (
                self.materialize(val["kind"], val["value"], None)
                if isinstance(val, dict) and "kind" in val
                else val
            )
        return bind_container_specialization(self._registry, out, dt)

    # -- 一等值物化（Rust 原生值 → 语言对象模型）--
    def _quoted(self, v, dt):
        quoted_cls = self._registry.get_class("quoted")
        if quoted_cls is None:
            return v
        from core.runtime.objects.primitives.quoted import IbQuoted

        try:
            return IbQuoted(quoted_cls, source=v)
        except Exception:
            return v

    def _vector(self, v, dt):
        vector_cls = self._registry.get_class("vector")
        if vector_cls is None:
            return v
        from core.runtime.objects.primitives.vector import IbVector

        try:
            return IbVector(v or [], vector_cls)
        except Exception:
            return v

    def _function(self, v, dt):
        # 宿主 callable 统一协议（P4）：RustHostCallable——经
        # call_top_level_function 无状态执行（纯函数契约）。
        if self._kernel is None or self._artifact_json is None or not isinstance(v, dict):
            return v
        return RustHostCallable(
            self._kernel, self._artifact_json, v.get("name"), self._registry
        )
