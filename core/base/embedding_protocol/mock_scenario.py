"""``core.base.embedding_protocol.mock_scenario`` —— embedding mock 场景引擎。

``MOCK:VEC`` 指令语言（机制同构基准 = 上游 LLM mock 场景引擎的
MOCK:STR/SEQ/FAIL 指令面），保证测试断言可判定、零网络、零 key：

- ``MOCK:VEC[:seed]``     —— 哈希派生确定性向量（seed 可选；缺省 = 引擎默认）；
- ``MOCK:VEC:SEQ=<json>`` —— 固定向量序列（JSON 数组逐批消费；同输入同输出）；
- ``MOCK:FAIL[:msg]``     —— 下一次调用 fail-fast 抛 ``EmbeddingProviderError``。

引擎语义（显式，文档化）：

- 场景按 FIFO 逐次消费；**耗尽后回落到哈希派生默认**（显式行为，不静默失败）；
- 每个场景至多消费一次（SEQ 的向量按批逐条对齐请求 texts 顺序，长度不足
  fail-fast——与契约层 fail-fast 纪律一致）；
- 引擎本身零 I/O、零随机源（确定性可复现；线程安全由调用方保证）。

失败语义 → 诊断码：抛出的 ``EmbeddingProviderError`` 携带 ``code`` 属性
（``EMB_`` 域）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional

from core.base.diagnostics.codes import (
    EMB_BATCH_ORDER,
    EMB_DIMENSION_MISMATCH,
    EMB_INVALID_INPUT,
)
from core.base.embedding_protocol.recommended import EmbeddingProviderError, mock_vector


@dataclass(frozen=True)
class EmbeddingMockScenario:
    """一条 mock 场景指令。

    - ``kind``：``"VEC"`` / ``"SEQ"`` / ``"FAIL"``；
    - ``seed``：VEC 派生种子（仅 VEC 有效）；
    - ``vectors``：SEQ 的固定向量序列（仅 SEQ 有效）；
    - ``msg``：FAIL 的定位消息（仅 FAIL 有效）。
    """

    kind: str
    seed: int = 0
    vectors: Optional[List[List[float]]] = None
    msg: str = ""


class EmbeddingMockEngine:
    """MOCK:VEC 指令语言引擎（FIFO 场景队列 + 耗尽回落哈希派生）。"""

    def __init__(self, default_seed: int = 0) -> None:
        self._queue: List[EmbeddingMockScenario] = []
        self._default_seed = int(default_seed)
        self._seq_remaining: Optional[List[List[float]]] = None  # SEQ 持久缓冲
        self.consumed: int = 0  # 观测面：已消费调用数

    # ------------------------------------------------------------------ #
    # 指令入口（与上游 mock 场景引擎指令面同构）
    # ------------------------------------------------------------------ #

    def vec(self, seed: Optional[int] = None) -> None:
        """``MOCK:VEC[:seed]``——下一次调用返回哈希派生确定性向量。"""
        self._queue.append(
            EmbeddingMockScenario(
                kind="VEC",
                seed=int(seed if seed is not None else self._default_seed),
            )
        )

    def seq(self, vectors: List[List[float]]) -> None:
        """``MOCK:VEC:SEQ=<json>``——下一次调用按序返回固定向量序列。"""
        if not vectors:
            raise EmbeddingProviderError(
                "MOCK:VEC:SEQ 序列为空（指令非法）。", code=EMB_INVALID_INPUT
            )
        self._queue.append(
            EmbeddingMockScenario(
                kind="SEQ", vectors=[list(map(float, v)) for v in vectors]
            )
        )

    def seq_from_json(self, payload: str) -> None:
        """``MOCK:VEC:SEQ`` 的 JSON 字符串入口（解析失败 fail-fast）。"""
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            raise EmbeddingProviderError(
                f"MOCK:VEC:SEQ JSON 解析失败: {e}", code=EMB_INVALID_INPUT
            ) from e
        if not isinstance(data, list) or not all(isinstance(v, list) for v in data):
            raise EmbeddingProviderError(
                "MOCK:VEC:SEQ 载荷须为二维数组（向量序列）。",
                code=EMB_INVALID_INPUT,
            )
        self.seq(data)

    def fail(self, msg: str = "MOCK:FAIL 注入失败") -> None:
        """``MOCK:FAIL[:msg]``——下一次调用抛 ``EmbeddingProviderError``。"""
        self._queue.append(EmbeddingMockScenario(kind="FAIL", msg=msg))

    def reset(self) -> None:
        """清空队列与 SEQ 缓冲（耗尽回落语义的显式重置面）。"""
        self._queue = []
        self._seq_remaining = None
        self.consumed = 0

    # ------------------------------------------------------------------ #
    # 消费
    # ------------------------------------------------------------------ #

    def has_pending(self) -> bool:
        return len(self._queue) > 0

    def pop(self) -> Optional[EmbeddingMockScenario]:
        """取出一条场景（FIFO）；空队列返回 ``None``（调用方回落默认）。"""
        if not self._queue:
            return None
        self.consumed += 1
        return self._queue.pop(0)

    def next_vectors(self, n_texts: int, dim: int) -> List[List[float]]:
        """按当前场景为 ``n_texts`` 条请求文本生成向量（契约校验 fail-fast）。

        - VEC 场景：哈希派生（per-text，序号前缀 ``vec:{i}`` 拼入 text 后派生），
          一次消费；
        - SEQ 场景：固定序列**按批逐条对齐、跨调用持久**（序列耗尽前不切换
          场景；缓冲余量 < n_texts fail-fast）；
        - FAIL 场景：抛错（消费）；
        - 无场景（耗尽）：回落哈希派生默认（序号前缀 ``default:{i}``；
          显式行为，不静默失败）。
        """
        sc = self._queue[0] if self._queue else None
        if sc is None:
            self.consumed += 1
            return [
                mock_vector(f"default:{i}", dim, self._default_seed)
                for i in range(n_texts)
            ]
        if sc.kind == "FAIL":
            self._queue.pop(0)
            self.consumed += 1
            raise EmbeddingProviderError(sc.msg, code=EMB_INVALID_INPUT)
        if sc.kind == "VEC":
            self._queue.pop(0)
            self.consumed += 1
            return [mock_vector(f"vec:{i}", dim, sc.seed) for i in range(n_texts)]
        if sc.kind == "SEQ":
            if self._seq_remaining is None:
                self._seq_remaining = [list(map(float, v)) for v in sc.vectors]
            if len(self._seq_remaining) < n_texts:
                raise EmbeddingProviderError(
                    f"MOCK:VEC:SEQ 剩余 {len(self._seq_remaining)} < 请求 {n_texts}（契约违约）。",
                    code=EMB_BATCH_ORDER,
                )
            take = self._seq_remaining[:n_texts]
            for v in take:
                if len(v) != dim:
                    raise EmbeddingProviderError(
                        f"MOCK:VEC:SEQ 向量维度 {len(v)} != 目标 {dim}（契约违约，不做隐式补齐）。",
                        code=EMB_DIMENSION_MISMATCH,
                    )
            del self._seq_remaining[:n_texts]
            if not self._seq_remaining:
                self._queue.pop(0)
                self._seq_remaining = None
            self.consumed += 1
            return take
        raise EmbeddingProviderError(
            f"未知 mock 场景类型: {sc.kind!r}（契约违约）。", code=EMB_INVALID_INPUT
        )
