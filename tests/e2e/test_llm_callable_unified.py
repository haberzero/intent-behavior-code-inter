# -*- coding: utf-8 -*-
"""
tests/e2e/test_llm_callable_unified.py
========================================

用户 llm 可调用类（实现 ``LLMCallable`` 协议的 ``__llm_call__`` 方法）
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
            "active": list(request.intents.active),
            "global": list(request.intents.global_),
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

_BIND_TEMPLATE = (
    'import python "{rec}" as lib:\n'
    "    bind provider -> any\n"
    'import python "{inv}" as lib2:\n'
    "    bind invoke -> any\n"
)

_import_counter = [0]


def _run(body: str, tmp_path, monkeypatch):
    # 每测试唯一模块名：避免 Python sys.modules 缓存导致 provider 实例/统计跨测试累积。
    _import_counter[0] += 1
    rec = f"llcmod_{_import_counter[0]}_rec"
    inv = f"llcmod_{_import_counter[0]}_inv"
    (tmp_path / f"{rec}.py").write_text(_REC_PROVIDER_SRC, encoding="utf-8")
    (tmp_path / f"{inv}.py").write_text(_INVOKE_SRC, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    out = []
    eng = IBCIEngine(root_dir=os.getcwd())
    code = (
        _BIND_TEMPLATE.format(rec=rec, inv=inv) +
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
        """run_batch 统一接受用户 llm 可调用实例（行为语义保留；
        llm 类逐项一次调用，item 仅在 __llm_call__ 声明 item 参时参数化）。"""
        body = (
            "class Translator:\n"
            "    func __llm_call__(self) -> dict:\n"
            "        str prompt = \"批量「\" + self.text + \"」\"\n"
            "        return {\"user_prompt\": prompt}\n"
            "    str text = \"\"\n"
            "Translator tr = Translator()\n"
            "tr.text = \"x\"\n"
            "list results = ai.run_batch(tr, [0])\n"
            "print(results)\n"
        )
        out, eng = _run(body, tmp_path, monkeypatch)
        prov = eng.capability_registry.get(CapabilityRegistry.CAP_LLM_PROVIDER)
        assert prov is not None and prov.calls, "run_batch 未触发统一装配路径"
        assert prov.calls[-1]["user_prompt"] == "批量「x」", f"prompt={prov.calls[-1]['user_prompt']}"
        assert any("TRANSLATED_OK" in line for line in out), f"结果未返回: {out}"

    def test_run_batch_items_parameterize_llm_callable(self, tmp_path, monkeypatch):
        """run_batch 逐项以 item 参装配（__llm_call__(self, any item) →
        每 item 一次 LLM 调用，装配随 item 变化）。"""
        body = (
            "class Greeter:\n"
            "    func __llm_call__(self, any item) -> dict:\n"
            "        return {\"user_prompt\": \"欢迎\" + str(item)}\n"
            "Greeter g = Greeter()\n"
            "list results = ai.run_batch(g, [1, 2])\n"
            "print(results)\n"
        )
        out, eng = _run(body, tmp_path, monkeypatch)
        prov = eng.capability_registry.get(CapabilityRegistry.CAP_LLM_PROVIDER)
        assert prov is not None and prov.calls, "run_batch 未逐项装配"
        assert len(prov.calls) == 2, f"应逐项 2 次调用: {len(prov.calls)}"
        prompts = [c["user_prompt"] for c in prov.calls]
        assert "欢迎1" in prompts and "欢迎2" in prompts, f"items 未逐项参数化: {prompts}"


class TestLLMCallableIntentRewrite:
    """``__intent__`` 可选协议方法运行时发现 + 装配改写合并。

    判别：用户 llm 类声明 ``func __intent__(self, dict intents) -> dict`` 时，装配入口
    发现并调用——返回 dict 中存在的键替换对应意图层（消解/增删/重排），缺失的键保持
    原层（合并语义透传）；未声明时意图原样透传。provider 记录请求的意图三层供断言。
    """

    def test_intent_rewrites_merged_and_maps_three_layers(self, tmp_path, monkeypatch):
        """__intent__ 读入三层 dict（验证 global 层映射），改写 merged；active/global 透传。"""
        body = (
            'ai.set_global_intent("钱是身外之物")\n'
            "class Rewriter:\n"
            "    func __intent__(self, dict intents) -> dict:\n"
            "        return {\"merged\": [\"改写自:\" + intents[\"global\"][0]]}\n"
            "    func __llm_call__(self) -> dict:\n"
            "        return {\"user_prompt\": \"hi\"}\n"
            "Rewriter r = Rewriter()\n"
            "@+ 优雅论述\n"
            "lib2.invoke(r)\n"
            "print(\"done\")\n"
        )
        out, eng = _run(body, tmp_path, monkeypatch)
        assert out and out[0] == "done", out
        prov = eng.capability_registry.get(CapabilityRegistry.CAP_LLM_PROVIDER)
        assert prov is not None and prov.calls, "provider 未被调用"
        last = prov.calls[-1]
        # __intent__ 改写了 merged（读入 global 层并前置"改写自:"）
        assert last["merged"] == ["改写自:钱是身外之物"], f"merged={last['merged']}"
        # 缺失的键保持原层：global / active 透传
        assert last["global"] == ["钱是身外之物"], f"global={last['global']}"
        assert "优雅论述" in last["active"], f"active={last['active']}"

    def test_intent_explicit_empty_list_clears_layer(self, tmp_path, monkeypatch):
        """显式空列表 = 清空该层（消解 merged）；其余层保持。"""
        body = (
            'ai.set_global_intent("钱是身外之物")\n'
            "class Rewriter:\n"
            "    func __intent__(self, dict intents) -> dict:\n"
            "        return {\"merged\": []}\n"
            "    func __llm_call__(self) -> dict:\n"
            "        return {\"user_prompt\": \"hi\"}\n"
            "Rewriter r = Rewriter()\n"
            "lib2.invoke(r)\n"
            "print(\"done\")\n"
        )
        out, eng = _run(body, tmp_path, monkeypatch)
        prov = eng.capability_registry.get(CapabilityRegistry.CAP_LLM_PROVIDER)
        assert prov is not None and prov.calls, "provider 未被调用"
        last = prov.calls[-1]
        assert last["merged"] == [], f"merged 应按显式空列表清空: {last['merged']}"
        assert last["global"] == ["钱是身外之物"], f"global 应透传: {last['global']}"

    def test_intent_without_declaration_passes_intents_through(self, tmp_path, monkeypatch):
        """未声明 __intent__ 的 llm 类：意图原样透传（行为默认透传语义）。"""
        body = (
            'ai.set_global_intent("钱是身外之物")\n'
            "class Plain:\n"
            "    func __llm_call__(self) -> dict:\n"
            "        return {\"user_prompt\": \"hi\"}\n"
            "Plain p = Plain()\n"
            "@+ 优雅论述\n"
            "lib2.invoke(p)\n"
            "print(\"done\")\n"
        )
        out, eng = _run(body, tmp_path, monkeypatch)
        prov = eng.capability_registry.get(CapabilityRegistry.CAP_LLM_PROVIDER)
        assert prov is not None and prov.calls, "provider 未被调用"
        last = prov.calls[-1]
        # 未改写：merged = 原始合并消解结果（至少包含 global 意图项）
        assert "钱是身外之物" in last["merged"], f"merged={last['merged']}"
        assert "优雅论述" in last["active"], f"active={last['active']}"

    def test_intent_run_batch_inherits_rewrite(self, tmp_path, monkeypatch):
        """run_batch（共用统一装配入口）自动继承 __intent__ 改写，逐项均生效。"""
        body = (
            "class Rewriter:\n"
            "    func __intent__(self, dict intents) -> dict:\n"
            "        return {\"merged\": [\"批量改写\"]}\n"
            "    func __llm_call__(self, any item) -> dict:\n"
            "        return {\"user_prompt\": \"hi\"}\n"
            "Rewriter r = Rewriter()\n"
            "list results = ai.run_batch(r, [1, 2])\n"
            "print(results)\n"
        )
        out, eng = _run(body, tmp_path, monkeypatch)
        prov = eng.capability_registry.get(CapabilityRegistry.CAP_LLM_PROVIDER)
        assert prov is not None and prov.calls, "run_batch 未触发装配"
        assert len(prov.calls) == 2, f"应逐项 2 次调用: {len(prov.calls)}"
        for call in prov.calls:
            assert call["merged"] == ["批量改写"], f"merged={call['merged']}"

    def test_intent_contract_violations_fail_fast(self, tmp_path, monkeypatch):
        """契约违约 fail-fast：参数数非 1 / 返回非 dict → TypeError 显式暴露。"""
        import pytest

        bad_param_count = (
            "class Bad:\n"
            "    func __intent__(self) -> dict:\n"
            "        return {\"merged\": []}\n"
            "    func __llm_call__(self) -> dict:\n"
            "        return {\"user_prompt\": \"hi\"}\n"
            "Bad b = Bad()\n"
            "lib2.invoke(b)\n"
        )
        with pytest.raises(Exception) as exc_param:
            _run(bad_param_count, tmp_path, monkeypatch)
        assert "exactly one argument" in str(exc_param.value), str(exc_param.value)

        bad_return = (
            "class Bad:\n"
            "    func __intent__(self, dict intents) -> str:\n"
            "        return \"x\"\n"
            "    func __llm_call__(self) -> dict:\n"
            "        return {\"user_prompt\": \"hi\"}\n"
            "Bad b = Bad()\n"
            "lib2.invoke(b)\n"
        )
        with pytest.raises(Exception) as exc_ret:
            _run(bad_return, tmp_path, monkeypatch)
        assert "__intent__ must return a config dict" in str(exc_ret.value), str(exc_ret.value)


class TestLLMCallableExpectedTypeUserClass:
    """llm-callable ``expected_type`` 裸用户类名解析（KERNEL_ISSUE-LLM-4 回归）。

    expected_type 是运行时字符串（裸名如 ``"Resp"``），直接传给解析器会因注册表键
    为 module 限定名而 miss，退化为默认 str 解析（__from_prompt__ 不生效）。
    修复：装配时按 callable 类 module 限定裸名，VTableParsingStrategy 命中运行时
    类键后经 __from_prompt__ 解析用户类。
    """

    def test_expected_type_bare_user_class_parses_via_from_prompt(self, tmp_path, monkeypatch):
        """静态形态 __from_prompt__：expected_type=裸 "Resp" → 返回 Resp 实例（非 str）。"""
        body = (
            "class Resp:\n"
            "    str text\n"
            "    func __init__(self, str text) -> auto:\n"
            "        self.text = text\n"
            "    func __from_prompt__(str raw) -> tuple:\n"
            "        return (True, Resp(raw.strip()))\n"
            "class 取:\n"
            "    func __llm_call__(self) -> dict:\n"
            "        return {\"user_prompt\": \"hi\", \"expected_type\": \"Resp\"}\n"
            "取 inst = 取()\n"
            "Resp r = inst()\n"
            "print(\"text=\" + r.text)\n"
        )
        out, eng = _run(body, tmp_path, monkeypatch)
        assert any("text=TRANSLATED_OK" in line for line in out), f"未经 __from_prompt__ 解析为用户类: {out}"

    def test_expected_type_bare_user_class_instance_form(self, tmp_path, monkeypatch):
        """实例形态 __from_prompt__(self, raw)：同样解析为用户类实例。"""
        body = (
            "class Resp:\n"
            "    str text\n"
            "    func __init__(self, str text) -> auto:\n"
            "        self.text = text\n"
            "    func __from_prompt__(self, str raw) -> tuple:\n"
            "        return (True, Resp(raw.strip()))\n"
            "class 取:\n"
            "    func __llm_call__(self) -> dict:\n"
            "        return {\"user_prompt\": \"hi\", \"expected_type\": \"Resp\"}\n"
            "取 inst = 取()\n"
            "Resp r = inst()\n"
            "print(\"text=\" + r.text)\n"
        )
        out, eng = _run(body, tmp_path, monkeypatch)
        assert any("text=TRANSLATED_OK" in line for line in out), f"实例形态未解析为用户类: {out}"
