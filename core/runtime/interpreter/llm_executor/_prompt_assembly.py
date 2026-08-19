"""``_prompt_assembly`` —— LLM 重试多轮对话消息结构（内核侧单一权威源）。

行为表达式的 **retry 多轮对话消息**（assistant/user 序列）构造规则集中
于此，供 ``_BehaviorMixin`` 使用，避免消息结构在多条执行路径中重复漂移。

**职责边界**（LLM 调用层插件化主线）：
- 内核**不**负责把细节拼进单一系统提示词——系统提示词的形态由 provider
  （推荐模板，见 ``core.base.llm_protocol.recommended``）组装；
- 本模块只保留**重试多轮对话消息结构**（消息历史），这是 retry 语义的结构化
  数据，由内核产给 provider 追加在首轮之后。
本模块只做纯消息结构构造，不访问 live context / provider / registry。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def build_retry_user_message(
    *,
    parse_error: Optional[str] = None,
    user_hint: Optional[str] = None,
) -> str:
    """构造 retry 轮的用户消息（标准多轮对话中的纠错 user turn）。

    只描述对本次输出的要求，不重复系统提示词中已有的身份/纪律内容。
    """
    lines = ["上一次输出无法解析。请重新只输出符合要求的结果数据本身。"]
    if parse_error:
        lines.append(f"解析失败原因：{parse_error}")
    if user_hint:
        lines.append(f"补充要求：{user_hint}")
    return "\n".join(lines)


def build_retry_message_history(
    *,
    parse_error: Optional[str] = None,
    raw_response: Optional[str] = None,
    user_hint: Optional[str] = None,
) -> List[Dict[str, str]]:
    """构造一次失败重试的消息历史（assistant 上次输出 + user 纠错）。

    供 provider 追加在 ``[system, user]`` 之后，形成标准多轮对话：
    ``system → user(原任务) → assistant(失败输出) → user(纠错)``。
    """
    messages: List[Dict[str, str]] = []
    if raw_response is not None and raw_response != "":
        messages.append({"role": "assistant", "content": raw_response})
    messages.append({
        "role": "user",
        "content": build_retry_user_message(
            parse_error=parse_error,
            user_hint=user_hint,
        ),
    })
    return messages


def build_retry_message_history_from_attempts(
    attempts: Optional[Iterable[Dict[str, Any]]],
) -> Optional[List[Dict[str, str]]]:
    """把 llmexcept 帧记录的失败尝试序列转换为完整多轮对话历史。

    每个失败尝试记录形如 ``{"raw_response": ..., "parse_error": ...,
    "user_hint": ...}``；按失败顺序生成 ``assistant → user`` 序列。
    """
    if not attempts:
        return None
    messages: List[Dict[str, str]] = []
    for attempt in attempts:
        messages.extend(
            build_retry_message_history(
                parse_error=attempt.get("parse_error"),
                raw_response=attempt.get("raw_response"),
                user_hint=attempt.get("user_hint"),
            )
        )
    return messages or None
