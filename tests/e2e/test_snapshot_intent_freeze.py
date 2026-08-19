# -*- coding: utf-8 -*-
"""
tests/e2e/test_snapshot_intent_freeze.py
==========================================

snapshot 意图冻结补齐——纯 snapshot lambda（非行为体，
fn_callable 路径）同样在**定义时刻**冻结意图栈，调用时忽略调用处意图；
lambda 保持调用点 live（高阶函数透明：lambda 看到调用点的意图 fork 副本）。

判别方式：自定义宿主绑定 provider 记录每次 LLM 调用的意图层
（``LLMCallRequest.intents.active``），断言冻结 vs live。
"""
import os

import pytest

from core.engine import IBCIEngine
from core.runtime.capability_registry import CapabilityRegistry

_REC_PROVIDER_SRC = '''\
from core.base.llm_protocol.llm_call import LLMCallResult
class RecProvider:
    def __init__(self):
        self.calls = []
    def call(self, request):
        self.calls.append({
            "active": list(request.intents.active),
            "merged": list(request.intents.merged),
        })
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
    'import python "snap_rec_mod" as lib:\n'
    "    bind provider -> any\n"
)


def _run_ibci(code: str, tmp_path, monkeypatch):
    (tmp_path / "snap_rec_mod.py").write_text(_REC_PROVIDER_SRC, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    out = []
    eng = IBCIEngine(root_dir=os.getcwd())
    eng.run_string(_BIND + code, output_callback=lambda s: out.append(str(s)), silent=True)
    return out, eng


def _active_provider(eng):
    return eng.capability_registry.get(CapabilityRegistry.CAP_LLM_PROVIDER)


class TestSnapshotIntentFreeze:
    def test_pure_snapshot_lambda_freezes_definition_intent(self, tmp_path, monkeypatch):
        """纯 snapshot lambda（body 非行为体 → fn_callable 路径）调用时使用定义
        时刻意图，忽略调用处意图。"""
        code = (
            "import ai\n"
            "ai.set_provider(lib.provider)\n"
            "\n"
            "func helper() -> str:\n"
            "    str r = @~ call ~\n"
            "    return r\n"
            "\n"
            "func runit(fn g) -> str:\n"
            "    return g()\n"
            "\n"
            "@ DEF_INTENT_DEF\n"
            "fn s = snapshot -> auto: helper()\n"
            "\n"
            "@ CALL_INTENT_IGNORED\n"
            "str out = runit(s)\n"
            "print(out)\n"
        )
        out, eng = _run_ibci(code, tmp_path, monkeypatch)
        assert out == ["OK"], out
        prov = _active_provider(eng)
        assert prov is not None and prov.calls, "provider 未被内核调用"
        last = prov.calls[-1]
        # 冻结（经 @ smear 消解进 merged）：定义时刻意图在，调用处意图被忽略
        assert "DEF_INTENT_DEF" in last["merged"], f"定义意图未冻结: {last['merged']}"
        assert "CALL_INTENT_IGNORED" not in last["merged"], f"调用处意图泄漏入冻结: {last['merged']}"

    def test_lambda_keeps_call_site_intent(self, tmp_path, monkeypatch):
        """lambda（非 snapshot）不冻结：调用处意图生效（lambda 分支对照）。"""
        code = (
            "import ai\n"
            "ai.set_provider(lib.provider)\n"
            "\n"
            "func helper() -> str:\n"
            "    str r = @~ call ~\n"
            "    return r\n"
            "\n"
            "func runit(fn g) -> str:\n"
            "    return g()\n"
            "\n"
            "@ DEF_INTENT_DEF\n"
            "fn s = lambda -> auto: helper()\n"
            "\n"
            "@ CALL_INTENT_ACTIVE\n"
            "str out = runit(s)\n"
            "print(out)\n"
        )
        out, eng = _run_ibci(code, tmp_path, monkeypatch)
        assert out == ["OK"], out
        prov = _active_provider(eng)
        last = prov.calls[-1]
        # lambda：调用处意图 live，经 @ smear 消解进 merged
        assert "CALL_INTENT_ACTIVE" in last["merged"], f"调用处意图缺失: {last['merged']}"
