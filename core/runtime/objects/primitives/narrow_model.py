"""
core/runtime/objects/primitives/narrow_model.py

IbNarrowModel —— 推理时窄模型值对象（一等不可变值类型）。

``narrow_model`` 是 ``world_model.bind_artifact`` 的返回值：**冻结的 KG 嵌入
向量空间模型**（试用方侧离线训练成工件，IBCI 推理时加载）——纯推理、零训练。
主架构 TransE（实体嵌入 E + 关系嵌入 R；``f(s,r,o)=‖e_s + r_r − e_o‖`` 平移
假设，距离越小越优）。

语义契约：

- **不可变冻结工件**：无修改面（权重/词表加载即冻结）；deep_clone 走不可变
  引用复用（同 vector/run_result/quoted 纪律）；``narrow_model()`` 语言构造
  fail-fast（模型必经 ``world_model.bind_artifact`` 加载门——良构由加载门
  成立，同 quoted 仅经 meta.quote 产出）。
- **推理面（内容信号，非判定——D1：判定走确定性路径）**：
  - ``score(s, r, o)`` = TransE 距离（越小越优）；
  - ``topk(s, r, k)`` = 全部候选实体按距离升序取前 k（每项 ``{o, score}``，
    确定性 tie-break = (距离, 实体名) 升序）。
- **参考未注册词 fail-fast**（同 KB 治理门纪律）：s/o 未注册实体 =
  ``NAR_ENTITY_UNREGISTERED``；r 未注册关系 = ``NAR_RELATION_UNREGISTERED``
  （冻结模型词表固定，无静默默认）。
- **确定性**：候选序 = artifact entities 固定序；IEEE 浮点纯算术（同输入同
  输出）。
- **拆箱**：``to_native()`` = 原生结构快照（防边界共享变异）。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from core.base.diagnostics.codes import (
    NAR_ENTITY_UNREGISTERED,
    NAR_RELATION_UNREGISTERED,
    NAR_TOPK_INVALID,
)
from core.kernel.issue import InterpreterError
from core.runtime.objects.kernel import IbObject, IbValue
from core.runtime.objects.kernel.base import unbox
from core.runtime.objects.ib_type_mapping import register_ib_type


@register_ib_type("narrow_model")
class IbNarrowModel(IbValue):
    """推理时窄模型值对象（冻结 KG 嵌入工件）。

    ``payload`` = 原生结构（序列化/边界 to_native 消费）：
    ``{model_name, architecture, dim, entities, entity_embeddings,
    relations, relation_embeddings, schema_version, content_hash}``。
    """

    __slots__ = ()

    def __init__(
        self,
        ib_class: "IbObject",
        payload: Optional[Dict[str, Any]] = None,
    ):
        # narrow_model 仅经 world_model.bind_artifact 水化构造（payload 直传）；
        # 无空白构造面（空模型无意义）。
        if payload is None:
            raise InterpreterError(
                "narrow_model 不能空白构造：模型须经 world_model.bind_artifact(path) "
                "从工件加载。",
            )
        super().__init__(ib_class, payload=dict(payload))

    # ------------------------------------------------------------------ #
    # 内部结构访问（单一权威：payload 原生结构）
    # ------------------------------------------------------------------ #

    def _entities(self) -> List[str]:
        return self.payload["entities"]

    def _entity_embeddings(self) -> Dict[str, List[float]]:
        return self.payload["entity_embeddings"]

    def _relations(self) -> List[str]:
        return self.payload["relations"]

    def _relation_embeddings(self) -> Dict[str, List[float]]:
        return self.payload["relation_embeddings"]

    def _dim(self) -> int:
        return self.payload["dim"]

    # ------------------------------------------------------------------ #
    # 推理面（TransE 纯算术；内容信号，非判定）
    # ------------------------------------------------------------------ #

    @staticmethod
    def _transe_distance(es: List[float], rr: List[float], eo: List[float]) -> float:
        """TransE 距离 ``‖e_s + r_r − e_o‖``（L2 范数；越小越优）。"""
        total = 0.0
        for i in range(len(es)):
            d = es[i] + rr[i] - eo[i]
            total += d * d
        return math.sqrt(total)

    def _resolve_entity(self, name: Any) -> List[float]:
        """实体名 → 嵌入向量（未注册 = fail-fast，无静默默认）。"""
        emb = self._entity_embeddings().get(name)
        if emb is None:
            raise InterpreterError(
                f"narrow_model: 实体 '{name}' 未在工件词表注册（score/topk 的 "
                f"s/o 须为已注册实体；冻结模型词表固定）。",
                error_code=NAR_ENTITY_UNREGISTERED,
            )
        return emb

    def _resolve_relation(self, name: Any) -> List[float]:
        """关系名 → 嵌入向量（未注册 = fail-fast，无静默默认）。"""
        emb = self._relation_embeddings().get(name)
        if emb is None:
            raise InterpreterError(
                f"narrow_model: 关系 '{name}' 未在工件词表注册（score/topk 的 "
                f"r 须为已注册关系；冻结模型词表固定）。",
                error_code=NAR_RELATION_UNREGISTERED,
            )
        return emb

    def score(self, s: IbObject, r: IbObject, o: IbObject) -> Any:
        """三元组 (s, r, o) 的 TransE 距离（内容信号，**越小越优**）。

        s/o 须已注册实体、r 须已注册关系（未注册 = fail-fast）。纯算术，
        确定性（同输入同输出），零训练。
        """
        subj = unbox(s)
        rel = unbox(r)
        obj = unbox(o)
        es = self._resolve_entity(subj)
        rr = self._resolve_relation(rel)
        eo = self._resolve_entity(obj)
        return self._transe_distance(es, rr, eo)

    def topk(self, s: IbObject, r: IbObject, k: IbObject) -> Any:
        """给定 (s, r) 的 top-k 候选实体（按 TransE 距离升序）。

        返回 ``list``，每项 ``{o: str, score: float}``（score = 距离，越小
        越优）。候选序 = 工件 entities 固定序；排序键 ``(距离, 实体名)`` 升序
        （确定性 tie-break）。``k`` 须为正整数（``NAR_TOPK_INVALID``）；
        ``k`` 超候选数 = 返回全部候选（非错误）。s/r 未注册 = fail-fast。
        """
        subj = unbox(s)
        rel = unbox(r)
        kk = unbox(k)
        if not isinstance(kk, int) or isinstance(kk, bool) or kk < 1:
            raise InterpreterError(
                f"narrow_model.topk: k 须为正整数（收到 {kk!r}）。",
                error_code=NAR_TOPK_INVALID,
            )
        es = self._resolve_entity(subj)
        rr = self._resolve_relation(rel)
        embs = self._entity_embeddings()
        dim = self._dim()
        scored: List[tuple] = []
        for name in self._entities():
            eo = embs[name]
            total = 0.0
            for i in range(dim):
                d = es[i] + rr[i] - eo[i]
                total += d * d
            scored.append((math.sqrt(total), name))
        scored.sort(key=lambda t: (t[0], t[1]))
        return [{"o": name, "score": dist} for dist, name in scored[:kk]]

    # ------------------------------------------------------------------ #
    # 元数据查询面
    # ------------------------------------------------------------------ #

    def name(self) -> Any:
        """工件模型名。"""
        return self.payload["model_name"]

    def dim(self) -> Any:
        """嵌入维度。"""
        return self._dim()

    def entities(self) -> Any:
        """候选实体空间（``list[str]``，工件固定序）。"""
        return list(self._entities())

    def relations(self) -> Any:
        """关系空间（``list[str]``，工件固定序）。"""
        return list(self._relations())

    def architecture(self) -> Any:
        """模型架构（当前仅 ``"transe"``）。"""
        return self.payload["architecture"]

    def content_hash(self) -> Any:
        """内容哈希（钉扎/审计基准）。"""
        return self.payload["content_hash"]

    # ------------------------------------------------------------------ #
    # 拆箱 / 序列化 / 提示词
    # ------------------------------------------------------------------ #

    def _payload_snapshot(self) -> Dict[str, Any]:
        """原生结构快照（embedding 向量拷贝——边界不共享内部引用）。"""
        return {
            "model_name": self.payload["model_name"],
            "architecture": self.payload["architecture"],
            "dim": self.payload["dim"],
            "entities": list(self._entities()),
            "entity_embeddings": {
                k: list(v) for k, v in self._entity_embeddings().items()
            },
            "relations": list(self._relations()),
            "relation_embeddings": {
                k: list(v) for k, v in self._relation_embeddings().items()
            },
            "schema_version": self.payload["schema_version"],
            "content_hash": self.payload["content_hash"],
        }

    def to_native(self, memo=None) -> Any:
        # 冻结窄模型 = 不可变值类型：原生表征 = 全字段快照（序列化/边界消费）。
        return self._payload_snapshot()

    def __to_prompt__(self) -> str:
        """提示词面 = 结构化摘要（模型名/架构/规模/哈希）。"""
        p = self.payload
        return (
            f"narrow_model({p['model_name']}, arch={p['architecture']}, "
            f"dim={p['dim']}, entities={len(self._entities())}, "
            f"relations={len(self._relations())}, "
            f"hash={p['content_hash'][:12]}…)"
        )

    def cast_to(self, target_class) -> IbObject:
        if target_class.name in ("narrow_model", "any"):
            return self
        raise InterpreterError(
            f"TypeError: Cannot cast 'narrow_model' to '{target_class.name}' "
            f"(narrow_model/any 转换受支持)。",
        )

    def serialize_for_debug(self):
        p = self.payload
        return {
            "type": "narrow_model",
            "model_name": p["model_name"],
            "architecture": p["architecture"],
            "dim": p["dim"],
            "n_entities": len(self._entities()),
            "n_relations": len(self._relations()),
            "content_hash": p["content_hash"][:16],
        }

    def __repr__(self):
        p = self.payload
        return (
            f"<NarrowModel {p['model_name']!r} arch={p['architecture']} "
            f"dim={p['dim']} entities={len(self._entities())}>"
        )

    # ------------------------------------------------------------------ #
    # 值语义（不可变冻结工件——引用身份即语义；不作 dict 键）
    # ------------------------------------------------------------------ #

    __hash__ = None
