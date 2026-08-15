"""``_prompt_assembly`` — LLM 系统提示词组装单一权威源。

行为表达式与命名 LLM 函数的 system prompt 追加规则集中于此，供
``_BehaviorMixin``（sync/CPS）与 ``_LLMFunctionMixin``（CPS）共用，
避免同一段拼装逻辑在两条执行路径/两个调用形态中重复漂移。

本模块只做纯文本组装，不访问 live context / provider / registry。
"""

from typing import Iterable, Optional

# ---------------------------------------------------------------------------
# 基础角色框架（behavior 专用）
# ---------------------------------------------------------------------------

BEHAVIOR_SYSTEM_PROMPT = (
    "你是一个被 IBCI 程序调用的函数。"
    "你只返回调用方要求的数据本身；"
    "禁止输出问候语、解释、提问、拒绝、安全声明或任何与结果无关的文字。"
)

# ---------------------------------------------------------------------------
# 段落标题（全系统统一）
# ---------------------------------------------------------------------------

OUTPUT_FORMAT_HEADING = "[输出格式要求]"
EXPECTED_TYPE_HEADING = "[期望输出类型]"
RETRY_FEEDBACK_HEADING = "[重试反馈]"
INTENT_HEADING = "当前上下文意图（必须严格遵守）："

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
        return (
            f"{EXPECTED_TYPE_HEADING}\n"
            f"必须返回一个 {_display_type_name(type_hint)} 值。"
        )
    return None


def build_intent_section(intents: Optional[Iterable[str]]) -> Optional[str]:
    """构造意图注入段落。"""
    if not intents:
        return None
    return INTENT_HEADING + "\n" + "\n".join(f"- {i}" for i in intents)


def build_retry_feedback(
    *,
    user_hint: Optional[str] = None,
    parse_error: Optional[str] = None,
    raw_response: Optional[str] = None,
) -> Optional[str]:
    """构造自动重试反馈文本（不含标题，供调用方包入段落）。

    自动回喂上一次失败调用的原始响应与解析错误；用户手写 retry hint
    （``retry "..."`` / ``__llmretry__``）作为补充指令追加在后，二者语义
    不混写。
    """
    lines: list[str] = []
    if raw_response is not None and raw_response != "":
        lines.append(f"上一次调用返回的内容：\n{raw_response}")
    if parse_error:
        lines.append(f"解析失败原因：{parse_error}")
    if lines:
        lines.insert(0, "上一次调用未能产生可解析的结果。")
        lines.append("请纠正后只返回符合要求的数据本身。")
    if user_hint:
        lines.append(f"补充重试要求：{user_hint}")
    if not lines:
        return None
    return "\n".join(lines)


def build_retry_feedback_section(
    *,
    user_hint: Optional[str] = None,
    parse_error: Optional[str] = None,
    raw_response: Optional[str] = None,
) -> Optional[str]:
    """构造完整 ``[重试反馈]`` 段落（含标题）。"""
    body = build_retry_feedback(
        user_hint=user_hint,
        parse_error=parse_error,
        raw_response=raw_response,
    )
    if not body:
        return None
    return f"{RETRY_FEEDBACK_HEADING}\n{body}"


def build_behavior_system_prompt(
    *,
    output_hint: Optional[str] = None,
    type_hint: Optional[str] = None,
    provider_type_prompt: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    intents: Optional[Iterable[str]] = None,
) -> str:
    """组装 behavior 表达式的完整 system prompt（单一权威）。

    顺序：角色框架 → 输出格式/期望类型 → 意图 → 重试反馈。
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

    if retry_feedback:
        sections.append(f"{RETRY_FEEDBACK_HEADING}\n{retry_feedback}")

    return "\n\n".join(sections)
