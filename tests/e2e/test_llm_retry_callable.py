# -*- coding: utf-8 -*-
"""
tests/e2e/test_llm_retry_callable.py
=====================================

P4d：``__retry__`` 可选协议方法（retry 高阶化，决策 5）——llm 可调用类声明
重试策略（``{"max_retry": int, "hint": str}``），统一装配入口发现并解析
（``_discover_optional_protocol_method``，与 ``__intent__`` P4b-3a 同通道），
``invoke`` 路径据此驱动重试循环：不确定轮次经 _prompt_assembly 单一消息构造
累积多轮对话（``message_history`` 回喂 provider），达到 ``max_retry`` 仍不确定
则返回最后一次不确定结果交语句层（llmexcept 接管 / 无帧则 LLMParseError）。

判别：自定义宿主绑定 provider 按序返回 MOCK_REPAIR（不确定）后成功，断言
重试轮数、`message_history` 的 hint/原始响应注入、耗尽语义、契约违约 fail-fast。
"""
import importlib
import os

from core.engine import IBCIEngine
from core.runtime.capability_registry import CapabilityRegistry

_REC_PROVIDER_SRC = '''\
from core.base.llm_protocol.llm_call import LLMCallResult, MOCK_REPAIR_SENTINEL
class RecProvider:
    def __init__(self):
        self.calls = []
        self.fail_times = 0
    def call(self, request):
        self.calls.append({
            "user_prompt": request.user_prompt,
            "message_history": request.message_history,
        })
        if len(self.calls) <= self.fail_times:
            return LLMCallResult(content=MOCK_REPAIR_SENTINEL)
        return LLMCallResult(content="TRANSLATED_OK")
    def stream(self, request):
        yield "OK"
    def get_retry(self):
        return 3
    def is_auto_intent_injection_enabled(self):
        return True
    def get_current_call_info(self):
        return {}
provider = RecProvider()
'''

_BIND_TEMPLATE = (
    'import python "{rec}" as lib:\n'
    "    bind provider -> any\n"
)

_import_counter = [0]


