"""
tests/runtime/test_llm_protocol_contracts.py
============================================

``core.base.llm_protocol`` —— LLM 调用层插件化契约层语义测试。

锁定内核 ↔ 调用服务之间的供应商无关数据契约：

- ``LLMCallRequest``：携带 IBCI 语义原始信息（意图栈 / 输出契约 / 提示词
  语义槽），**不**含供应商字段；``as_dict()`` 可诊断序列化。
- ``IntentBlock`` / ``OutputContract`` / ``PromptSlot``：原始分层结构、
  左值派生信息未预拼装。
- 冻结性（frozen dataclass）：请求对象不可变，避免跨线程误改。
- ``LLMCallResult``：供应商无关的响应字段（content / reasoning）。
- 配置契约 ``ModelSpec`` / ``LLMConnectionConfig``：逻辑配置形态不含文件
  schema；``ConfigSourceAdapter`` 是抽象要求实现方读取文件。

这些类位于 ``core/base``（叶子层，只出不进），无 executor 依赖，可独立单测。
"""
from dataclasses import FrozenInstanceError

from core.base.llm_protocol import (
    LLMCallRequest,
    LLMCallResult,
    OutputContract,
    IntentBlock,
    PromptSlot,
    ModelSpec,
    CallDefaults,
    LLMConnectionConfig,
    ConfigSourceAdapter,
    THINKING_AUTO,
    THINKING_OFF,
)

import pytest


class TestPromptSlot:
    def test_holds_kind_and_text(self):
        s = PromptSlot(kind="intent", text="必须遵守要求")
        assert s.kind == "intent"
        assert s.text == "必须遵守要求"


class TestIntentBlock:
    def test_defaults_empty_three_layers(self):
        b = IntentBlock()
        assert b.active == []
        assert b.global_ == []
        assert b.merged == []

    def test_can_hold_three_layers(self):
        b = IntentBlock(active=["a"], global_=["g"], merged=["a", "g"])
        assert b.active == ["a"]
        assert b.global_ == ["g"]
        assert b.merged == ["a", "g"]


class TestOutputContract:
    def test_defaults(self):
        c = OutputContract()
        assert c.expected_type is None
        assert c.output_hint is None
        assert c.provider_type_prompt is None
        assert c.suppress_type_constraint is False

    def test_carries_left_value_info_unassembled(self):
        c = OutputContract(expected_type="main.Point",
                           output_hint="点坐标", suppress_type_constraint=True)
        # 原始信息保留，未拼进任何"提示词文本"
        assert c.expected_type == "main.Point"
        assert c.output_hint == "点坐标"
        assert c.suppress_type_constraint is True


class TestLLMCallRequest:
    def test_is_supplier_agnostic_frozen(self):
        r = LLMCallRequest(node_uid="n1", user_prompt="hi")
        # 不含供应商字段名：本契约不使用 enable_thinking/extra_body/max_tokens
        with pytest.raises(AttributeError):
            _ = r.enable_thinking  # type: ignore[attr-defined]
        with pytest.raises(AttributeError):
            _ = r.extra_body  # type: ignore[attr-defined]
        with pytest.raises(FrozenInstanceError):
            r.target_model = "other"  # type: ignore[misc]

    def test_carries_raw_semantic_structure(self):
        r = LLMCallRequest(
            node_uid="n1",
            user_prompt="hello",
            prompt_slots=[
                PromptSlot(kind="discipline", text="只输出结果"),
                PromptSlot(kind="intent", text="步进计数"),
            ],
            intents=IntentBlock(active=["@step"], global_=["说明"]),
            output_contract=OutputContract(expected_type="int"),
            thinking_mode=THINKING_OFF,
        )
        assert r.thinking_mode == THINKING_OFF
        assert r.output_contract.expected_type == "int"
        assert r.intents.active == ["@step"]
        assert [s.kind for s in r.prompt_slots] == ["discipline", "intent"]

    def test_as_dict_is_diagnosed_snapshot(self):
        r = LLMCallRequest(
            node_uid="n1", user_prompt="hi",
            intents=IntentBlock(active=["a"], global_=["g"], merged=["a", "g"]),
            message_history=[{"role": "user", "content": "retry"}],
        )
        d = r.as_dict()
        assert d["node_uid"] == "n1"
        assert d["intents"]["active"] == ["a"]
        assert d["intents"]["global"] == ["g"]
        assert d["has_message_history"] is True
        assert d["prompt_slots"] == []

    def test_as_dict_with_prompt_slots(self):
        r = LLMCallRequest(
            node_uid="n1", user_prompt="hi",
            prompt_slots=[PromptSlot(kind="intent", text="x")],
        )
        assert r.as_dict()["prompt_slots"] == [{"kind": "intent", "text": "x"}]


class TestLLMCallResult:
    def test_supplier_agnostic_fields(self):
        res = LLMCallResult(content="42", raw_response="42", thinking_detected=True)
        assert res.content == "42"
        assert res.raw_response == "42"
        assert res.thinking_detected is True
        assert res.reasoning is None

    def test_can_carry_structured_reasoning(self):
        res = LLMCallResult(content="42", reasoning="先加一再...")
        assert res.reasoning == "先加一再..."


class TestConfigContract:
    def test_model_spec_default_timeout_none(self):
        m = ModelSpec(provider="openai", model_id="gpt-4o")
        assert m.endpoint is None
        assert m.auth is None
        assert m.timeout is None
        assert m.thinking_mode == THINKING_AUTO

    def test_connection_config_is_file_schema_agnostic(self):
        cfg = LLMConnectionConfig(
            default_model=ModelSpec(provider="ollama", model_id="qwen3"),
            models={
                "local": ModelSpec(provider="ollama", model_id="qwen3", timeout=60.0),
            },
            defaults=CallDefaults(retry=2, thinking_mode=THINKING_OFF),
        )
        assert cfg.default_model.model_id == "qwen3"
        assert cfg.models["local"].timeout == 60.0
        assert cfg.defaults.retry == 2
        assert cfg.defaults.thinking_mode == THINKING_OFF

    def test_config_source_adapter_is_abstract(self):
        # ConfigSourceAdapter 是抽象类，不可直接实例化（要求实现方可插拔读取）
        with pytest.raises(TypeError):
            ConfigSourceAdapter()  # type: ignore[abstract]
