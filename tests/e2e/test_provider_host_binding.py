# -*- coding: utf-8 -*-
"""
tests/e2e/test_provider_host_binding.py
=========================================

F4：自定义 LLM provider 经宿主绑定统一（`ai.set_provider`）。

验证用户经 `import python "<mod>" as lib: bind provider` 声明自定义 provider
（实现 LLMProvider 契约），并经 `ai.set_provider(lib.provider)` 注册为激活的
llm_provider 后，内核 LLM 调用实际走用户 provider（非 stub）。

覆盖：
- 自定义 provider 经宿主绑定 + set_provider → 内核调用返回其响应；
- provider 被内核实际调用（调用计数 > 0）；
- 缺契约方法的 provider 注册 fail-fast。
"""
import os

import pytest

from core.engine import IBCIEngine
from core.runtime.capability_registry import CapabilityRegistry


# --- 自足的自定义 provider 模块（写到临时目录，经 sys.path 可见） ------------ #

_CUSTOM_PROVIDER_SRC = '''\
from core.base.llm_protocol.llm_call import LLMCallResult
class MyProvider:
    def __init__(self):
        self.calls = 0
    def call(self, request):
        self.calls += 1
        return LLMCallResult(content="CUSTOM_PROVIDER_ANSWER")
    def stream(self, request):
        yield "custom"
    def get_retry(self):
        return 1
    def is_auto_intent_injection_enabled(self):
        return True
    def get_current_call_info(self):
        return {"custom": True}
provider = MyProvider()
'''

_BAD_PROVIDER_SRC = '''\
class BadProvider:
    def call(self, request):
        return None
provider = BadProvider()
'''


@pytest.fixture
def provider_mod(tmp_path, monkeypatch):
    """写入自定义 provider Python 模块到 tmp_path，并把其加入 sys.path。"""
    (tmp_path / "custom_provider_mod.py").write_text(_CUSTOM_PROVIDER_SRC, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))


def _run_with_provider(binding_src: str, body: str):
    """构造引擎、绑定 provider、执行 body，返回 (print输出, 引擎)。"""
    out = []
    eng = IBCIEngine(root_dir=os.getcwd())
    code = binding_src + "\n" + body
    eng.run_string(code, output_callback=lambda s: out.append(str(s)), silent=True)
    return out, eng


class TestSetProviderHostBinding:
    def test_custom_provider_invoked_by_kernel(self, provider_mod):
        """用户 provider 经宿主绑定 + set_provider 后被内核实际调用。"""
        binding = (
            'import python "custom_provider_mod" as lib:\n'
            "    bind provider -> any\n"
        )
        body = (
            "import ai\n"
            "ai.set_provider(lib.provider)\n"
            "str result = @~ {hello} ~\n"
            "print(result)\n"
        )
        out, eng = _run_with_provider(binding, body)
        assert out == ["CUSTOM_PROVIDER_ANSWER"], out

        # provider 被内核实际调用（非 stub）：经由能力表读出，验证调用计数
        active = eng.capability_registry.get(CapabilityRegistry.CAP_LLM_PROVIDER)
        assert active.calls >= 1, "kernel 未调用自定义 provider"

    def test_set_provider_registers_high_priority(self, provider_mod):
        """set_provider 后能力表 primary = 用户 provider（HIGH 优先级覆盖默认）。"""
        binding = (
            'import python "custom_provider_mod" as lib:\n'
            "    bind provider -> any\n"
        )
        body = (
            "import ai\n"
            "ai.set_provider(lib.provider)\n"
            'print("ok")\n'
        )
        _, eng = _run_with_provider(binding, body)
        active = eng.capability_registry.get(CapabilityRegistry.CAP_LLM_PROVIDER)
        assert type(active).__name__ == "MyProvider"

    def test_missing_contract_method_fails_fast(self, tmp_path, monkeypatch):
        """缺 LLMProvider 契约方法的 provider → set_provider 抛错（不静默降级）。"""
        (tmp_path / "bad_provider_mod.py").write_text(_BAD_PROVIDER_SRC, encoding="utf-8")
        monkeypatch.syspath_prepend(str(tmp_path))
        out = []
        eng = IBCIEngine(root_dir=os.getcwd())
        code = (
            'import python "bad_provider_mod" as lib:\n'
            "    bind provider -> any\n"
            "import ai\n"
            "ai.set_provider(lib.provider)\n"
        )
        with pytest.raises(Exception) as exc_info:
            eng.run_string(code, output_callback=lambda s: out.append(str(s)), silent=True)
        assert "LLMProvider 契约方法" in str(exc_info.value)


class TestDefaultProviderUnchanged:
    def test_without_set_provider_uses_default(self):
        """未调用 set_provider 时，默认 provider（RecommendedProvider）仍生效。"""
        eng = IBCIEngine(root_dir=os.getcwd())
        out = []
        eng.run_string(
            "import ai\n"
            "print('ok')\n",
            output_callback=lambda s: out.append(str(s)), silent=True,
        )
        active = eng.capability_registry.get(CapabilityRegistry.CAP_LLM_PROVIDER)
        assert active is not None
        assert type(active).__name__ == "AIPlugin"
