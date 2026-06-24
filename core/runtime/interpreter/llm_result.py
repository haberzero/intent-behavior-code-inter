# 向后兼容垫片 — 实际定义已移至 core/runtime/shared/llm_result.py
# 此文件保留以避免破坏可能存在的 ``from core.runtime.interpreter.llm_result import ...``
from core.runtime.shared.llm_result import LLMResult, LLMFuture

__all__ = ["LLMResult", "LLMFuture"]
