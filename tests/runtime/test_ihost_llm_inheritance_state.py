"""
tests/runtime/test_ihost_llm_inheritance.py

ihost 子环境 LLM 配置继承（E1）白箱契约（设计：
E1 子环境 LLM 配置继承（状态面）；E2E 面见 tests/e2e/）：

- 快照 = spawn 时点活状态深拷贝（父后续变异不影响快照）；
- 快照含命名模型注册表（@NAME~ 路由面补漏）；
- _apply_llm_inheritance：正常应用 / 非 stateful provider 跳过 /
  损坏快照 fail-safe（kernel_diagnostic 警告，不阻断）；
- on_ready 钩子时序（解释器就绪后、执行开始前，恰一次）。
"""
import warnings

from core.engine import _apply_llm_inheritance
from core.extension.ibcext import IbStatefulPlugin


class _FakeStatefulProvider(IbStatefulPlugin):
    """最小 stateful provider（快照存/取契约）。"""

    def __init__(self, config):
        self._config = dict(config)
        self.restored = None

    def save_plugin_state(self):
        return {"config": dict(self._config), "model_registry": {}}

    def restore_plugin_state(self, state):
        self.restored = state
        if isinstance(state.get("config"), dict):
            self._config.update(state["config"])
        else:
            # 损坏快照面（restore 内部 fail-fast；_apply 侧捕获 → 警告）
            raise ValueError(f"corrupt snapshot config: {state.get('config')!r}")


class _FakeRegistry:
    def __init__(self, provider):
        self._provider = provider

    def get(self, name):
        return self._provider


class _FakeEngine:
    def __init__(self, provider):
        class _CR:
            CAP_LLM_PROVIDER = "llm_provider"
        self.capability_registry = _FakeRegistry(provider)
        self._cr = _CR


class TestSnapshotSemantics:
    def test_snapshot_is_deep_copy(self):
        """save 后父活状态变异 → 快照不变（spawn 时点值语义）。"""
        from ibci_modules.ibci_ai.provider_impl import RecommendedProvider
        prov = RecommendedProvider.__new__(RecommendedProvider)
        # 最小构造面：仅 _config / _model_registry / _return_type_prompts
        prov._config = {"mock": True, "model": "m1", "url": None, "key": None}
        prov._model_registry = {"nm": {"url": "u", "key": "k", "model": "mm"}}
        prov._return_type_prompts = {"int": "p"}
        snap = prov.save_plugin_state()
        prov._config["mock"] = False          # 父变异
        prov._config["model"] = "m2"
        prov._model_registry["nm2"] = {}
        assert snap["config"]["mock"] is True
        assert snap["config"]["model"] == "m1"
        assert "nm2" not in snap["model_registry"]

    def test_snapshot_contains_named_model_registry(self):
        """命名模型注册表入快照（补漏面——活配置状态一部分）。"""
        from ibci_modules.ibci_ai.provider_impl import RecommendedProvider
        prov = RecommendedProvider.__new__(RecommendedProvider)
        prov._config = {"mock": False, "url": None, "key": None}
        prov._model_registry = {"nm": {"url": "u", "key": "k", "model": "mm"}}
        prov._return_type_prompts = {}
        snap = prov.save_plugin_state()
        assert snap["model_registry"]["nm"]["model"] == "mm"

    def test_restore_rebuilds_config_and_registry(self):
        """restore 面：config + 命名模型注册表 + 客户端缓存重置。"""
        from ibci_modules.ibci_ai.provider_impl import RecommendedProvider
        prov = RecommendedProvider.__new__(RecommendedProvider)
        prov._config = {"mock": False, "url": None, "key": None, "model": None}
        prov._model_registry = {}
        prov._return_type_prompts = {"int": "default"}
        prov._named_clients = {"nm": "stale-client"}
        prov._client = "stale"
        prov._model_capabilities = {"probed": True}
        prov._unprobed_warned = True
        prov.restore_plugin_state({
            "config": {"mock": True, "model": "m1"},
            "model_registry": {"nm": {"url": "u", "key": "k", "model": "mm"}},
        })
        assert prov._config["mock"] is True and prov._config["model"] == "m1"
        assert prov._model_registry["nm"]["model"] == "mm"
        assert prov._named_clients == {}       # 客户端缓存整体重置
        assert prov._client is None
        assert prov._model_capabilities["probed"] is False


class TestApplyInheritance:
    def test_apply_success(self):
        provider = _FakeStatefulProvider({"mock": False})
        eng = _FakeEngine(provider)
        _apply_llm_inheritance(eng, {"config": {"mock": True}, "model_registry": {}})
        assert provider._config["mock"] is True
        assert provider.restored is not None

    def test_apply_non_stateful_skips_with_warning(self):
        """非 stateful provider = 跳过继承 + kernel_diagnostic 显形。"""
        eng = _FakeEngine(object())  # 非 stateful
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _apply_llm_inheritance(eng, {"config": {}})
        # 警告投影 = 人类文本（码字面量在事件投影 detail 面，不入 warn 文本）
        assert any("继承跳过" in str(w.message) for w in caught)

    def test_apply_corrupt_snapshot_fail_safe(self):
        """损坏快照 = 警告不阻断（子照常执行，LLM 调用按自身状态得清晰错误）。"""
        provider = _FakeStatefulProvider({"mock": True})
        eng = _FakeEngine(provider)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _apply_llm_inheritance(eng, {"config": "corrupt-not-dict"})
        # 警告投影 = 人类文本（码字面量在事件投影 detail 面，不入 warn 文本）
        assert any("继承应用失败" in str(w.message) for w in caught)
        assert provider._config["mock"] is True  # 原状保留（未被损坏状态污染）


class TestOnReadyHook:
    def test_hook_fires_once_before_execution(self):
        """on_ready = 解释器就绪后、执行开始前，恰一次（收引擎引用）。"""
        from core.engine import IBCIEngine
        from tests.conftest import TESTS_ROOT
        engine = IBCIEngine(root_dir=TESTS_ROOT)
        seen = []
        print_marker = []
        engine.run_string(
            "print('hello')",
            output_callback=lambda t: print_marker.append(t),
            silent=True,
            on_ready=lambda e: seen.append(e),
        )
        assert len(seen) == 1
        assert seen[0] is engine
        assert print_marker == ["hello"]

    def test_no_hook_zero_intrusion(self):
        from tests.conftest import run_ibci
        out = run_ibci("print('plain')")
        assert out == ["plain"]
