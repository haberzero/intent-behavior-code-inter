"""
tests/runtime/test_probe_model.py
=================================

``ai.probe_model`` 测试覆盖。

锁定三项关键不变式：

① probe 为 setup-time 显式动作（无懒探测竞争）——MOCK 路径调用 ``probe_model()``
   显式写入 ``_model_capabilities`` 并返回 ``MOCK_PROBE_SUCCESS``；未 probe 时
   ``__call__`` 保守回退为推理策略（不触发懒探测）。
② ``_model_capabilities`` 在并行阶段只读消费——probe 后多次 ``__call__``
   不改写该能力字典（read-only 消费不变式）。
③ MOCK / 推理判定 / 失败兜底 三路径 + 消费方决策（``__call__`` 依
   ``is_reasoning`` 注入 ``ANSWER:`` 指令或使用原 prompt）。

说明：为锁定 ② 必须读取插件内部 `_model_capabilities`（无公开 getter），
属白盒不变式核验，非生产代码封装穿透。
"""

import pytest

from ibci_modules.ibci_ai.core import AIPlugin


# ---------------------------------------------------------------------------
# 测试替身
# ---------------------------------------------------------------------------


def _completion(content, *, reasoning=None, reasoning_content=None):
    """构造一个降级 OpenAIChatCompletion：仅含 probe/__call__ 需要的字段。"""
    class _Msg:
        pass
    class _Choice:
        pass
    class _Comp:
        pass

    msg = _Msg()
    msg.content = content
    msg.reasoning = reasoning
    msg.reasoning_content = reasoning_content

    choice = _Choice()
    choice.message = msg

    comp = _Comp()
    comp.choices = [choice]
    return comp


class FakeClient:
    """精简 OpenAI 客户端替身：``chat.completions.create`` 由 responder 驱动。

    responder 形如 ``fn(*args, **kwargs) -> completion``；用闭包/外部列表捕获
    调用内的 system prompt，以验证消费方决策。
    """

    def __init__(self, responder=None):
        responder = responder if responder is not None else (
            lambda *a, **k: _completion(content="ok")
        )
        self._responder = responder

        # OpenAI 结构：client.chat.completions.create(...)
        class _Completions:
            create = responder

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


def _plugin_with_fake(responder=None):
    """构造非 MOCK 配置 + FakeClient 的 AIPlugin（零真实网络）。"""
    plugin = AIPlugin()
    plugin.set_config("https://llm.invalid/v1", "sk-fake", "fake-model")
    plugin._client = FakeClient(responder)
    return plugin


def _plugin_mock():
    """构造 MOCK 配置的 AIPlugin（``_is_test_mode()`` 为 True）。"""
    plugin = AIPlugin()
    plugin.set_mock_mode()
    return plugin


def _mcreq(sys_prompt="sys", user_prompt="user", *, expected_type=None):
    """把 scalar (sys, user) 转为一次 ``LLMCallRequest``（provider.call 消费）。"""
    from core.base.llm_protocol import LLMCallRequest, OutputContract
    from core.base.llm_protocol.llm_call import PromptSlot
    return LLMCallRequest(
        node_uid="",
        user_prompt=user_prompt,
        prompt_slots=[PromptSlot(kind="user_sys", text=sys_prompt)] if sys_prompt else [],
        output_contract=OutputContract(expected_type=expected_type),
    )


REASONING_LONG = (
    "this is a deliberately verbose response containing many more than ten words "
    "that plainly ignores the one word instruction and rambles on at length yes indeed"
)


# ---------------------------------------------------------------------------
# ① probe 为 setup-time 显式动作（MOCK 路径）
# ---------------------------------------------------------------------------


class TestProbeMockPath:
    def test_mock_returns_success_and_sets_standard_caps(self):
        plugin = _plugin_mock()
        assert plugin.probe_model() == "MOCK_PROBE_SUCCESS"
        assert plugin._model_capabilities["probed"] is True
        assert plugin._model_capabilities["is_reasoning"] is False

    def test_mock_path_never_builds_network_client(self):
        from ibci_modules.ibci_ai.core import MOCK_CLIENT_SENTINEL

        plugin = _plugin_mock()
        plugin.probe_model()
        # MOCK 路径下 _init_client 只置哨兵，不构造真实 OpenAI 客户端；
        # probe 成功即证明未走 chat.completions 网络路径。
        assert plugin._client == MOCK_CLIENT_SENTINEL


# ---------------------------------------------------------------------------
# ③a 推理判定 / 标准判定三路径（真实客户端替身）
# ---------------------------------------------------------------------------


