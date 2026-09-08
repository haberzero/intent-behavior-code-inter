"""
core.runtime.replay.provider — 确定性重放 LLMProvider。

LLMProvider 协议的一种实现形态（与真实 provider / mock 同槽——机制同构：
provider 就是 provider，经 CAP_LLM_PROVIDER 能力槽按优先级生效）：

- ``call``：按 journal seq 序返回记录的 LLMCallResult（content/raw_response/
  finish_reason/provider_meta 原样重建）；记录的 error 行 → 同形态 raise
  （_call_llm 异常面包装为 LLMCallError——与原始 run 的失败同形态）；
- 耗尽（代码请求次数 > 记录次数）= fail-fast（确定性承诺不容静默回落真实
  provider；错误消息携带耗尽语义，经既有 LLMCallError 包装面到达用户）；
- ``stream``：不支持（流式不入 journal——覆盖边界，诚实 NotImplementedError）；
- 内省面（get_current_call_info）：返回最近一次重放记录（idbg/call_info
  面在重放模式同形态可用）。
"""

from __future__ import annotations

from typing import Any, Dict

from core.base.llm_protocol.llm_call import LLMCallRequest, LLMCallResult
from core.base.llm_protocol.provider import LLMProvider

from .journal_reader import ReplayJournal


class ReplayLLMProvider(LLMProvider):
    """确定性重放 provider（一 journal 一实例；CLI --replay 注册）。"""

    def __init__(self, journal: ReplayJournal):
        self._journal = journal
        self._last_call_info: Dict[str, Any] = {}

    def call(self, request: LLMCallRequest) -> LLMCallResult:
        if self._journal.consumed_calls >= self._journal.total_calls:
            # 耗尽 fail-fast：代码相对记录 run 变更了调用序列（确定性契约
            # 违背）——消息携带语义，经 _call_llm 包装为 LLMCallError。
            raise RuntimeError(
                f"replay journal exhausted at call #"
                f"{self._journal.consumed_calls + 1} — code diverges from the "
                f"recorded run (deterministic replay contract violated; "
                f"source: {self._journal.source_path})"
            )
        rec = self._journal.next_call()

        # 失败记录：同形态 raise（与原始 run 的 provider 失败同路径——
        # _call_llm 异常面包装为 LLMCallError，llmexcept 重试对其无效）。
        if rec.get("error"):
            raise RuntimeError(str(rec["error"]))

        meta: Dict[str, Any] = {"sys_prompt": rec.get("sys_prompt", "")}
        if rec.get("generation"):
            meta["generation"] = rec["generation"]
        if rec.get("usage"):
            meta["usage"] = rec["usage"]

        self._last_call_info = {
            "node_uid": rec.get("node_uid"),
            "target_model": rec.get("target_model"),
            "user_prompt": rec.get("user_prompt", ""),
            "response": rec.get("content", ""),
            "finish_reason": rec.get("finish_reason"),
            "replayed": True,
            "replay_source": self._journal.source_path,
        }
        return LLMCallResult(
            content=rec.get("content", ""),
            raw_response=rec.get("raw_response", ""),
            finish_reason=rec.get("finish_reason"),
            provider_meta=meta,
        )

    def stream(self, request: LLMCallRequest):
        # 流式不入 journal（批 1 覆盖边界）——重放模式不支持流式，诚实拒绝。
        raise NotImplementedError(
            "replay mode does not support streaming (streaming calls are not "
            "journaled — deterministic replay coverage boundary)"
        )

    def get_retry(self) -> int:
        return 3

    def is_auto_intent_injection_enabled(self) -> bool:
        return True

    def get_current_call_info(self) -> Dict[str, Any]:
        return dict(self._last_call_info)
