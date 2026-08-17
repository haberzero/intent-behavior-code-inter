"""tests/runtime/test_idbg.py — idbg 插件单元测试（pure Python，不需要 IBCI 引擎）。

F3-1 起 idbg 的 spec 内联于 builtin_modules.BUILTIN_MODULE_SPECS（不再有 ibci_modules/.../_spec.py
磁盘文件），此处直接断言内联 spec 成员契约。
"""
from core.runtime.bootstrap.builtin_modules import BUILTIN_MODULE_SPECS
from ibci_modules.ibci_idbg.core import IDbgPlugin


class _DummyCapabilityRegistry:
    def __init__(self):
        self._store = {}

    def register(self, name, provider, plugin_id=None, priority=50):
        self._store[name] = provider

    def get(self, name):
        return self._store.get(name)


class _DummyCapabilities:
    def __init__(self, kernel_registry, capability_registry):
        self.kernel_registry = kernel_registry
        self._capability_registry = capability_registry

    def expose(self, name, provider):
        self._capability_registry.register(name, provider)


class _DummyStateReader:
    def get_vars(self):
        return {"x": 1}

    def get_llm_except_frames(self):
        return []

    def get_active_intents(self):
        return []


class _DummyStackInspector:
    def get_call_stack_depth(self):
        return 3

    def get_active_intents(self):
        return ["intent-a"]


class _DummyExecutionContext:
    """假内核执行上下文：只提供结构化保护映射查询（内核逻辑另测）。"""

    def __init__(self, protection_map):
        self._protection_map = protection_map

    def get_llmexcept_protection_map(self):
        return self._protection_map


class _DummyKernelRegistry:
    def __init__(self, protection_map):
        self._state_reader = _DummyStateReader()
        self._stack_inspector = _DummyStackInspector()
        self._execution_context = _DummyExecutionContext(protection_map)

    def get_state_reader(self):
        return self._state_reader

    def get_stack_inspector(self):
        return self._stack_inspector

    def get_llm_executor(self):
        return None

    def get_execution_context(self):
        return self._execution_context


def _make_plugin(protection_map):
    cap_registry = _DummyCapabilityRegistry()
    kr = _DummyKernelRegistry(protection_map)
    plugin = IDbgPlugin()
    plugin.setup(_DummyCapabilities(kr, cap_registry))
    return plugin


class TestIdbgSpec:
    def test_vtable_exports_new_print_methods(self):
        members = BUILTIN_MODULE_SPECS["idbg"].members
        assert "print_vars" in members
        assert "protection_map" in members
        assert "show_retry_stack" in members
        assert "show_protection_map" in members
        assert "show_env" in members


class TestIdbgProtectionMap:
    def test_protection_map_delegates_to_kernel_query(self):
        """idbg.protection_map 消费内核结构化查询（不直扫 node_pool）。"""
        canned = {"target_1": "handler_1", "cond_1": "handler_2"}
        plugin = _make_plugin(canned)
        assert plugin.protection_map() == canned

    def test_protection_map_empty_without_execution_context(self):
        kr = _DummyKernelRegistry({})
        kr._execution_context = None
        plugin = IDbgPlugin()
        plugin.setup(_DummyCapabilities(kr, _DummyCapabilityRegistry()))
        assert plugin.protection_map() == {}

    def test_show_protection_map_prints_output(self, capsys):
        plugin = _make_plugin({"target_1": "handler_1"})
        plugin.show_protection_map()
        out = capsys.readouterr().out
        assert "[IDBG] llmexcept 保护映射:" in out
        assert "target_1 -> handler_1" in out
