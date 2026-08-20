# -*- coding: utf-8 -*-
"""
tests/e2e/test_intent_priority_flow.py
=======================================

（PT-TEST-2 覆盖缺口补齐）意图优先级与 return 清除语义的判别测试。

- INV-INTENT-PRIORITY-2：smear（@ 一次性）意图排在持久栈（@+）之后——
  自定义 provider 捕获 LLM 调用意图层（``LLMCallRequest.intents.merged``），
  断言顺序 = 持久栈在前、smear 在后。
- INV-INTENT-FLOW-3：return 清除 smear 意图——函数体内的一次性意图在
  return 后不泄漏到调用方后续 LLM 调用。

判别方式：宿主绑定 provider 记录每次 LLM 调用的合并意图列表（顺序敏感）。
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
    'import python "prio_rec_mod" as lib:\n'
    "    bind provider -> any\n"
)


def _run_ibci(code: str, tmp_path, monkeypatch):
    (tmp_path / "prio_rec_mod.py").write_text(_REC_PROVIDER_SRC, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    out = []
    eng = IBCIEngine(root_dir=os.getcwd())
    eng.run_string(_BIND + code, output_callback=lambda s: out.append(str(s)), silent=True)
    return out, eng


def _active_provider(eng):
    return eng.capability_registry.get(CapabilityRegistry.CAP_LLM_PROVIDER)


class TestIntentPrioritySmearAfterStack:
    def test_smear_intent_comes_after_persistent_stack(self, tmp_path, monkeypatch):
        """INV-INTENT-PRIORITY-2: @+ 持久栈意图在前、@ smear 一次性意图在后。"""
        code = (
            "import ai\n"
            "ai.set_provider(lib.provider)\n"
            "@+ \"STACK_A\"\n"
            "@+ \"STACK_B\"\n"
            "@ \"SMEAR_C\"\n"
            "str r = @~ call ~\n"
            "print(r)\n"
        )
        out, eng = _run_ibci(code, tmp_path, monkeypatch)
        assert out == ["OK"], out
        prov = _active_provider(eng)
        assert prov is not None and prov.calls, "provider 未被内核调用"
        merged = prov.calls[-1]
        # 顺序：持久栈（STACK_A, STACK_B）在前，smear（SMEAR_C）在后
        assert merged == ["STACK_A", "STACK_B", "SMEAR_C"], f"意图顺序错误: {merged}"


class TestIntentReturnClearsSmear:
    def test_return_clears_function_smear_intent(self, tmp_path, monkeypatch):
        """INV-INTENT-FLOW-3: return 清除 smear 意图——函数内一次性意图不泄漏到调用方。"""
        code = (
            "import ai\n"
            "ai.set_provider(lib.provider)\n"
            "func g() -> str:\n"
            "    @ SMEAR_IN_FUNC\n"
            "    return \"done\"\n"
            "str ignored = g()\n"
            "str r = @~ call_after_return ~\n"
            "print(r)\n"
        )
        out, eng = _run_ibci(code, tmp_path, monkeypatch)
        assert out == ["OK"], out
        prov = _active_provider(eng)
        assert prov is not None and prov.calls, "provider 未被内核调用"
        merged = prov.calls[-1]
        # 函数 return 后 smear 已清除：调用方 LLM 调用看不到函数内的一次性意图
        assert "SMEAR_IN_FUNC" not in merged, f"return 后 smear 泄漏: {merged}"
