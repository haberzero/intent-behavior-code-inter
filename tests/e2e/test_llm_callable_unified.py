# -*- coding: utf-8 -*-
"""
tests/e2e/test_llm_callable_unified.py
========================================

P4b-2a：用户 llm 可调用类（实现 ``LLMCallable`` 协议的 ``__llm_call__`` 方法）
经**统一装配入口** ``invoke_llm_callable_cps`` 消费——协议门
（``satisfies_protocol(..., 'llm_callable')``）→ 用户 ``__llm_call__`` 返回装配
配置 dict → 内核映射为 ``LLMCallRequest`` → 统一 worker（``_call_and_parse``）。

判别：自定义宿主绑定 provider 记录收到请求的 ``user_prompt`` / ``output_hint``，
断言用户 llm 类的装配生效。
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
        self.calls.append({
            "user_prompt": request.user_prompt,
            "output_hint": request.output_contract.output_hint,
            "merged": list(request.intents.merged),
        })
        return LLMCallResult(content="TRANSLATED_OK")
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

_INVOKE_SRC = '''\
def invoke(inst):
    from core.runtime.frame import get_current_execution_context
    from core.runtime.coordinator import _drive_generator
    ec = get_current_execution_context()
    if ec is None or ec.vm_executor is None:
        raise RuntimeError("no active execution context")
    llm_exec = ec.registry.get_llm_executor()
    gen = llm_exec.invoke_llm_callable_cps(inst, ec)
    return _drive_generator(ec.vm_executor, gen)
'''

_BIND = (
    'import python "llc_rec_mod" as lib:\n'
    "    bind provider -> any\n"
    'import python "llc_invoke_mod" as lib2:\n'
    "    bind invoke -> any\n"
)


def _run(body: str, tmp_path, monkeypatch):
    (tmp_path / "llc_rec_mod.py").write_text(_REC_PROVIDER_SRC, encoding="utf-8")
    (tmp_path / "llc_invoke_mod.py").write_text(_INVOKE_SRC, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    out = []
    eng = IBCIEngine(root_dir=os.getcwd())
    code = (
        _BIND +
        "import ai\nai.set_provider(lib.provider)\n" +
        body
    )
    eng.run_string(code, output_callback=lambda s: out.append(str(s)), silent=True)
    return out, eng


class TestLLMCallableUnifiedInvoke:
    def test_user_llm_callable_assembled_and_executed(self, tmp_path, monkeypatch):
        """用户 llm 类 __llm_call__ 返回装配 dict → 统一 worker 执行，provider 收到装配。"""
        body = (
            "class Translator:\n"
            "    func __llm_call__(self) -> dict:\n"
            "        str prompt = \"将「\" + self.text + \"」翻译为\" + self.target_lang\n"
            "        return {\"user_prompt\": prompt, \"output_hint\": \"只输出译文\"}\n"
            "\n"
            "    str text = \"\"\n"
            "    str target_lang = \"英语\"\n"
            "\n"
            "Translator tr = Translator()\n"
            "tr.text = \"hello\"\n"
            "lib2.invoke(tr)\n"
            "print(\"done\")\n"
        )
        out, eng = _run(body, tmp_path, monkeypatch)
        assert out and out[0] == "done", out
        prov = eng.capability_registry.get(CapabilityRegistry.CAP_LLM_PROVIDER)
        assert prov is not None and prov.calls, "provider 未被调用（统一装配路径未执行）"
        last = prov.calls[-1]
        # 用户 __llm_call__ 装配的 user_prompt / output_hint 生效
        assert last["user_prompt"] == "将「hello」翻译为英语", f"user_prompt={last['user_prompt']}"
        assert last["output_hint"] == "只输出译文"

    def test_non_llm_callable_rejected_fail_fast(self, tmp_path, monkeypatch):
        """不满足 LLMCallable 的值 → 统一装配入口 fail-fast（satisfies 唯一判定）。"""
        body = (
            "class Plain:\n"
            "    func not_llm_call(self) -> str:\n"
            "        return 'x'\n"
            "Plain p = Plain()\n"
            "lib2.invoke(p)\n"
        )
        import pytest
        # 编译期 Plain 不满足 llm_callable；运行时入口须 fail-fast
        # （ibci 层调用 host invoke → 内部抛 TypeError）。
        with pytest.raises(Exception) as exc:
            engout, eng = _run(body, tmp_path, monkeypatch)
        assert "LLMCallable" in str(exc.value) or "llm_callable" in str(exc.value)

    def test_run_batch_accepts_llm_callable_instance(self, tmp_path, monkeypatch):
        """P4b-2b：run_batch 统一接受用户 llm 可调用实例（行为语义保留；
        llm 类经统一装配执行一次，返回单元素结果）。"""
        body = (
            "class Translator:\n"
            "    func __llm_call__(self) -> dict:\n"
            "        str prompt = \"批量「\" + self.text + \"」\"\n"
            "        return {\"user_prompt\": prompt}\n"
            "    str text = \"\"\n"
            "Translator tr = Translator()\n"
            "tr.text = \"x\"\n"
            "list results = ai.run_batch(tr, [])\n"
            "print(results)\n"
        )
        out, eng = _run(body, tmp_path, monkeypatch)
        prov = eng.capability_registry.get(CapabilityRegistry.CAP_LLM_PROVIDER)
        assert prov is not None and prov.calls, "run_batch 未触发统一装配路径"
        assert prov.calls[-1]["user_prompt"] == "批量「x」", f"prompt={prov.calls[-1]['user_prompt']}"
        assert any("TRANSLATED_OK" in line for line in out), f"结果未返回: {out}"
