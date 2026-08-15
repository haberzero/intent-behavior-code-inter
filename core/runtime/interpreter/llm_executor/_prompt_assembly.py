"""``_prompt_assembly`` — LLM 提示词组装单一权威源。

行为表达式与命名 LLM 函数的 system prompt 追加规则、retry 多轮对话消息
构造规则集中于此，供 ``_BehaviorMixin``（sync/CPS）与 ``_LLMFunctionMixin``
（CPS）共用，避免同一段拼装逻辑在两条执行路径/两个调用形态中重复漂移。

本模块只做纯文本/消息结构组装，不访问 live context / provider / registry。
"""

from typing import Any, Dict, Iterable, List, Optional

# ---------------------------------------------------------------------------
# 基础输出纪律（behavior 专用）
#
# 不向模型介绍 IBCI 是什么；只描述本次调用必须遵守的规则。
# ---------------------------------------------------------------------------

BEHAVIOR_SYSTEM_PROMPT = (
    "只输出任务要求的结果数据本身。"
    "禁止输出任何解释、问候、提问、拒绝、安全声明或其他与结果无关的文字。"
)

# ---------------------------------------------------------------------------
# 段落标题（全系统统一）
# ---------------------------------------------------------------------------

OUTPUT_FORMAT_HEADING = "[输出格式要求]"
INTENT_HEADING = "必须遵守以下要求："

# 无真实输出契约的类型：不应把内部类型名作为"期望输出类型"注入给模型。
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


def build_type_constraint_section(
    *,
    output_hint: Optional[str] = None,
    type_hint: Optional[str] = None,
    provider_type_prompt: Optional[str] = None,
    include_generic_type: bool = True,
) -> Optional[str]:
    """构造"输出格式/期望类型"约束段落（按优先级取一个权威来源）。

    优先级：provider 显式注册的类型提示 > 类型 ``__outputhint_prompt__`` >
    通用类型声明。provider 提示是插件/用户可覆盖的显式契约，应优先于类型
    内建默认；类型 hint 在无显式 provider 提示时生效；通用类型声明仅作
    兜底。后两项按调用形态决定是否启用。
    """
    if provider_type_prompt:
        return provider_type_prompt
    if output_hint:
        return f"{OUTPUT_FORMAT_HEADING}\n{output_hint}"
    if (
        include_generic_type
        and type_hint
        and _is_contract_type_hint(type_hint)
    ):
        return f"必须返回一个 {_display_type_name(type_hint)} 值。"
    return None


def build_intent_section(intents: Optional[Iterable[str]]) -> Optional[str]:
    """构造意图注入段落（只描述必须遵守的要求，不介绍系统身份）。"""
    if not intents:
        return None
    return INTENT_HEADING + "\n" + "\n".join(f"- {i}" for i in intents)


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


def build_behavior_system_prompt(
    *,
    output_hint: Optional[str] = None,
    type_hint: Optional[str] = None,
    provider_type_prompt: Optional[str] = None,
    intents: Optional[Iterable[str]] = None,
) -> str:
    """组装 behavior 表达式的完整 system prompt（单一权威）。

    顺序：输出纪律 → 输出格式/期望类型 → 意图要求。
    """
    sections = [BEHAVIOR_SYSTEM_PROMPT]

    type_constraint = build_type_constraint_section(
        output_hint=output_hint,
        type_hint=type_hint,
        provider_type_prompt=provider_type_prompt,
        include_generic_type=True,
    )
    if type_constraint:
        sections.append(type_constraint)

    intent_section = build_intent_section(intents)
    if intent_section:
        sections.append(intent_section)

    return "\n\n".join(sections)