def _run(body: str, tmp_path, monkeypatch, fail_times: int = 0):
    # 每测试唯一模块名（前缀独立于 test_llm_callable_unified.py 的 llcmod_*，
    # 避免同一 pytest 进程内 sys.modules 同名模块相撞）：避免 Python sys.modules
    # 缓存导致 provider 实例/统计跨测试累积。
    _import_counter[0] += 1
    rec = f"llcretry_{_import_counter[0]}_rec"
    (tmp_path / f"{rec}.py").write_text(_REC_PROVIDER_SRC, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    # 预导入并设置失败轮数：IBCI 宿主导入走 importlib.import_module（复用 sys.modules），
    # 测试侧直接改模块级 provider 实例状态，避免过多宿主绑定。
    mod = importlib.import_module(rec)
    mod.provider.fail_times = fail_times
    out = []
    eng = IBCIEngine(root_dir=os.getcwd())
    code = (
        _BIND_TEMPLATE.format(rec=rec) +
        "import ai\nai.set_provider(lib.provider)\n" +
        body
    )
    try:
        eng.run_string(code, output_callback=lambda s: out.append(str(s)), silent=True)
        return out, eng, None
    except Exception as e:  # 语言级错误（LLMParseError / TypeError）经引擎抛出
        return out, eng, e


def _provider(eng) -> "RecProvider":
    prov = eng.capability_registry.get(CapabilityRegistry.CAP_LLM_PROVIDER)
    assert prov is not None, "provider 未注册"
    return prov


_TRANSLATOR_RETRY = (
    "class Translator:\n"
    "    func __retry__(self) -> dict:\n"
    '        return {"max_retry": 2, "hint": "严格输出"}\n'
    "    func __llm_call__(self) -> dict:\n"
    '        return {"user_prompt": "将「\" + self.text + \"」翻译为英语"}\n'
    "    str text = \"\"\n"
    "\n"
    "Translator tr = Translator()\n"
    "tr.text = \"hello\"\n"
)


class TestLLMRetryCallable:
    def test_retry_policy_retries_and_injects_hint(self, tmp_path, monkeypatch):
        """`__retry__` 声明 max_retry=2 + hint：首轮不确定 → hint 经多轮对话回喂
        下一轮 → 成功。provider 收到 2 次调用，第 2 次 message_history 含 hint
        与首轮 assistant 原始响应。"""
        body = _TRANSLATOR_RETRY + (
            "any r = tr()\n"
            "print(r)\n"
        )
        out, eng, exc = _run(body, tmp_path, monkeypatch, fail_times=1)
        assert exc is None, f"重试后应成功: {exc}"
        prov = _provider(eng)
        assert len(prov.calls) == 2, f"应重试 1 轮共 2 次调用: {len(prov.calls)}"
        last = prov.calls[-1]
        history = last["message_history"]
        assert history, "重试轮应携带 message_history"
        roles = [m["role"] for m in history]
        assert roles == ["assistant", "user"], f"roles={roles}"
        assert "MOCK" in history[0]["content"], (
            f"assistant 应为首轮原始响应: {history[0]['content']!r}"
        )
        assert "补充要求：严格输出" in history[1]["content"], (
            f"hint 应注入 retry 轮 user 消息: {history[1]['content']!r}"
        )
        # 首轮调用（不确定）不应带 message_history
        assert prov.calls[0]["message_history"] is None
        assert any("TRANSLATED_OK" in line for line in out), f"最终结果未返回: {out}"

    def test_retry_policy_exhaustion_passes_uncertain_to_statement_layer(self, tmp_path, monkeypatch):
        """耗尽语义：max_retry=2 且 provider 恒不确定 → 恰 2 次调用后返回不确定
        结果交语句层；赋值点无 llmexcept 帧 → LLMParseError 显式抛出。"""
        body = _TRANSLATOR_RETRY + (
            "any r = tr()\n"
        )
        out, eng, exc = _run(body, tmp_path, monkeypatch, fail_times=99)
        prov = _provider(eng)
        assert len(prov.calls) == 2, f"应恰 2 次调用后耗竭: {len(prov.calls)}"
        assert exc is not None, "耗尽后应抛 LLMParseError（无 llmexcept 帧）"
        assert "parse" in str(exc).lower() or "LLM" in str(exc), str(exc)

    def test_no_retry_declaration_single_call(self, tmp_path, monkeypatch):
        """未声明 `__retry__`：不自动重试（行为与现状一致），第 1 次不确定即交
        语句层（LLMParseError），恰 1 次调用。"""
        body = (
            "class Plain:\n"
            "    func __llm_call__(self) -> dict:\n"
            '        return {"user_prompt": "hi"}\n'
            "Plain p = Plain()\n"
            "any r = p()\n"
        )
        out, eng, exc = _run(body, tmp_path, monkeypatch, fail_times=1)
        prov = _provider(eng)
        assert len(prov.calls) == 1, f"未声明 __retry__ 应不自动重试: {len(prov.calls)}"
        assert exc is not None
        assert "parse" in str(exc).lower() or "LLM" in str(exc), str(exc)

    def test_retry_policy_empty_dict_uses_default_max_retry(self, tmp_path, monkeypatch):
        """空策略 dict（声明 `__retry__` 但无键）→ 启用默认 max_retry=3 的策略重试。"""
        body = (
            "class Trans:\n"
            "    func __retry__(self) -> dict:\n"
            '        return {}\n'
            "    func __llm_call__(self) -> dict:\n"
            '        return {"user_prompt": "hi"}\n'
            "Trans t = Trans()\n"
            "any r = t()\n"
        )
        out, eng, exc = _run(body, tmp_path, monkeypatch, fail_times=99)
        prov = _provider(eng)
        # 默认 max_retry=3：恰 3 次调用后耗竭
        assert len(prov.calls) == 3, f"默认 max_retry=3 应恰 3 次调用: {len(prov.calls)}"

    def test_retry_policy_run_batch_inherits_retry_loop(self, tmp_path, monkeypatch):
        """run_batch 逐项经统一装配入口（invoke 路径）自动继承 `__retry__` 循环：
        首轮不确定 → 按策略重试 → 成功。"""
        body = (
            "class Trans:\n"
            "    func __retry__(self) -> dict:\n"
            '        return {"max_retry": 2}\n'
            "    func __llm_call__(self, any item) -> dict:\n"
            '        return {"user_prompt": "hi" + str(item)}\n'
            "Trans t = Trans()\n"
            "list results = ai.run_batch(t, [1])\n"
            "print(results)\n"
        )
        out, eng, exc = _run(body, tmp_path, monkeypatch, fail_times=1)
        assert exc is None, f"返回报错应成功: {exc}"
        prov = _provider(eng)
        assert len(prov.calls) == 2, f"run_batch 首项应经 1 轮重试共 2 次调用: {len(prov.calls)}"
        assert any("TRANSLATED_OK" in line for line in out), f"批量结果未返回: {out}"

    def test_retry_contract_violations_fail_fast(self, tmp_path, monkeypatch):
        """契约违约 fail-fast：`__retry__` 带参 / 返回非 dict → TypeError 显式暴露。"""
        bad_param = (
            "class Bad:\n"
            "    func __retry__(self, any x) -> dict:\n"
            '        return {"max_retry": 2}\n'
            "    func __llm_call__(self) -> dict:\n"
            '        return {"user_prompt": "hi"}\n'
            "Bad b = Bad()\n"
            "any r = b()\n"
        )
        out, eng, exc_param = _run(bad_param, tmp_path, monkeypatch)
        assert exc_param is not None
        assert "__retry__ must take no arguments" in str(exc_param), str(exc_param)

        bad_return = (
            "class Bad:\n"
            "    func __retry__(self) -> str:\n"
            '        return "x"\n'
            "    func __llm_call__(self) -> dict:\n"
            '        return {"user_prompt": "hi"}\n'
            "Bad b = Bad()\n"
            "any r = b()\n"
        )
        out, eng, exc_ret = _run(bad_return, tmp_path, monkeypatch)
        assert exc_ret is not None
        assert "__retry__ must return a config dict" in str(exc_ret), str(exc_ret)