class TestProbeReasoningDetection:
    def test_reasoning_via_long_verbose_content(self):
        plugin = _plugin_with_fake(
            responder=lambda *a, **k: _completion(content=REASONING_LONG)
        )
        assert plugin.probe_model() == "REASONING_MODEL"
        assert plugin._model_capabilities["is_reasoning"] is True

    def test_reasoning_via_reasoning_field(self):
        plugin = _plugin_with_fake(
            responder=lambda *a, **k: _completion(
                content="", reasoning="internal chain of thought..."
            )
        )
        assert plugin.probe_model() == "REASONING_MODEL"
        assert plugin._model_capabilities["is_reasoning"] is True

    def test_reasoning_via_thinking_marker(self):
        plugin = _plugin_with_fake(
            responder=lambda *a, **k: _completion(
                content="Thinking Process: the sky is blue"
            )
        )
        assert plugin.probe_model() == "REASONING_MODEL"

    def test_standard_short_content(self):
        plugin = _plugin_with_fake(responder=lambda *a, **k: _completion(content="YES"))
        assert plugin.probe_model() == "STANDARD_MODEL"
        assert plugin._model_capabilities["is_reasoning"] is False


# ---------------------------------------------------------------------------
# ③b 失败兜底路径
# ---------------------------------------------------------------------------


class TestProbeFailureFallback:
    def test_failure_falls_back_to_reasoning(self):
        def boom(*a, **k):
            raise RuntimeError("network down")

        plugin = _plugin_with_fake(responder=boom)
        assert plugin.probe_model() == "PROBE_FAILED_FALLBACK_REASONING"
        assert plugin._model_capabilities["is_reasoning"] is True


# ---------------------------------------------------------------------------
# ③c 消费方决策：__call__ 依 is_reasoning 注入 ANSWER: 或使用原 prompt
# ---------------------------------------------------------------------------


class TestConsumerDecision:
    def test_call_injects_answer_for_reasoning_model(self):
        sys_prompts = []

        def responder(*a, **k):
            sys_prompts.append(k["messages"][0]["content"])
            if len(sys_prompts) == 1:  # 探测轮：长文 → 判定推理模型
                return _completion(content=REASONING_LONG)
            return _completion(content="ANSWER: final")

        plugin = _plugin_with_fake(responder=responder)
        plugin.probe_model()
        plugin.call(_mcreq("sys", "user"))
        assert len(sys_prompts) == 2
        assert "ANSWER:" in sys_prompts[1]

    def test_call_no_answer_injection_for_standard_model(self):
        sys_prompts = []

        def responder(*a, **k):
            sys_prompts.append(k["messages"][0]["content"])
            return _completion(content="YES")

        plugin = _plugin_with_fake(responder=responder)
        plugin.probe_model()
        plugin.call(_mcreq("sys", "user"))
        assert len(sys_prompts) == 2
        assert "ANSWER:" not in sys_prompts[1]

    def test_unprobed_defaults_conservative_reasoning(self):
        sys_prompts = []

        def responder(*a, **k):
            sys_prompts.append(k["messages"][0]["content"])
            return _completion(content="ANSWER: hi")

        plugin = _plugin_with_fake(responder=responder)
        # 未 probe 直接调用：不触发懒探测，保守回退为推理策略 → 注入 ANSWER:
        plugin.call(_mcreq("sys", "user"))
        assert "ANSWER:" in sys_prompts[0]

    def test_unprobed_emits_warning_once(self, capsys):
        plugin = _plugin_with_fake(responder=lambda *a, **k: _completion(content="ANSWER: hi"))
        plugin.call(_mcreq("sys", "user"))
        plugin.call(_mcreq("sys", "user"))
        captured = capsys.readouterr()
        # 未探测告警仅首次触发一次（去重，避免热路径刷屏）
        assert captured.out.count("未调用 ai.probe_model()") == 1

    def test_warning_resets_after_set_config(self, capsys):
        plugin = _plugin_with_fake(responder=lambda *a, **k: _completion(content="ANSWER: hi"))
        plugin.call(_mcreq("sys", "user"))
        capsys.readouterr()  # 清空第一个告警窗口
        # 切换模型触发 set_config → 重置探测状态与告警去重 → 再次告警
        plugin.set_config("https://llm.invalid/v2", "sk-fake-2", "fake-model-2")
        plugin._client = FakeClient(lambda *a, **k: _completion(content="ANSWER: hi"))
        plugin.call(_mcreq("sys", "user"))
        captured = capsys.readouterr()
        assert captured.out.count("未调用 ai.probe_model()") == 1


# ---------------------------------------------------------------------------
# ② _model_capabilities 只读消费不变式
# ---------------------------------------------------------------------------


class TestCapabilitiesReadOnly:
    def test_capabilities_unchanged_across_calls_after_probe(self):
        plugin = _plugin_with_fake(responder=lambda *a, **k: _completion(content="short"))
        plugin.probe_model()
        before = dict(plugin._model_capabilities)

        plugin.call(_mcreq("sys one", "user one"))
        plugin.call(_mcreq("sys two", "user two"))
        plugin.call(_mcreq("sys three", "user three"))

        assert plugin._model_capabilities == before

    def test_probe_after_set_config_resets_probed_flag(self):
        plugin = _plugin_with_fake(responder=lambda *a, **k: _completion(content="YES"))
        plugin.probe_model()
        assert plugin._model_capabilities["probed"] is True
        # 切换模型触发 set_config → 重置 probed，需重新显式探测
        plugin.set_config("https://llm.invalid/v2", "sk-fake-2", "fake-model-2")
        plugin._client = FakeClient(lambda *a, **k: _completion(content="YES"))
        assert plugin._model_capabilities["probed"] is False