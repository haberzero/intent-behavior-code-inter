"""
core/runtime/objects/primitives/memory.py

IbMemory —— 层级记忆基底值对象（一等内置值类型）。

Round4 MEM 需求：把 LLM 上下文当高速内存，把 ibci 记忆当等效记忆窗口（近无限）。
定位类比 = in-language hierarchical memory store（分层/生命周期/可遗忘/可审计）。

语义契约（设计裁定见 tasks_docs/_round4_mem_rec_design.md §二）：

- **记忆对象 = 可变值对象**（引用语义，同 dict/knowledge）；
  **条目值 = 冻结快照**（encode 入时深克隆 + retrieve 出时深克隆）。
- **分层**：working_set / session / knowledge / long_term，每层有容量+条目数。
- **层级操作**：promote/demote 为一等确定性操作。
- **生命周期**：encode（登记）/ consolidate（巩固）/ prune（遗忘）。
- **完整性**：content_hash（SHA-256）+ provenance + append-only events。
- **铁律**：一切记忆操作 = 显式程序操作（普通值方法调用）。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from core.base.diagnostics.codes import (
    MEM_KEY_EXISTS,
    MEM_TIER_FULL,
    MEM_TIER_UNKNOWN,
    MEM_KEY_NOT_FOUND,
)
from core.kernel.issue import InterpreterError
from core.runtime.objects.kernel import IbObject, IbValue
from core.runtime.objects.kernel.base import unbox
from core.runtime.objects.deep_clone import try_deep_clone
from core.runtime.objects.ib_type_mapping import register_ib_type

# 合法层名（固定集，非用户可扩展）
VALID_TIERS = ("working_set", "session", "knowledge", "long_term")

# 默认容量（None = 无界）
_DEFAULT_CAPACITY: Dict[str, Optional[int]] = {
    "working_set": 16,
    "session": 128,
    "knowledge": None,
    "long_term": None,
}


def _clone_snapshot(value: IbObject) -> IbObject:
    """深克隆冻结快照（同 knowledge 先例）。"""
    cloned = try_deep_clone(value)
    if cloned is None:
        name = getattr(value.ib_class, "name", "?") if getattr(value, "ib_class", None) else "?"
        raise InterpreterError(
            f"memory: 条目值类型 '{name}' 不可深克隆，拒绝登记。",
            error_code=MEM_KEY_EXISTS,
        )
    return cloned


def _content_hash(value: IbObject) -> str:
    """条目内容哈希（SHA-256，tamper-evident）。"""
    try:
        native = value.to_native()
        canonical = json.dumps(native, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    except Exception:
        return "unhashable"


@register_ib_type("memory")
class IbMemory(IbValue):
    """层级记忆基底。``payload`` = ``{"tiers": {tier_name: {key: entry}}, "seq": int, "capacities": {tier: int|None}}``。"""

    __slots__ = ()

    @classmethod
    def _create_blank(cls, ib_class: "IbObject") -> "IbMemory":
        return cls(ib_class)

    def __init__(self, ib_class: "IbObject", payload: Any = None):
        if payload is None:
            payload = {
                "tiers": {t: {} for t in VALID_TIERS},
                "seq": 0,
                "capacities": dict(_DEFAULT_CAPACITY),
            }
        super().__init__(ib_class, payload=payload)

    # ------------------------------------------------------------------ #
    # 内部结构
    # ------------------------------------------------------------------ #

    def _tiers(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        return self.payload["tiers"]

    def _capacities(self) -> Dict[str, Optional[int]]:
        return self.payload["capacities"]

    def _next_seq(self) -> int:
        self.payload["seq"] += 1
        return self.payload["seq"]

    def _find_entry(self, key: str) -> Optional[tuple]:
        """查找键在哪个层（返回 (tier, entry) 或 None）。"""
        for tier in VALID_TIERS:
            if key in self._tiers()[tier]:
                return tier, self._tiers()[tier][key]
        return None

    def _check_capacity(self, tier: str) -> None:
        """容量检查（满 = fail-fast，不静默溢出）。"""
        cap = self._capacities().get(tier)
        if cap is not None and len(self._tiers()[tier]) >= cap:
            raise InterpreterError(
                f"memory: 层 '{tier}' 已满（容量 {cap}），拒绝写入。"
                f"请先 prune 或 demote 腾出空间。",
                error_code=MEM_TIER_FULL,
            )

    # ------------------------------------------------------------------ #
    # 方法面
    # ------------------------------------------------------------------ #

    def encode(self, key: IbObject, value: IbObject, tier: IbObject,
               provenance: Optional[IbObject] = None) -> IbObject:
        """登记新条目（深克隆快照 + 内容哈希 + provenance）。

        键已存在 = 错误（与 knowledge.store 同语义——重复登记须先删或走其它层）。
        ``tier``：目标层名（str：working_set/session/knowledge/long_term）。
        """
        k = unbox(key)
        t = unbox(tier)
        if not isinstance(k, str) or not k:
            raise InterpreterError("memory.encode 键须为非空 str", error_code=MEM_KEY_EXISTS)
        if not isinstance(t, str) or t not in VALID_TIERS:
            raise InterpreterError(
                f"memory.encode 层须为 {VALID_TIERS} 之一（收到 {t!r}）",
                error_code=MEM_TIER_UNKNOWN,
            )
        if self._find_entry(k) is not None:
            raise InterpreterError(
                f"memory.encode 键 '{k}' 已存在（重复登记拒绝）。",
                error_code=MEM_KEY_EXISTS,
            )
        self._check_capacity(t)
        snapshot = _clone_snapshot(value)
        seq = self._next_seq()
        prov = unbox(provenance) if provenance is not None else ""
        if not isinstance(prov, str):
            prov = str(prov)
        self._tiers()[t][k] = {
            "value": snapshot,
            "content_hash": _content_hash(snapshot),
            "provenance": prov,
            "events": [{"seq": seq, "kind": "encode", "reason": ""}],
        }
        return self.ib_class.registry.get_none()

    def retrieve(self, key: IbObject) -> IbObject:
        """查询当前值（跨层查找；未登记 → null）。"""
        k = unbox(key)
        found = self._find_entry(k)
        if found is None:
            return self.ib_class.registry.get_none()
        return _clone_snapshot(found[1]["value"])

    def promote(self, key: IbObject, to_tier: IbObject) -> IbObject:
        """提升条目到更高层。"""
        k = unbox(key)
        target = unbox(to_tier)
        if not isinstance(target, str) or target not in VALID_TIERS:
            raise InterpreterError(
                f"memory.promote 目标层须为 {VALID_TIERS} 之一",
                error_code=MEM_TIER_UNKNOWN,
            )
        found = self._find_entry(k)
        if found is None:
            raise InterpreterError(
                f"memory.promote 键 '{k}' 未登记。",
                error_code=MEM_KEY_NOT_FOUND,
            )
        src_tier, entry = found
        if src_tier == target:
            return self.ib_class.registry.get_none()  # no-op
        self._check_capacity(target)
        # 从源层移除，写入目标层
        del self._tiers()[src_tier][k]
        self._tiers()[target][k] = entry
        seq = self._next_seq()
        entry["events"].append({"seq": seq, "kind": "promote", "reason": f"{src_tier}→{target}"})
        return self.ib_class.registry.get_none()

    def demote(self, key: IbObject, to_tier: IbObject) -> IbObject:
        """降级条目到更低层。"""
        return self.promote(key, to_tier)  # 机制同构（方向由调用方决定）

    def tier(self, key: IbObject) -> IbObject:
        """查询条目所在层（未登记 → null）。"""
        k = unbox(key)
        found = self._find_entry(k)
        if found is None:
            return self.ib_class.registry.get_none()
        return self.ib_class.registry.box(found[0])

    def tier_size(self, tier: IbObject) -> IbObject:
        """某层条目数。"""
        t = unbox(tier)
        if not isinstance(t, str) or t not in VALID_TIERS:
            raise InterpreterError(
                f"memory.tier_size 层须为 {VALID_TIERS} 之一",
                error_code=MEM_TIER_UNKNOWN,
            )
        return self.ib_class.registry.box(len(self._tiers()[t]))

    def tier_keys(self, tier: IbObject) -> IbObject:
        """某层所有键（list[str]）。"""
        t = unbox(tier)
        if not isinstance(t, str) or t not in VALID_TIERS:
            raise InterpreterError(
                f"memory.tier_keys 层须为 {VALID_TIERS} 之一",
                error_code=MEM_TIER_UNKNOWN,
            )
        return self.ib_class.registry.box(list(self._tiers()[t].keys()))

    def set_capacity(self, tier: IbObject, n: IbObject) -> IbObject:
        """设置层容量上限（None/负数 = 无界）。"""
        t = unbox(tier)
        cap = unbox(n)
        if not isinstance(t, str) or t not in VALID_TIERS:
            raise InterpreterError(
                f"memory.set_capacity 层须为 {VALID_TIERS} 之一",
                error_code=MEM_TIER_UNKNOWN,
            )
        if cap is None or (isinstance(cap, int) and cap < 0):
            self._capacities()[t] = None
        elif isinstance(cap, int):
            self._capacities()[t] = cap
        else:
            raise InterpreterError(
                "memory.set_capacity n 须为 int 或 null（null=无界）",
                error_code=MEM_TIER_UNKNOWN,
            )
        return self.ib_class.registry.get_none()

    def keys(self) -> IbObject:
        """全部键（跨层，list[str]）。"""
        all_keys: List[str] = []
        for t in VALID_TIERS:
            all_keys.extend(self._tiers()[t].keys())
        return self.ib_class.registry.box(all_keys)

    def len(self) -> IbObject:
        """全部条目数（跨层）。"""
        return self.ib_class.registry.box(sum(len(self._tiers()[t]) for t in VALID_TIERS))

    def content_hash(self, key: IbObject) -> IbObject:
        """条目内容哈希（tamper-evident 校验面）。"""
        k = unbox(key)
        found = self._find_entry(k)
        if found is None:
            raise InterpreterError(
                f"memory.content_hash 键 '{k}' 未登记。",
                error_code=MEM_KEY_NOT_FOUND,
            )
        return self.ib_class.registry.box(found[1]["content_hash"])

    def verify(self, key: IbObject) -> IbObject:
        """验证条目完整性（重算哈希 vs 存储哈希）。"""
        k = unbox(key)
        found = self._find_entry(k)
        if found is None:
            return self.ib_class.registry.box(False)
        entry = found[1]
        current_hash = _content_hash(entry["value"])
        return self.ib_class.registry.box(current_hash == entry["content_hash"])

    def export(self) -> IbObject:
        """全记忆导出（dict：tier → {key: {value, content_hash, provenance, events}}）。"""
        reg = self.ib_class.registry
        out = reg.box({})
        for t in VALID_TIERS:
            tier_dict = reg.box({})
            for k, entry in self._tiers()[t].items():
                rec = reg.box({})
                rec.receive("__setitem__", [reg.box("value"), _clone_snapshot(entry["value"])])
                rec.receive("__setitem__", [reg.box("content_hash"), reg.box(entry["content_hash"])])
                rec.receive("__setitem__", [reg.box("provenance"), reg.box(entry.get("provenance", ""))])
                tier_dict.receive("__setitem__", [reg.box(k), rec])
            out.receive("__setitem__", [reg.box(t), tier_dict])
        return out

    # ------------------------------------------------------------------ #
    # 值对象协议面
    # ------------------------------------------------------------------ #

    def to_native(self, memo=None) -> Any:
        return {
            "tiers": {
                t: {
                    k: {
                        "value": v["value"].to_native(memo),
                        "content_hash": v["content_hash"],
                        "provenance": v.get("provenance", ""),
                    }
                    for k, v in self._tiers()[t].items()
                }
                for t in VALID_TIERS
            },
            "seq": self.payload["seq"],
            "capacities": self._capacities(),
        }

    def serialize_for_debug(self):
        return {
            "type": "memory",
            "total": self.len().to_native(),
            "tiers": {t: len(self._tiers()[t]) for t in VALID_TIERS},
            "seq": self.payload["seq"],
        }

    def __repr__(self):
        sizes = {t: len(self._tiers()[t]) for t in VALID_TIERS}
        return f"memory({sizes})"

    def cast_to(self, target_class) -> IbObject:
        if target_class.name in ("memory", "any"):
            return self
        if target_class.name == "str":
            return self.ib_class.registry.box(repr(self))
        raise InterpreterError(
            f"TypeError: Cannot cast 'memory' to '{target_class.name}'",
            error_code=MEM_TIER_UNKNOWN,
        )
