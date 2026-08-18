# -*- coding: utf-8 -*-
"""
tests/e2e/test_intent_callable_embedding.py
============================================

G5/G2（意图一等值）：函数/可调用/行为实例放入意图注释时应渲染为**有意义的
可调用契约**（bogus ``func helper() -> str`` / ``fn_callable[...]`` /
``behavior[...]``），而非 Python repr（``<Function 'helper'>`` / ``<FnCallable ...>``）。

判别方式：自定义宿主绑定 provider 记录每次 LLM 调用的意图层
（``LLMCallRequest.intents.merged``），断言契约嵌入。
"""
import os

from core.engine import IBCIEngine
from core.runtime.capability_registry import CapabilityRegistry

_REC_PROVIDER_SRC = '''\
from core.base.llm_protocol.llm_call import LLMCallResult
class RecProvider:
    def __init__(self):
        self.calls = []
    def call(self, request):
        self.calls.append(list(request.intents.merged))
        return LLMCallResult(content="OK")
    def stream(self, request):
        yield "OK"
    def get_retry(self):
        return 1
    def is_auto_intent_injection_enabled(self):
        return True
    def get_current_call_info(self):
        return {}
provider = RecProvider()
'''

_BIND = (
    'import python "embed_rec_mod" as lib:\n'
    "    bind provider -> any\n"
)


def _run(code: str, tmp_path, monkeypatch):
    (tmp_path / "embed_rec_mod.py").write_text(_REC_PROVIDER_SRC, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    eng = IBCIEngine(root_dir=os.getcwd())
    eng.run_string(_BIND + code, silent=True)
    return eng.capability_registry.get(CapabilityRegistry.CAP_LLM_PROVIDER)


def _embed(body: str, tmp_path, monkeypatch):
    code = "import ai\nai.set_provider(lib.provider)\n" + body
    prov = _run(code, tmp_path, monkeypatch)
    assert prov is not None and prov.calls, "provider 未被调用"
    return prov.calls[-1], prov.calls


class TestIntentCallableEmbedding:
    def test_function_value_embeds_meaningful_contract(self, tmp_path, monkeypatch):
        """函数值放入意图 → 渲染可调用契约 ``func name(params) -> ret``，非 repr。"""
        merged, _ = _embed(
            "func helper(int n, str tag) -> str:\n"
            "    return tag\n"
            "@+ 请调用 $helper\n"
            "@~ call ~\n",
            tmp_path, monkeypatch,
        )
        joined = " ".join(merged)
        assert "func helper(int, str) -> str" in joined, f"契约未嵌入: {merged}"
        assert "<Function" not in joined, f"repr 泄漏: {merged}"

    def test_snapshot_callable_embeds_signature_name(self, tmp_path, monkeypatch):
        """snapshot 可调用实例（fn_callable）放入意图 → 契约签名形式。"""
        merged, _ = _embed(
            "func helper() -> str:\n"
            "    return 'H'\n"
            "fn s = snapshot -> auto: helper()\n"
            "@+ 捕获 $s\n"
            "@~ call ~\n",
            tmp_path, monkeypatch,
        )
        joined = " ".join(merged)
        assert "fn_callable" in joined, f"fn_callable 契约未嵌入: {merged}"
        assert "<FnCallable" not in joined, f"repr 泄漏: {merged}"
