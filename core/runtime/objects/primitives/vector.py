"""
core/runtime/objects/primitives/vector.py

IbVector —— 一等词嵌入向量值类型（值语义）。

设计契约（词嵌入一等能力——值语义固定维度向量）：

- **固定维度**：创建时定，不可变（无扩维/缩维/改元素面——方法面闭合，
  任何修改操作返回**新** vector，不变更自身）。
- **值语义**：按元素精确相等（浮点逐元素；-0.0 == 0.0 按 IEEE 754 相等）；
  与 dict/list 按引用传递显式对立。
- **不可拆箱**：``to_native()`` 显式违约（EMB_INVALID_INPUT）——dict 键/
  set 成员/原生调用边界经 unbox 单一边界统一 fail-fast；``__hash__ = None``
  双保险（Python 原生层亦拒绝）。浮点相等语义在哈希面未定义，故 vector
  不作 dict 键（显式排除，非"能哈希但语义危险"的隐式面）。
- **NaN/Inf 构造期封死**：值语义相等在 NaN 上未定义，构造点 fail-fast
  （EMB_INVALID_INPUT）；方法面输入经自身构造点同纪律。
- **不做隐式归一化**：``cosine`` 自带尺度不变性；``norm()`` 显式可用。
- **零 I/O 面**：纯内存值类型（沙箱/fs 无交互）。
"""

from __future__ import annotations

import math
from typing import Sequence, Tuple

from core.base.diagnostics.codes import (
    EMB_DIMENSION_MISMATCH,
    EMB_INVALID_INPUT,
    EMB_ZERO_NORM,
)
from core.kernel.issue import InterpreterError
from core.runtime.objects.kernel import IbObject, IbValue
from core.runtime.objects.kernel.base import unbox
from core.runtime.objects.ib_type_mapping import register_ib_type


def _validate_elements(elements: Sequence) -> Tuple[float, ...]:
    """元素面校验（构造点单一纪律）：数值可转 float + 有限性 fail-fast。"""
    out: list = []
    for i, e in enumerate(elements):
        try:
            f = float(e)
        except (TypeError, ValueError):
            raise InterpreterError(
                f"TypeError: vector 元素须为数值（位置 {i} 收到 {type(e).__name__}）。",
                error_code=EMB_INVALID_INPUT,
            )
        if not math.isfinite(f):
            raise InterpreterError(
                f"vector 含非有限值（位置 {i}：NaN/Inf，契约违约——"
                f"值语义相等在 NaN 上未定义，构造期封死）。",
                error_code=EMB_INVALID_INPUT,
            )
        out.append(f)
    return tuple(out)


