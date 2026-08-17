"""``core.base.llm_protocol.llm_call`` —— LLM 调用结构化契约（供应商无关）。

契约定位于 ``core/base``（最底层，可迁移到任何语言），是内核 / runtime 与
外部 LLM 调用服务（AI 插件）之间**唯一**的请求/响应数据契约。

设计立场（对应"LLM 调用层插件化"主线）：

- 内核只关心"调用 LLM 这个抽象动作"，**不**关心具体供应商的请求格式。
  因此 :class:`LLMCallRequest` 只承载 IBCI 语义的原始信息（意图栈 / 输出契约 /
  提示词语义槽 / 目标模型），**不**含任何 `enable_thinking`/`extra_body`/
  `max_tokens` 之类的供应商字段名。
- 具体调用服务（provider 插件）负责把 :class:`LLMCallRequest` 组装成它所属
  供应商的真实 API payload，并把供应商响应解析回供应商无关的
  :class:`LLMCallResult`。拼装格式 / api_config.json 书写格式都在插件侧，
  不在本契约内定死（可提供推荐模板）。
- 思考模式以供应商无关的 `"auto"/"on"/"off"` 声明存在；供应商如何映射到
  自身的思考字段（LM Studio `enable_thinking` / Anthropic `thinking.budget`
  / OpenAI `reasoning.effort` …）由插件实现，不在本契约内。

本模块只定义纯数据结构，不访问 runtime / registry / provider，无任何副作用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# 提示词语义槽（内核产出的结构化片断，不预拼合成单一系统提示词）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PromptSlot:
    """系统提示词的一个具名语义槽。

    ``kind`` 标识槽的来源（如 ``discipline`` / ``type_constraint`` /
    ``intent`` / ``retry``），供格式自定义方按需取舍槽位与顺序；不要求
    拼合成单一字符串。内核只负责按语义收集槽位，具体怎么写入提示词由
    使用方决定。
    """

    kind: str
    text: str


# ---------------------------------------------------------------------------
# 意图注释栈（原始分层，未摊平为字符串）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntentBlock:
    """一次 LLM 调用时捕获的意图注释栈（原始三层，按 IBCI 意图语义）。

    - ``active``：当前活跃的一次性意图（含 ``@`` / ``@!`` 覆盖）
    - ``global``：全局意图（``global_intent`` 注入）
    - ``merged``：进入本次调用的合并消解结果（去重后、可直接消费的提示列表）
    """

    active: List[str] = field(default_factory=list)
    global_: List[str] = field(default_factory=list)
    merged: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 输出契约（左值/返回类型派生的原始信息，未拼进字符串）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OutputContract:
    """LLM 调用的输出约束信息（原始结构，未装配成提示词文本）。

    - ``expected_type``：行为/LLM 函数的期望返回类型名（如 ``str`` /
      ``main.Point`` / ``list[int]``）。``None`` 表示无显式类型声明。
    - ``output_hint``：类型 ``__outputhint_prompt__`` 协议产出的原始输出格式
      约束文本（未加段落标题）。
    - ``provider_type_prompt``：provider 显式注册的返回类型提示（未加段落标题）。
    - ``suppress_type_constraint``：是否存在排他意图（``@!``）导致不注入类型级
      输出约束。
    """

    expected_type: Optional[str] = None
    output_hint: Optional[str] = None
    provider_type_prompt: Optional[str] = None
    suppress_type_constraint: bool = False


# ---------------------------------------------------------------------------
# 图片/多模态 content 块（透明透传给使用方，不做供应商规范化）
# ---------------------------------------------------------------------------

#: 一次提示内容的可能形态：纯文本，或多模态 content blocks 结构（块类型由
#: 上游捕获，本契约不强制 schema——具体块结构由内核求值产物携带）。
ContentValue = Union[str, List[Dict[str, Any]]]


# ---------------------------------------------------------------------------
# 完整 LLM 调用请求
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LLMCallRequest:
    """一次来自 IBCI 内核的完整 LLM 调用请求（唯一结构化交付物）。

    内核在调用点收集全部内核级原始信息装配本对象，并将其委托给具体调用服务
    （provider 插件 / LLMProviderV2 实现）。使用方负责：

    1. 把 ``prompt_slots`` 按自身格式拼装成系统提示词（或直接使用各语义槽）；
    2. 把 ``user_prompt`` 组装成供应商请求的 user content；
    3. 依据 ``thinking_mode`` 与 ``output_contract`` 施加供应商侧约束。

    本对象**不含**任何供应商专有字段；供应商字段映射在使用方实现内。
    """

    node_uid: str
    user_prompt: ContentValue
    #: 系统提示词的语义槽列表（按语义收集，未预拼装；使用方可取舍/重排）
    prompt_slots: List[PromptSlot] = field(default_factory=list)
    intents: IntentBlock = field(default_factory=IntentBlock)
    output_contract: OutputContract = field(default_factory=OutputContract)
    target_model: str = ""
    #: 标准多轮对话历史（assistant/user 消息序列），追加在首轮之后
    message_history: Optional[List[Dict[str, str]]] = None
    #: 供应商无关的思考模式声明："auto" / "on" / "off"（供应商自行映射）
    thinking_mode: str = "auto"
    #: 具名模型路由标识（@NAME~ 语法）；空表示默认模型

    def as_dict(self) -> Dict[str, Any]:
        """序列化为可诊断的纯 dict（供 idbg / call_info 内省）。"""
        return {
            "node_uid": self.node_uid,
            "target_model": self.target_model,
            "thinking_mode": self.thinking_mode,
            "intents": {
                "active": list(self.intents.active),
                "global": list(self.intents.global_),
                "merged": list(self.intents.merged),
            },
            "output_contract": {
                "expected_type": self.output_contract.expected_type,
                "output_hint": self.output_contract.output_hint,
                "provider_type_prompt": self.output_contract.provider_type_prompt,
                "suppress_type_constraint": self.output_contract.suppress_type_constraint,
            },
            "prompt_slots": [
                {"kind": s.kind, "text": s.text} for s in self.prompt_slots
            ],
            "has_message_history": bool(self.message_history),
            "message_history": list(self.message_history or []),
        }


# ---------------------------------------------------------------------------
# LLM 调用结果
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LLMCallResult:
    """一次 LLM 调用的响应结果（供应商无关）。

    使用方（provider）负责把供应商响应解析为本对象字段；内核只消费本对象，
    不在解析时触碰供应商对象。

    - ``content``：最终答案文本（内核解析 / llmexcept 重试消费的对象）。
    - ``raw_response``：完整原始响应（可包含思考过程；内核通常只解析 content）。
    - ``reasoning``：结构化思考字段（供应商无关）；无思考为 ``None``。
    - ``thinking_detected``：响应中出现思考内容（即便请求施加了思考抑制）。
      供供应商感知的思考抑制失败告警判断。
    - ``provider_meta``：供应商侧额外原始信息（可选），仅供内省，不参与解析。
    """

    content: str
    raw_response: str = ""
    reasoning: Optional[str] = None
    thinking_detected: bool = False
    provider_meta: Dict[str, Any] = field(default_factory=dict)
