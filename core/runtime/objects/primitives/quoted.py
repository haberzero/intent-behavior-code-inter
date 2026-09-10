"""
core/runtime/objects/primitives/quoted.py

IbQuoted —— 被提及表达式值对象（一等不可变值类型）。

``quoted`` 是 ``meta.quote`` 的返回值：**数据/命令二元的数据形态**——经子引擎
compile-only 验证门冻结的自包含源串（可查询 / 可打印其自身 / 可精确对比），
经 ``meta.eval`` 取回表达式的**值**（命令形态）。

语义契约：

- **不可变值类型**：无修改面（源串冻结）；deep_clone 走不可变引用复用
  （同 vector/run_result 纪律）。
- **值语义**：按 source 值相等（逐字节）；``__hash__ = None``（不作 dict
  键/set 成员）。
- **字段访问**：``q.source``——字段值装箱 str，经 ``_dispatch_getattr``
  实例字段优先命中（run_result 三字段先例的单字段形态）。
- **拆箱**：``to_native() = source``（str）——边界拆箱单一入口自然成立
  （meta.eval 插件面经此取回源串送值通道执行）。
- **提示词面**：``__to_prompt__ = source`` **完整源串，无截断**（数据面忠实
  呈现——与 run_result 的截断摘要纪律不同：quoted 的数据形态**就是**源串，
  截断即失真）。
- **零 I/O 面**：纯内存值类型。

字段面由 ``QuotedAxiom`` 声明（``kind="field"``），方法面（cast_to/
__to_prompt__）经 axiom-driven auto-bind 绑定。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.kernel.issue import InterpreterError
from core.runtime.objects.kernel import IbObject, IbValue
from core.runtime.objects.ib_type_mapping import register_ib_type


@register_ib_type("quoted")
class IbQuoted(IbValue):
    """被提及表达式值对象。

    ``payload`` = 原生结构 ``{"source": str}``（序列化/边界 to_native 消费）；
    ``fields`` = source 字段装箱值（经 ``_dispatch_getattr`` 提供
    ``q.source`` attribute 访问）。
    """

    __slots__ = ()

    def __init__(
        self,
        ib_class: "IbObject",
        source: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ):
        if payload is not None:
            # 序列化水化直传（原生结构；字段据此重建装箱）
            source = payload.get("source", "")
        reg = ib_class.registry
        super().__init__(
            ib_class,
            payload={"source": source},
            fields={"source": reg.box(source)},
        )

    # ------------------------------------------------------------------ #
    # 值语义（相等/哈希——经原生 payload 比较）
    # ------------------------------------------------------------------ #

    def __eq__(self, other: "IbQuoted") -> bool:
        if not isinstance(other, IbQuoted):
            return NotImplemented
        return self.payload.get("source") == other.payload.get("source")

    def __ne__(self, other: "IbQuoted") -> bool:
        if not isinstance(other, IbQuoted):
            return NotImplemented
        return self.payload.get("source") != other.payload.get("source")

    __hash__ = None  # 显式不可哈希（不作 dict 键/set 成员）

    # ------------------------------------------------------------------ #
    # 拆箱 / 序列化
    # ------------------------------------------------------------------ #

    def to_native(self, memo=None) -> str:
        # 被提及表达式 = 不可变值类型：原生表征 = 完整源串（边界拆箱/
        # 序列化/值通道消费）
        return self.payload["source"]

    def __to_prompt__(self) -> str:
        """提示词面渲染 = 完整源串（数据面忠实呈现，无截断——截断即失真）。"""
        return self.payload["source"]

    def cast_to(self, target_class) -> IbObject:
        if target_class.name in ("quoted", "any"):
            return self
        if target_class.name == "str":
            return self.ib_class.registry.box(self.payload["source"])
        raise InterpreterError(
            f"TypeError: Cannot cast 'quoted' to '{target_class.name}' "
            f"(str/any 转换受支持)。",
        )

    def serialize_for_debug(self):
        return {
            "type": "quoted",
            "source_len": len(self.payload["source"]),
        }

    def __repr__(self):
        return f"<Quoted {self.payload['source']!r}>"
