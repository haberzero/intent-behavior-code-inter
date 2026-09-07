"""``core.base.embedding_protocol.retrieval`` —— 检索最小闭包。

"先 ``cosine`` + list 线性扫描内置，索引结构按需求演进"的最小闭包起步裁决：
本模块只实现**线性 top-k 检索**（多向量 + 查询 → 按余弦相似度排序取前 k），
不引入任何索引结构。

粒度纪律（实测实证，CONVERGENCE 发现 28）：

- 检索产物是**语料级/语域级的候选召回**（相对测量：相似度排序）——
  用于候选生成/上下文召回/语料倾向分析；
- **不是**单句级的语义判定器；
  铁律：embedding 只做相对测量，判定=确定性规则。

实现纪律（机制同构 = 本包既有 fail-fast 显式约定）：

- 非法输入 fail-fast（``RetrievalError``）：空语料 / k<=0 / 查询与语料维度
  不一致 / 向量含非有限值（NaN/Inf）/ 零范数；
- ``k > n`` 显式钳制为 ``n``（返回全部，不静默截断语义——文档化显式行为）；
- 相似度并列时**按语料索引升序**（稳定、确定性、可复现）；
- 零外部依赖（纯 Python 数学；不引入 numpy 依赖——上游环境有 numpy 时
  调用方可自行加速，本模块不强制）。

失败语义 → 诊断码：``RetrievalError`` 携带 ``code`` 属性（``EMB_`` 域）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from core.base.diagnostics.codes import (
    EMB_DIMENSION_MISMATCH,
    EMB_INVALID_INPUT,
    EMB_ZERO_NORM,
)


class RetrievalError(RuntimeError):
    """检索契约/输入失败的定位异常（fail-fast，不静默回退）。

    ``code`` 属性 = 失败语义的诊断码（``EMB_`` 域）。
    """

    def __init__(self, message: str, code: str = EMB_INVALID_INPUT):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------- #
# 结果结构
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RetrievalHit:
    """一个检索命中（语料索引 + 相似度）。

    - ``index``：语料中的位置（0 起，与输入 ``corpus`` 对应）。
    - ``score``：与查询的余弦相似度（[-1, 1]；确定性浮点，相对测量）。
    """

    index: int
    score: float


# --------------------------------------------------------------------------- #
# 相似度
# --------------------------------------------------------------------------- #


def _check_vector(v: Sequence[float], name: str) -> List[float]:
    """维度一致性/有限性校验（fail-fast）。"""
    if v is None or len(v) == 0:
        raise RetrievalError(f"{name} 为空向量（契约违约）。", code=EMB_INVALID_INPUT)
    out = [float(x) for x in v]
    for x in out:
        if not math.isfinite(x):
            raise RetrievalError(
                f"{name} 含非有限值（NaN/Inf，契约违约）。", code=EMB_INVALID_INPUT
            )
    return out


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """两向量的余弦相似度（确定性；零范数 fail-fast——退化输入不产生静默 0）。"""
    va = _check_vector(a, "向量 a")
    vb = _check_vector(b, "向量 b")
    if len(va) != len(vb):
        raise RetrievalError(
            f"维度不一致：a={len(va)} b={len(vb)}（检索契约违约）。",
            code=EMB_DIMENSION_MISMATCH,
        )
    na = math.sqrt(sum(x * x for x in va))
    nb = math.sqrt(sum(x * x for x in vb))
    if na == 0.0 or nb == 0.0:
        raise RetrievalError(
            "零范数向量（余弦未定义，fail-fast）。", code=EMB_ZERO_NORM
        )
    return sum(x * y for x, y in zip(va, vb)) / (na * nb)


# --------------------------------------------------------------------------- #
# 线性 top-k
# --------------------------------------------------------------------------- #


def linear_topk(
    query: Sequence[float],
    corpus: Sequence[Sequence[float]],
    k: int,
) -> List[RetrievalHit]:
    """线性扫描 top-k 检索（最小闭包：无索引结构）。

    - 返回按 ``score`` 降序的至多 ``k`` 个 :class:`RetrievalHit`；
      ``k > n`` 时显式钳制为 ``n``（返回全部）。
    - 并列分数按语料索引升序（稳定可复现）。
    - 复杂度 O(n·d)——最小闭包阶段的显式取舍（索引结构按需求演进）。
    """
    if not isinstance(k, int) or k <= 0:
        raise RetrievalError(f"k 须为正整数（契约违约）：k={k!r}", code=EMB_INVALID_INPUT)
    if corpus is None or len(corpus) == 0:
        raise RetrievalError("语料为空（检索契约违约）。", code=EMB_INVALID_INPUT)
    vq = _check_vector(query, "查询向量")
    scored: List[Tuple[float, int]] = []
    for i, cv in enumerate(corpus):
        sc = cosine(vq, cv)
        scored.append((sc, i))
    # 排序：score 降序；并列 → index 升序（确定性稳定序）
    scored.sort(key=lambda t: (-t[0], t[1]))
    take = min(k, len(scored))
    return [RetrievalHit(index=i, score=sc) for sc, i in scored[:take]]


def linear_topk_texts(
    query: Sequence[float],
    vectors: Sequence[Sequence[float]],
    texts: Sequence[str],
    k: int,
) -> List[Tuple[int, str, float]]:
    """带文本回放的便捷面：返回 ``[(index, text, score), ...]``（同 linear_topk 语义）。"""
    if len(vectors) != len(texts):
        raise RetrievalError(
            f"向量数与文本数不一致：{len(vectors)} vs {len(texts)}（契约违约）。",
            code=EMB_INVALID_INPUT,
        )
    out = []
    for hit in linear_topk(query, vectors, k):
        out.append((hit.index, str(texts[hit.index]), hit.score))
    return out
