"""
core.runtime.replay — LLM 确定性重放（round3 需求 R-1 子系统，批 2）。

确定性重放（--replay：能力槽 SYSTEM 优先级替换 provider）。

同一入口代码 + 同一 journal = 同一执行轨迹：LLM 输出全部来自记录
（replay provider 经能力槽替换真实 provider，真实 provider 不加载——
无需 API key）。耗尽（代码请求次数 > 记录次数）= fail-fast
（确定性承诺不容静默回落真实 provider）；提前结束（控制流少走调用）
= 合法。

覆盖边界：流式调用（stream_call/stream_channel）不经 replay（流式不入
journal——与批 1 覆盖边界一致，诚实 fail-fast）；ihost 隔离子 run 的
LLM 调用不经主 run 的能力槽（子引擎独立 registry）——重放覆盖主 run。
"""

from .journal_reader import ReplayJournal, JournalFormatError
from .provider import ReplayLLMProvider

__all__ = ["ReplayJournal", "JournalFormatError", "ReplayLLMProvider"]
