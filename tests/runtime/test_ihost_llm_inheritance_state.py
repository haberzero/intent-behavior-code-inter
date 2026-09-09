"""
tests/runtime/test_ihost_llm_inheritance_state.py

ihost 子环境 LLM 配置继承（E1）白箱契约（设计：
E1 子环境 LLM 配置继承（状态面）；E2E 面见 tests/e2e/）：

- 快照 = spawn 时点活状态深拷贝（父后续变异不影响快照）；
- 快照含命名模型注册表（@NAME~ 路由面补漏）；
- restore 重建配置 + 命名模型注册表 + 客户端缓存重置；
- on_ready 钩子时序（解释器就绪后、执行开始前，恰一次）。

注：进程级隔离下子进程经 api_config.json 自动发现继承端点/模型/密钥；
运行时 model_registry 变化继承归 B2（temp JSON 文件传递快照）。
"""
import warnings

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
            raise ValueError(f"corrupt snapshot config: {state.get('config')!r}")


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
        # mock 模式：restore 恢复 MOCK_CLIENT_SENTINEL（与 set_mock_mode 同语义）
        from ibci_modules.ibci_ai.provider_impl import MOCK_CLIENT_SENTINEL
        assert prov._client is MOCK_CLIENT_SENTINEL
        assert prov._model_capabilities["probed"] is True


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
