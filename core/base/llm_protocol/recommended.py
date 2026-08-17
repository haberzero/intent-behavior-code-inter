"""``core.base.llm_protocol.recommended`` —— 推荐系统提示词组装模板（供应商无关）。

把一次 :class:`~core.base.llm_protocol.llm_call.LLMCallRequest` 的语义槽
（``PromptSlot``）组装成一份可用的系统提示词的**推荐**实现。

设计立场：

- 内核**不**负责把细节拼进单一系统提示词；它只产出结构化 `PromptSlot`。
- 本模块是"把语义槽变为系统提示词"的**推荐模板**（可移植、纯文本、供应商无关），
  供默认 provider 使用；**provider 完全可忽略它、自写组装逻辑**（自定义 provider
  即可自定义提示词形态）。
- 用户想改写"面对某左值/类型的默认行为"，本质是自定义 provider 或自定义组装
  策略——这是可插拔的，不在内核定死。

本模块纯文本，无 runtime / registry / provider 依赖，可存在于 base 层。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from core.base.llm_protocol.llm_call import IntentBlock, OutputContract, PromptSlot


# ---------------------------------------------------------------------------
# 基础输出纪律（behavior 专用）
# ---------------------------------------------------------------------------


def behavior_discipline() -> str:
    """behavior 表达式的输出纪律段落（不介绍系统，只描述本次调用规则）。"""
    return (
        "只输出任务要求的结果数据本身。"
        "禁止输出任何解释、问候、提问、拒绝、安全声明或其他与结果无关的文字。"
    )


# ---------------------------------------------------------------------------
# 段落标题（全系统统一推荐形态）
# ---------------------------------------------------------------------------

_OUTPUT_FORMAT_HEADING = "[输出格式要求]"
_INTENT_HEADING = "必须遵守以下要求："

#: 无真实输出契约的类型：不应把内部类型名作为"期望输出类型"注入给模型。
_NO_CONTRACT_TYPE_BASES = frozenset({
    "behavior",
    "fn_callable",
    "any",
    "auto",
    "fn",
    "void",
    "none",
})


def _base_type_name(type_hint: str) -> str:
    """取泛型声明的基名（``list[int]`` → ``list``）。"""
    return type_hint.split("[", 1)[0].strip()


def _display_type_name(type_hint: str) -> str:
    """把内部模块前缀从提示词中剥离（``__string_exec__.Status`` → ``Status``）。

    真实用户模块名（如 ``geo.Point``）保留，避免同名类误指。
    """
    prefix = "__string_exec__."
    if type_hint.startswith(prefix):
        return type_hint[len(prefix):]
    return type_hint


def _is_contract_type_hint(type_hint: str) -> bool:
    """该 type_hint 是否代表一个有真实输出契约的期望类型。"""
    return _base_type_name(type_hint) not in _NO_CONTRACT_TYPE_BASES


def type_constraint_section(
    output_contract: OutputContract,
    provider_type_prompt: Optional[str] = None,
) -> Optional[str]:
    """构造"输出格式/期望类型"约束段落（按优先级取一个权威来源）。

    优先级：provider 显式注册的类型提示 > 类型 ``__outputhint_prompt__`` >
    通用类型声明。provider 提示是插件/用户可覆盖的显式契约，应优先于类型
    内建默认；类型 hint 在无显式 provider 提示时生效；通用类型声明仅作兜底。
    """
    oc = output_contract
    if oc.suppress_type_constraint:
        return None
    if provider_type_prompt:
        return provider_type_prompt
    if oc.provider_type_prompt:
        return oc.provider_type_prompt
    if oc.output_hint:
        return f"{_OUTPUT_FORMAT_HEADING}\n{oc.output_hint}"
    if oc.expected_type and _is_contract_type_hint(oc.expected_type):
        return f"必须返回一个 {_display_type_name(oc.expected_type)} 值。"
    return None


def intent_section(intents: List[str]) -> Optional[str]:
    """构造意图注入段落（只描述必须遵守的要求，不介绍系统身份）。"""
    if not intents:
        return None
    return _INTENT_HEADING + "\n" + "\n".join(f"- {i}" for i in intents)


def _parts_of(*, intents: "IntentBlock", output_contract: OutputContract,
              extra_slots: List[PromptSlot], provider_type_prompt: Optional[str]) -> List[str]:
    """按推荐顺序归并系统提示词段落（有序列表）。

    只使用 request 已携带的结构化信息；本函数只是**推荐**呈现方式。
    """
    ordered: List[str] = []
    # 0) 用户自设 __sys__（LLM 函数）——放在最前
    for slot in extra_slots:
        if slot.kind == "user_sys" and slot.text:
            ordered.append(slot.text)
    # 1) 输出纪律（behavior 默认）
    ordered.append(behavior_discipline())
    # 2) 输出格式/期望类型（由 output_contract 派生）
    type_part = type_constraint_section(output_contract, provider_type_prompt=provider_type_prompt)
    if type_part:
        ordered.append(type_part)
    # 3) 意图要求（原始意图栈的 merged 层，逐条 bullet）
    merged = list(intents.merged)
    if merged:
        ordered.append(_INTENT_HEADING + "\n" + "\n".join(f"- {i}" for i in merged))
    # 4) 其余附加语义槽（用户/provider 补充，kind != user_sys）按其文本呈现
    for slot in extra_slots:
        if slot.kind in ("discipline", "type_constraint", "intent", "user_sys"):
            continue  # 已由权威来源处理，避免重复
        if slot.text:
            ordered.append(slot.text)
    return [s for s in ordered if s]


def assemble_system_prompt(
    *,
    intents: "IntentBlock",
    output_contract: OutputContract,
    extra_slots: List[PromptSlot] | None = None,
    provider_type_prompt: Optional[str] = None,
) -> Optional[str]:
    """把请求的意图栈 / 输出契约 / 附加槽组装为单一系统提示词（推荐实现）。

    顺序：输出纪律 → 输出格式/期望类型 → 意图要求 → 附加语义槽。
    返回 ``None`` 表示无任何可写内容。
    """
    parts = _parts_of(
        intents=intents,
        output_contract=output_contract,
        extra_slots=list(extra_slots or []),
        provider_type_prompt=provider_type_prompt,
    )
    return "\n\n".join(parts) if parts else None


# ---------------------------------------------------------------------------
# retry / 多轮对话消息构造（推荐格式）
# ---------------------------------------------------------------------------


def retry_user_message(
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


def retry_message_history(
    parse_error: Optional[str] = None,
    raw_response: Optional[str] = None,
    user_hint: Optional[str] = None,
) -> List[Dict[str, str]]:
    """构造一次失败重试的消息历史（assistant 上次输出 + user 纠错）。"""
    messages: List[Dict[str, str]] = []
    if raw_response:
        messages.append({"role": "assistant", "content": raw_response})
    messages.append({
        "role": "user",
        "content": retry_user_message(parse_error=parse_error, user_hint=user_hint),
    })
    return messages
