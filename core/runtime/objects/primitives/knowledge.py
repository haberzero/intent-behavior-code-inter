"""
core/runtime/objects/primitives/knowledge.py

IbKnowledge —— 已验证知识注册表值对象（一等内置值类型）。

语言自动机的知识层（D 纸带）：机器持有的知识是**类型化、门控、可审计**的。
定位类比 = in-language knowledge database（持久/结构化/门控/可审计/可查询）。

语义契约（设计裁定 K1-K9）：

- **知识库对象 = 可变值对象**（引用语义，同 dict——可共享/可传参/可进
  save_state）；**条目值 = 冻结快照**（store 入时深克隆 + get 出时深克隆——
  "知识库可变，知识不可变"，防引用陷阱污染审计）。
- **验证门**：store 时引擎求值 ``check(value)``——假 = fail-fast
  （KNW_CHECK_REJECTED，未过验证门拒绝登记）；check 含 LLM 调用/不透明 =
  编译期 SEM 错误（SEM_KNW_*，fail-fast：不纯度不可证明即拒绝）。
- **更正语义**：amend append-only（原值保留事件流，当前值指针切换）+
  reason 强制非空 + 新值再过 check 门（防更正通道变无门控写口）。
- **审计形态**：事件序号 = 引擎单调序号（非墙钟，确定性可复现）；
  history 事件 list（{seq, kind, value, reason}）；未登记 = 空 list。
- **铁律**：一切知识操作 = 显式程序操作（普通值方法调用）——引擎不提供
  任何"查表命中则跳过 LLM"的隐式路由（@~...~ 语义不变量）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.base.diagnostics.codes import (
    KNW_CHECK_REJECTED,
    KNW_KEY_EXISTS,
    KNW_REASON_EMPTY,
)
from core.kernel.issue import InterpreterError
from core.runtime.objects.kernel import IbObject, IbValue
from core.runtime.objects.kernel.base import unbox
from core.runtime.objects.deep_clone import try_deep_clone
from core.runtime.objects.ib_type_mapping import register_ib_type


def _clone_snapshot(value: IbObject) -> IbObject:
    """深克隆冻结快照（值不可克隆 → fail-fast，不静默存引用）。"""
    cloned = try_deep_clone(value)
    if cloned is None:
        name = getattr(value.ib_class, "name", "?") if getattr(value, "ib_class", None) else "?"
        raise InterpreterError(
            f"knowledge: 条目值类型 '{name}' 不可深克隆，拒绝登记"
            "（知识快照须为可克隆值类型）。",
            error_code=KNW_CHECK_REJECTED,
        )
    return cloned


@register_ib_type("knowledge")
class IbKnowledge(IbValue):
    """已验证知识注册表。``payload`` = ``{"entries": {...}, "seq": int}``。"""

    __slots__ = ()

    @classmethod
    def _create_blank(cls, ib_class: "IbObject") -> "IbKnowledge":
        """类型化空实例：使 ``knowledge()`` 语言构造产生真实 IbKnowledge
        （统一值对象机制——thread 先例同型）。"""
        return cls(ib_class)

    def __init__(self, ib_class: "IbObject", payload: Any = None):
        if payload is None:
            payload = {"entries": {}, "seq": 0}
        super().__init__(ib_class, payload=payload)

    # ------------------------------------------------------------------ #
    # 内部结构访问（单一权威：payload 结构）
    # ------------------------------------------------------------------ #

    def _entries(self) -> Dict[str, Dict[str, Any]]:
        return self.payload["entries"]

    def _next_seq(self) -> int:
        self.payload["seq"] += 1
        return self.payload["seq"]

    # ------------------------------------------------------------------ #
    # 方法面（vtable receive 派发）
    # ------------------------------------------------------------------ #

    def store(self, key: IbObject, value: IbObject, check: IbObject,
              provenance: Optional[IbObject] = None) -> IbObject:
        """登记（首次写入）：引擎求值 check(value) 过门 + 深克隆快照。

        键已存在 = 错误（"登记"与"更正"机器强制区分，更正走 amend）。
        ``provenance``（可选）= 来源标记（知识出处：模块/文件/采集轮次等），
        入条目 + 经 export/history 可观测（审计"知识从哪来"）。
        """
        k = unbox(key)
        if not isinstance(k, str) or not k:
            raise InterpreterError(
                "knowledge.store 键须为非空 str",
                error_code=KNW_KEY_EXISTS,
            )
        entries = self._entries()
        if k in entries:
            raise InterpreterError(
                f"knowledge.store 键 '{k}' 已登记（登记与更正机器强制区分，"
                f"更正走 amend）。",
                error_code=KNW_KEY_EXISTS,
            )
        # 验证门：引擎求值 check(value)（假 = 拒绝登记）
        snapshot = _clone_snapshot(value)
        result = check.receive("__call__", [snapshot])
        if not result.to_native():
            raise InterpreterError(
                f"knowledge.store 键 '{k}' 未过验证门 check(value) 为假，拒绝登记。",
                error_code=KNW_CHECK_REJECTED,
            )
        seq = self._next_seq()
        prov = unbox(provenance) if provenance is not None else ""
        if not isinstance(prov, str):
            prov = str(prov)
        entries[k] = {
            "value": snapshot,
            "check": check,  # 谓词引用（同进程/会话内 amend 再过门复用；
                             # 序列化恢复后为 None——amend fail-fast，见 KNW_ 边界）
            "check_name": self._check_name(check),
            "provenance": prov,
            "events": [
                {"seq": seq, "kind": "store", "value": snapshot, "reason": ""}
            ],
        }
        return self.ib_class.registry.get_none()

    def get(self, key: IbObject) -> IbObject:
        """查询当前值：未登记 → null（合法状态非错误）；返回深克隆快照。"""
        k = unbox(key)
        entries = self._entries()
        if not isinstance(k, str) or k not in entries:
            return self.ib_class.registry.get_none()
        return _clone_snapshot(entries[k]["value"])

    def amend(self, key: IbObject, new_value: IbObject, reason: IbObject) -> IbObject:
        """更正：reason 强制非空 + 新值再过 check 门 + append-only 事件。"""
        k = unbox(key)
        entries = self._entries()
        if not isinstance(k, str) or k not in entries:
            raise InterpreterError(
                f"knowledge.amend 键 '{k}' 未登记（更正仅适用于已登记条目）。",
                error_code=KNW_REASON_EMPTY,
            )
        r = unbox(reason)
        if not isinstance(r, str) or not r.strip():
            raise InterpreterError(
                "knowledge.amend 理由（reason）强制非空（审计链完整性）。",
                error_code=KNW_REASON_EMPTY,
            )
        entry = entries[k]
        # 新值再过 check 门（防更正通道变无门控写口）
        check_obj = self._resolve_check(entry)
        if check_obj is None:
            raise InterpreterError(
                f"knowledge.amend 键 '{k}' 的验证谓词引用不可用"
                f"（跨 save/load 恢复后谓词引用丢失——须重新 store 登记）。",
                error_code=KNW_CHECK_REJECTED,
            )
        snapshot = _clone_snapshot(new_value)
        result = check_obj.receive("__call__", [snapshot])
        if not result.to_native():
            raise InterpreterError(
                f"knowledge.amend 键 '{k}' 新值未过验证门，拒绝更正。",
                error_code=KNW_CHECK_REJECTED,
            )
        seq = self._next_seq()
        entry["events"].append(
            {"seq": seq, "kind": "amend", "value": snapshot, "reason": r}
        )
        entry["value"] = snapshot
        return self.ib_class.registry.get_none()

    def history(self, key: IbObject, kind: Optional[IbObject] = None) -> IbObject:
        """审计：事件序列 list（{seq, kind, value, reason}）；未登记 → 空 list。

        ``kind``（可选）= 事件类型过滤（"store"/"amend"）；缺省/空 = 全事件。
        """
        k = unbox(key)
        entries = self._entries()
        reg = self.ib_class.registry
        if not isinstance(k, str) or k not in entries:
            return reg.box([])
        kind_filter = unbox(kind) if kind is not None else ""
        if not isinstance(kind_filter, str):
            kind_filter = ""
        events = [
            ev for ev in entries[k]["events"]
            if not kind_filter or ev["kind"] == kind_filter
        ]
        out: List[Any] = []
        for ev in events:
            d = reg.box({})
            # 事件 dict 逐字段装配（值 = 快照深克隆，防审计链引用污染）
            d.receive("__setitem__", [reg.box(f"seq"), reg.box(ev["seq"])])
            d.receive("__setitem__", [reg.box(f"kind"), reg.box(ev["kind"])])
            d.receive("__setitem__", [reg.box(f"value"), _clone_snapshot(ev["value"])])
            d.receive("__setitem__", [reg.box(f"reason"), reg.box(ev["reason"])])
            out.append(d)
        return reg.box(out)

    def keys(self) -> IbObject:
        """枚举键（list[str]；dict 容器约定同构）。"""
        reg = self.ib_class.registry
        return reg.box(list(self._entries().keys()))

    def len(self) -> IbObject:
        """计数（dict 容器约定同构）。"""
        return self.ib_class.registry.box(len(self._entries()))

    def export(self) -> IbObject:
        """全注册表导出（dict 容器约定之外的整库检视面）。

        返回 ``dict``：键 → ``{value, check_name, provenance, events}``，
        events = ``[{seq, kind, value, reason}]``（append-only 审计链全量）。
        供整库序列化/检视/迁移（逐键 get+history 的批量替代）。值 = 快照深
        克隆（防导出引用污染活库）。
        """
        reg = self.ib_class.registry
        out = reg.box({})
        for k, entry in self._entries().items():
            rec = reg.box({})
            rec.receive("__setitem__", [reg.box("value"), _clone_snapshot(entry["value"])])
            rec.receive("__setitem__", [reg.box("check_name"), reg.box(entry.get("check_name", ""))])
            rec.receive("__setitem__", [reg.box("provenance"), reg.box(entry.get("provenance", ""))])
            evs: List[Any] = []
            for ev in entry["events"]:
                d = reg.box({})
                d.receive("__setitem__", [reg.box("seq"), reg.box(ev["seq"])])
                d.receive("__setitem__", [reg.box("kind"), reg.box(ev["kind"])])
                d.receive("__setitem__", [reg.box("value"), _clone_snapshot(ev["value"])])
                d.receive("__setitem__", [reg.box("reason"), reg.box(ev["reason"])])
                evs.append(d)
            rec.receive("__setitem__", [reg.box("events"), reg.box(evs)])
            out.receive("__setitem__", [reg.box(k), rec])
        return out

    # ------------------------------------------------------------------ #
    # 内部辅助
    # ------------------------------------------------------------------ #

    @staticmethod
    def _check_name(check: IbObject) -> str:
        """登记时验证谓词名/引用（审计"经谁验证"）。"""
        cls = getattr(check, "ib_class", None)
        if cls is not None and getattr(cls, "name", None):
            return str(cls.name)
        return "unknown"

    def _resolve_check(self, entry: Dict[str, Any]) -> Any:
        """解析条目的验证谓词引用（amend 再过门）。

        登记时保留谓词对象引用（同进程/会话内复用）；序列化/水化恢复后
        引用丢失（函数非值快照）→ 返回 None（amend 调用点 fail-fast，
        要求重新 store——边界文档化）。
        """
        return entry.get("check")

    # ------------------------------------------------------------------ #
    # 值对象协议面
    # ------------------------------------------------------------------ #

    def to_native(self, memo=None) -> Any:
        # 知识库 = 可变容器值对象：原生表征 = 条目结构（序列化/边界消费；
        # 谓词引用不拆箱（函数非值快照），仅审计名）
        return {
            "entries": {
                k: {
                    "value": v["value"].to_native(memo),
                    "check_name": v["check_name"],
                    "provenance": v.get("provenance", ""),
                }
                for k, v in self._entries().items()
            },
            "seq": self.payload["seq"],
        }

    def serialize_for_debug(self):
        entries = self._entries()
        return {
            "type": "knowledge",
            "len": len(entries),
            "keys": list(entries.keys())[:8],
            "seq": self.payload["seq"],
        }

    def __repr__(self):
        return f"knowledge(len={len(self._entries())}, seq={self.payload['seq']})"

    def cast_to(self, target_class) -> IbObject:
        if target_class.name in ("knowledge", "any"):
            return self
        if target_class.name == "str":
            return self.ib_class.registry.box(repr(self))
        raise InterpreterError(
            f"TypeError: Cannot cast 'knowledge' to '{target_class.name}' "
            f"(str/any 转换受支持)。",
            error_code=KNW_CHECK_REJECTED,
        )