@register_ib_type("vector")
class IbVector(IbValue):
    """词嵌入向量值对象。``payload`` = 不可变 float 元组（元素面）。"""

    __slots__ = ()

    def __init__(self, elements: Sequence, ib_class: "IbObject"):
        super().__init__(ib_class, payload=_validate_elements(elements))

    # ------------------------------------------------------------------ #
    # 元素面
    # ------------------------------------------------------------------ #

    @property
    def elements(self) -> Tuple[float, ...]:
        return self.payload

    def __len__(self) -> int:
        return len(self.payload)

    def __getitem__(self, key) -> float:
        # 下标入口可能是 IbObject（VM 经 __getitem__ 消息派发）或原生 int
        if isinstance(key, IbObject):
            key = unbox(key)
        if isinstance(key, slice):
            return self.payload[key]
        return self.payload[key]

    # ------------------------------------------------------------------ #
    # 值语义（相等/哈希）
    # ------------------------------------------------------------------ #

    def __eq__(self, other: "IbVector") -> bool:
        if not isinstance(other, IbVector):
            return NotImplemented
        return self.payload == other.payload

    def __ne__(self, other: "IbVector") -> bool:
        # 显式实现（语言层 ==/!= 经 vtable 派发，不依赖 Python 自动推导）
        if not isinstance(other, IbVector):
            return NotImplemented
        return self.payload != other.payload

    __hash__ = None  # 显式不可哈希（不作 dict 键/set 成员——浮点相等面未定义）

    # ------------------------------------------------------------------ #
    # 拆箱边界（显式违约——排除面）
    # ------------------------------------------------------------------ #

    def to_native(self, memo=None) -> object:
        raise InterpreterError(
            "vector 是值语义一等类型，不可拆箱为原生值"
            "（dict 键 / set 成员 / 原生调用边界不支持）。",
            error_code=EMB_INVALID_INPUT,
        )

    # ------------------------------------------------------------------ #
    # 方法面（vtable receive 派发；修改操作返回新 vector）
    # ------------------------------------------------------------------ #

    def _require_same_dim(self, other: "IbVector", op: str) -> None:
        if len(self.payload) != len(other.payload):
            raise InterpreterError(
                f"vector {op} 维度不一致：{len(self.payload)} vs {len(other.payload)}。",
                error_code=EMB_DIMENSION_MISMATCH,
            )

    def _new_vector(self, elements: Sequence) -> "IbVector":
        return IbVector(elements, self.ib_class)

    def dim(self) -> IbObject:
        """维度（元素个数）。"""
        return self.ib_class.registry.box(len(self.payload))

    def to_list(self) -> IbObject:
        """数据面原生列表（interchange——计算编排网关/宿主边界显式拆箱面；
        vector = 1D tensor 的缓冲交换形态）。"""
        return self.ib_class.registry.box(list(self.payload))

    def shape(self) -> IbObject:
        """形状（vector = 1D tensor → [dim]）。"""
        return self.ib_class.registry.box([len(self.payload)])

    def ndim(self) -> IbObject:
        """维数（vector = 1D tensor → 1）。"""
        return self.ib_class.registry.box(1)

    def dtype(self) -> IbObject:
        """元素类型（f64——当前统一数据形态）。"""
        return self.ib_class.registry.box("f64")

    def dot(self, other: IbObject) -> IbObject:
        """点积（dim 不一致 fail-fast）。"""
        o = _as_vector(other)
        self._require_same_dim(o, "dot")
        return self.ib_class.registry.box(
            sum(a * b for a, b in zip(self.payload, o.payload))
        )

    def norm(self) -> IbObject:
        """L2 范数（零范数 = 0.0，不违约——范数定义域含零向量）。"""
        return self.ib_class.registry.box(
            math.sqrt(sum(x * x for x in self.payload))
        )

    def cosine(self, other: IbObject) -> IbObject:
        """余弦相似度（尺度不变；零范数 fail-fast——余弦未定义不产生静默 0）。"""
        o = _as_vector(other)
        self._require_same_dim(o, "cosine")
        na = math.sqrt(sum(x * x for x in self.payload))
        nb = math.sqrt(sum(x * x for x in o.payload))
        if na == 0.0 or nb == 0.0:
            raise InterpreterError(
                "vector cosine 零范数向量（余弦未定义，fail-fast）。",
                error_code=EMB_ZERO_NORM,
            )
        return self.ib_class.registry.box(
            sum(a * b for a, b in zip(self.payload, o.payload)) / (na * nb)
        )

    def scale(self, k: IbObject) -> IbObject:
        """缩放（返回新 vector）。"""
        f = unbox(k)
        try:
            f = float(f)
        except (TypeError, ValueError):
            raise InterpreterError(
                f"TypeError: vector.scale 参数须为数值（收到 {type(f).__name__}）。",
                error_code=EMB_INVALID_INPUT,
            )
        if not math.isfinite(f):
            raise InterpreterError(
                "vector.scale 参数非有限值（NaN/Inf，契约违约）。",
                error_code=EMB_INVALID_INPUT,
            )
        return self._new_vector([x * f for x in self.payload])

    def add(self, other: IbObject) -> IbObject:
        """逐元素相加（返回新 vector）。"""
        o = _as_vector(other)
        self._require_same_dim(o, "add")
        return self._new_vector([a + b for a, b in zip(self.payload, o.payload)])

    def sub(self, other: IbObject) -> IbObject:
        """逐元素相减（返回新 vector）。"""
        o = _as_vector(other)
        self._require_same_dim(o, "sub")
        return self._new_vector([a - b for a, b in zip(self.payload, o.payload)])

    # ------------------------------------------------------------------ #
    # 类型转换 / 调试
    # ------------------------------------------------------------------ #

    def __to_prompt__(self) -> str:
        """提示词面渲染（截断摘要——全量维度进提示词 = 污染风险）。"""
        return self._string_repr()

    def cast_to(self, target_class) -> IbObject:
        if target_class.name in ("vector", "any"):
            return self
        if target_class.name == "str":
            return self.ib_class.registry.box(self._string_repr())
        # 无法转换显式违约（对齐通用 cast_to 链纪律：静默回落 = 类型谎言）
        raise InterpreterError(
            f"TypeError: Cannot cast 'vector' to '{target_class.name}' "
            f"(str/any 转换受支持)。",
            error_code=EMB_INVALID_INPUT,
        )

    def _string_repr(self) -> str:
        # idbg/str 摘要：dim + 前 8 维（非全量 dump）
        head = ", ".join(f"{x:.6g}" for x in self.payload[:8])
        ellipsis = ", ..." if len(self.payload) > 8 else ""
        return f"vector[{len(self.payload)}]({head}{ellipsis})"

    def serialize_for_debug(self):
        return {
            "type": "vector",
            "dim": len(self.payload),
            "preview": [round(x, 6) for x in self.payload[:8]],
        }

    def __repr__(self):
        return self._string_repr()


def _as_vector(obj: IbObject) -> IbVector:
    """方法面其他操作数校验（非 vector → fail-fast）。"""
    if not isinstance(obj, IbVector):
        name = getattr(obj, "ib_class", None)
        other_name = name.name if name is not None else type(obj).__name__
        raise InterpreterError(
            f"TypeError: vector 方法操作数须为 vector（收到 {other_name}）。",
            error_code=EMB_INVALID_INPUT,
        )
    return obj
