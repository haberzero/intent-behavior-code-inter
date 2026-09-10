"""
core/runtime/objects/primitives/knowledge.py

IbKnowledge —— 已验证知识注册表值对象（一等内置值类型）。

语言自动机的知识层（D 纸带）：机器持有的知识是**类型化、门控、可审计**的。
定位类比 = in-language knowledge database（持久/结构化/门控/可审计/可查询）。

payload = 三个正交数据面 + 派生索引（单点真理：日志是权威，索引是视图）：

- **entries**（通用知识登记面）：key → {value, check, check_name, provenance,
  events}——既有契约（store/get/amend/history，调用方 check 谓词门）。
- **facts**（世界模型事实日志）：fact_id → {id, world, s, r, o, source, status,
  events}——append-only 三元组事实（KB 单一权威源；内建治理门：world/relation/
  s/o 须已注册词表项，确定性零 LLM）。
- **vocab**（治理词表）：words/relations/worlds 的 allowlist 记录（KB 元规则；
  关系的 transitive/multi_valued 元数据支撑传递闭包与矛盾判定）。
- **indexes**（8 倒排索引）：**派生面**——增量维护 + 构造/水化时从 facts 重建，
  永不独立序列化（6 图索引 = active 视图；by_source/by_status = 全日志视图）。
- **seq** = KB 单一审计序号（引擎单调序号，非墙钟）：entries 事件与 facts 事件
  同序；fact_id = str(seq)（确定性可复现）。

语义契约（设计裁定 K1-K9 + KB 面）：

- **知识库对象 = 可变值对象**（引用语义，同 dict——可共享/可传参/可进
  save_state）；**条目值 = 冻结快照**（store 入时深克隆 + get 出时深克隆——
  "知识库可变，知识不可变"，防引用陷阱污染审计）。
- **验证门**：store 时引擎求值 ``check(value)``——假 = fail-fast
  （KNW_CHECK_REJECTED，未过验证门拒绝登记）；check 含 LLM 调用/不透明 =
  编译期 SEM 错误（SEM_KNW_*，fail-fast：不纯度不可证明即拒绝）。
- **facts 准入 = 内建治理门**（词表 allowlist 机器强制，零 LLM）：world/
  relation/s/o 未注册 = KNW_VOCAB_UNREGISTERED；重复 active 事实 =
  KNW_FACT_DUPLICATE（去重机器强制；更正是 amend_fact，废止是 retract）。
- **更正语义**：amend append-only（原值保留事件流，当前值指针切换）+
  reason 强制非空 + 新值再过 check 门（防更正通道变无门控写口）；facts 面同
  纪律（amend_fact 版本化 + retract 墓碑，reason 强制）。
- **审计形态**：事件序号 = 引擎单调序号（非墙钟，确定性可复现）；
  history 事件 list（{seq, kind, value, reason}）；未登记 = 空 list。
- **铁律**：一切知识操作 = 显式程序操作（普通值方法调用）——引擎不提供
  任何"查表命中则跳过 LLM"的隐式路由（@~...~ 语义不变量）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.base.diagnostics.codes import (
    KNW_CHECK_REJECTED,
    KNW_FACT_DUPLICATE,
    KNW_FACT_NOT_FOUND,
    KNW_FACT_RETRACTED,
    KNW_KEY_EXISTS,
    KNW_REASON_EMPTY,
    KNW_VOCAB_EXISTS,
    KNW_VOCAB_MALFORMED,
    KNW_VOCAB_UNREGISTERED,
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
        # payload 不变量：三数据面齐备 + 派生索引从事实日志重建（构造入口即
        # 归一——水化/克隆/空白构造全经本入口，索引永不跨构造存活）。
        payload.setdefault("entries", {})
        payload.setdefault("facts", {})
        payload.setdefault("vocab", self._blank_vocab())
        payload["indexes"] = self._build_indexes_from_facts(payload["facts"])
        super().__init__(ib_class, payload=payload)

    # ------------------------------------------------------------------ #
    # 内部结构访问（单一权威：payload 结构）
    # ------------------------------------------------------------------ #

    def _entries(self) -> Dict[str, Dict[str, Any]]:
        return self.payload["entries"]

    def _facts(self) -> Dict[str, Dict[str, Any]]:
        return self.payload["facts"]

    def _vocab(self) -> Dict[str, Dict[str, Any]]:
        return self.payload["vocab"]

    def _indexes(self) -> Dict[str, Any]:
        return self.payload["indexes"]

    def _next_seq(self) -> int:
        self.payload["seq"] += 1
        return self.payload["seq"]

    # ------------------------------------------------------------------ #
    # 派生索引（8 倒排：日志是权威，索引是视图——构造/水化重建 + 增量维护）
    # ------------------------------------------------------------------ #

    @staticmethod
    def _blank_vocab() -> Dict[str, Dict[str, Any]]:
        return {"words": {}, "relations": {}, "worlds": {}}

    @staticmethod
    def _build_indexes_from_facts(facts: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """从事实日志确定性重建 8 索引（水化/克隆/构造入口共用——单一重建源）。

        6 图索引 = **active 视图**（status == "active" 的事实）；by_source /
        by_status = **全日志视图**（含墓碑）。序 = fact_id（seq）升序（确定性）。
        """
        idx: Dict[str, Any] = {
            "by_subject": {}, "by_object": {}, "by_relation": {},
            "by_pair": {}, "by_triple": {}, "by_world": {},
            "by_source": {}, "by_status": {},
        }
        for fid in sorted(facts, key=lambda x: int(x)):
            f = facts[fid]
            if f["status"] == "active":
                IbKnowledge._index_insert(idx, f)
            idx["by_source"].setdefault(f["source"], []).append(fid)
            idx["by_status"].setdefault(f["status"], []).append(fid)
        return idx

    @staticmethod
    def _index_insert(idx: Dict[str, Any], f: Dict[str, Any]) -> None:
        """图索引增量插入（active 事实登记/版本切换后调用）。"""
        fid, s, r, o, w = f["id"], f["s"], f["r"], f["o"], f["world"]
        idx["by_subject"].setdefault(s, []).append(fid)
        idx["by_object"].setdefault(o, []).append(fid)
        idx["by_relation"].setdefault(r, []).append(fid)
        idx["by_pair"].setdefault(s, {}).setdefault(r, []).append(fid)
        idx["by_triple"].setdefault(w, {}).setdefault(s, {}).setdefault(r, {}).setdefault(o, []).append(fid)
        idx["by_world"].setdefault(w, []).append(fid)

    @staticmethod
    def _index_remove_graph(idx: Dict[str, Any], f: Dict[str, Any]) -> None:
        """图索引增量移除（墓碑/版本切换时；仅 6 图索引——审计索引全日志）。"""
        fid, s, r, o, w = f["id"], f["s"], f["r"], f["o"], f["world"]
        for section, key in (("by_subject", s), ("by_object", o),
                             ("by_relation", r), ("by_world", w)):
            lst = idx[section].get(key)
            if lst and fid in lst:
                lst.remove(fid)
        pair = idx["by_pair"].get(s, {}).get(r)
        if pair and fid in pair:
            pair.remove(fid)
        tri = idx["by_triple"].get(w, {}).get(s, {}).get(r, {}).get(o)
        if tri and fid in tri:
            tri.remove(fid)

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
    # 词表面（治理 allowlist——KB 元规则；全确定性零 LLM）
    # ------------------------------------------------------------------ #

    def register_word(self, lexeme: IbObject, gloss: IbObject, is_set: IbObject,
                      members: Optional[IbObject] = None,
                      entries: Optional[IbObject] = None) -> Any:
        """注册词（治理词表 words 面）。

        ``members``（缺省 []）= 集合词成员；``entries``（缺省 {}）= 跨世界词形
        ``{world: {form, self_ref}}``（跨尺度自指：同一词在不同世界的呈现 +
        尺度相对指涉）。词表重复注册 = fail-fast（KNW_VOCAB_EXISTS——词表是
        单一权威源，更正归调用方治理流程，KB 值面只有登记）。
        """
        lex = unbox(lexeme)
        gl = unbox(gloss)
        ist = unbox(is_set)
        if (not isinstance(lex, str) or not lex or not isinstance(gl, str)
                or not isinstance(ist, bool)):
            raise InterpreterError(
                "knowledge.register_word 参数须为 (lexeme: 非空 str, gloss: str, "
                "is_set: bool)。",
                error_code=KNW_VOCAB_MALFORMED,
            )
        mem = unbox(members) if members is not None else []
        ent = unbox(entries) if entries is not None else {}
        if not isinstance(mem, list) or not isinstance(ent, dict):
            raise InterpreterError(
                "knowledge.register_word members 须为 list、entries 须为 dict"
                "（{world: {form, self_ref}}）。",
                error_code=KNW_VOCAB_MALFORMED,
            )
        words = self._vocab()["words"]
        if lex in words:
            raise InterpreterError(
                f"knowledge.register_word 词 '{lex}' 已注册（词表单一权威源，"
                f"重复登记拒绝）。",
                error_code=KNW_VOCAB_EXISTS,
            )
        words[lex] = {
            "lexeme": lex, "gloss": gl, "is_set": ist,
            "members": mem, "entries": ent,
        }
        return None

    def register_relation(self, relation_type: IbObject, semantics: IbObject,
                          transitive: IbObject, multi_valued: IbObject) -> Any:
        """注册关系类型（治理词表 relations 面）。

        ``transitive`` = 传递性（传递闭包的元数据）；``multi_valued`` = 多值性
        （矛盾判定的元数据：同 (s,r) 允许多 o 当且仅当 multi_valued）。
        """
        rt = unbox(relation_type)
        sem = unbox(semantics)
        tr = unbox(transitive)
        mv = unbox(multi_valued)
        if (not isinstance(rt, str) or not rt or not isinstance(sem, str)
                or not isinstance(tr, bool) or not isinstance(mv, bool)):
            raise InterpreterError(
                "knowledge.register_relation 参数须为 (type: 非空 str, "
                "semantics: str, transitive: bool, multi_valued: bool)。",
                error_code=KNW_VOCAB_MALFORMED,
            )
        relations = self._vocab()["relations"]
        if rt in relations:
            raise InterpreterError(
                f"knowledge.register_relation 关系类型 '{rt}' 已注册（词表单一"
                f"权威源，重复登记拒绝）。",
                error_code=KNW_VOCAB_EXISTS,
            )
        relations[rt] = {
            "type": rt, "semantics": sem,
            "transitive": tr, "multi_valued": mv,
        }
        return None

    def register_world(self, name: IbObject, description: IbObject,
                       size_rank: IbObject) -> Any:
        """注册世界（治理词表 worlds 面）。``size_rank`` = 尺度秩（跨尺度
        对比/自指的元数据）。"""
        n = unbox(name)
        d = unbox(description)
        sr = unbox(size_rank)
        if (not isinstance(n, str) or not n or not isinstance(d, str)
                or not isinstance(sr, int) or isinstance(sr, bool)):
            raise InterpreterError(
                "knowledge.register_world 参数须为 (name: 非空 str, "
                "description: str, size_rank: int)。",
                error_code=KNW_VOCAB_MALFORMED,
            )
        worlds = self._vocab()["worlds"]
        if n in worlds:
            raise InterpreterError(
                f"knowledge.register_world 世界 '{n}' 已注册（词表单一权威源，"
                f"重复登记拒绝）。",
                error_code=KNW_VOCAB_EXISTS,
            )
        worlds[n] = {"name": n, "description": d, "size_rank": sr}
        return None

    def word(self, lexeme: IbObject) -> Any:
        """词表查询（words 面）：未注册 = null（合法态非错误）。"""
        lex = unbox(lexeme)
        if not isinstance(lex, str):
            raise InterpreterError(
                "knowledge.word 参数须为 str。",
                error_code=KNW_VOCAB_MALFORMED,
            )
        return self._vocab()["words"].get(lex)

    def relation(self, relation_type: IbObject) -> Any:
        """词表查询（relations 面）：未注册 = null（合法态非错误）。"""
        rt = unbox(relation_type)
        if not isinstance(rt, str):
            raise InterpreterError(
                "knowledge.relation 参数须为 str。",
                error_code=KNW_VOCAB_MALFORMED,
            )
        return self._vocab()["relations"].get(rt)

    def world(self, name: IbObject) -> Any:
        """词表查询（worlds 面）：未注册 = null（合法态非错误）。"""
        n = unbox(name)
        if not isinstance(n, str):
            raise InterpreterError(
                "knowledge.world 参数须为 str。",
                error_code=KNW_VOCAB_MALFORMED,
            )
        return self._vocab()["worlds"].get(n)

    def words(self) -> Any:
        """已注册词名枚举（list[str]，确定性序 = 插入序）。"""
        return list(self._vocab()["words"].keys())

    def relations(self) -> Any:
        """已注册关系类型名枚举（list[str]，确定性序 = 插入序）。"""
        return list(self._vocab()["relations"].keys())

    def worlds(self) -> Any:
        """已注册世界名枚举（list[str]，确定性序 = 插入序）。"""
        return list(self._vocab()["worlds"].keys())

    # ------------------------------------------------------------------ #
    # 事实面（append-only 事实日志——KB 单一权威源；内建治理门）
    # ------------------------------------------------------------------ #

    def add_fact(self, world: IbObject, s: IbObject, r: IbObject,
                 o: IbObject, source: Optional[IbObject] = None,
                 status: Optional[IbObject] = None) -> Any:
        """登记三元组事实（facts 面），返回 fact_id（= str(KB seq)，确定性）。

        **内建治理门**（单一准入面，机器强制，零 LLM）：world/relation/s/o
        全部须已注册词表项（KNW_VOCAB_UNREGISTERED）；同 (world,s,r,o) 已有
        active 事实 = 重复（KNW_FACT_DUPLICATE——去重机器强制；更正是
        amend_fact，废止是 retract）。``source``（缺省 ""）= 来源标记；
        ``status``（缺省 "active"）= 状态标记（"active"/"retracted" 惯例）。
        图索引仅收 active 事实；审计索引（by_source/by_status）全日志。
        """
        w = unbox(world)
        subj = unbox(s)
        rel = unbox(r)
        obj = unbox(o)
        src = unbox(source) if source is not None else ""
        st = unbox(status) if status is not None else "active"
        for name, val in (("world", w), ("s", subj), ("r", rel), ("o", obj)):
            if not isinstance(val, str) or not val:
                raise InterpreterError(
                    f"knowledge.add_fact {name} 须为非空 str。",
                    error_code=KNW_VOCAB_MALFORMED,
                )
        if not isinstance(src, str) or not isinstance(st, str) or not st:
            raise InterpreterError(
                "knowledge.add_fact source/status 须为 str（status 非空）。",
                error_code=KNW_VOCAB_MALFORMED,
            )
        # 治理门：词表 allowlist（确定性，零 LLM）
        vocab = self._vocab()
        if w not in vocab["worlds"]:
            raise InterpreterError(
                f"knowledge.add_fact 世界 '{w}' 未注册（先 register_world）。",
                error_code=KNW_VOCAB_UNREGISTERED,
            )
        if rel not in vocab["relations"]:
            raise InterpreterError(
                f"knowledge.add_fact 关系类型 '{rel}' 未注册（先 register_relation）。",
                error_code=KNW_VOCAB_UNREGISTERED,
            )
        if subj not in vocab["words"]:
            raise InterpreterError(
                f"knowledge.add_fact 主语 '{subj}' 未注册为词（先 register_word）。",
                error_code=KNW_VOCAB_UNREGISTERED,
            )
        if obj not in vocab["words"]:
            raise InterpreterError(
                f"knowledge.add_fact 对象 '{obj}' 未注册为词（先 register_word）。",
                error_code=KNW_VOCAB_UNREGISTERED,
            )
        # 去重门：同 (world,s,r,o) active 事实机器强制唯一
        triple = (self._indexes()["by_triple"].get(w, {})
                  .get(subj, {}).get(rel, {}).get(obj))
        if triple:
            raise InterpreterError(
                f"knowledge.add_fact 事实 ({w}, {subj}, {rel}, {obj}) 已有 active "
                f"登记（重复拒绝；更正走 amend_fact，废止走 retract）。",
                error_code=KNW_FACT_DUPLICATE,
            )
        seq = self._next_seq()
        fid = str(seq)
        fact = {
            "id": fid, "world": w, "s": subj, "r": rel, "o": obj,
            "source": src, "status": st,
            "events": [{"seq": seq, "kind": "add", "reason": "", "new_o": None}],
        }
        self._facts()[fid] = fact
        idx = self._indexes()
        if st == "active":
            self._index_insert(idx, fact)
        idx["by_source"].setdefault(src, []).append(fid)
        idx["by_status"].setdefault(st, []).append(fid)
        return fid

    def get_fact(self, fact_id: IbObject) -> Any:
        """事实记录查询（权威形态含全事件链）：未知 id / 非 str = null 或
        fail-fast（KB 是唯一权威读取口——调用方不自持 fact dict）。"""
        fid = unbox(fact_id)
        if not isinstance(fid, str):
            raise InterpreterError(
                "knowledge.get_fact fact_id 须为 str。",
                error_code=KNW_FACT_NOT_FOUND,
            )
        return self._facts().get(fid)

    def facts(self) -> Any:
        """全日志（含 retracted 墓碑，status 字段自辨；确定性序 = seq 序）。"""
        return [self._facts()[k] for k in sorted(self._facts(), key=lambda x: int(x))]

    def fact_len(self) -> Any:
        """事实计数（全日志，含墓碑）。"""
        return len(self._facts())

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
        # 知识库 = 可变容器值对象：原生表征 = 三数据面快照（序列化/边界消费；
        # entries 谓词引用不拆箱（函数非值快照），仅审计名；facts/vocab 全
        # 原生结构，结构化快照防边界共享变异；索引为派生面——不入原生表征）
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
            "facts": self._facts_snapshot(),
            "vocab": self._vocab_snapshot(),
        }

    def _facts_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """facts 面结构化快照（记录 + 事件链拷贝——边界不共享内部引用）。"""
        return {
            fid: {**f, "events": [dict(e) for e in f["events"]]}
            for fid, f in self._facts().items()
        }

    def _vocab_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """vocab 面结构化快照（词/关系/世界记录拷贝，含嵌套词形表）。"""
        vocab = self._vocab()
        return {
            "words": {
                k: {
                    **v,
                    "members": list(v["members"]),
                    "entries": {wk: dict(wv) for wk, wv in v["entries"].items()},
                }
                for k, v in vocab["words"].items()
            },
            "relations": {k: dict(v) for k, v in vocab["relations"].items()},
            "worlds": {k: dict(v) for k, v in vocab["worlds"].items()},
        }

    def serialize_for_debug(self):
        entries = self._entries()
        vocab = self._vocab()
        return {
            "type": "knowledge",
            "len": len(entries),
            "keys": list(entries.keys())[:8],
            "seq": self.payload["seq"],
            "n_facts": len(self._facts()),
            "n_words": len(vocab["words"]),
            "n_relations": len(vocab["relations"]),
            "n_worlds": len(vocab["worlds"]),
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
