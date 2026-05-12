from ibci_modules.ibci_idbg._spec import __ibcext_vtable__
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

    def get_last_llm_result(self):
        return None

    def get_llm_except_frames(self):
        return []

    def get_active_intents(self):
        return []


class _DummyStackInspector:
    def get_instruction_count(self):
        return 12

    def get_call_stack_depth(self):
        return 3

    def get_active_intents(self):
        return ["intent-a"]


class _DummyExecutionContext:
    def __init__(self, node_pool):
        self.node_pool = node_pool


class _DummyKernelRegistry:
    def __init__(self, node_pool):
        self._state_reader = _DummyStateReader()
        self._stack_inspector = _DummyStackInspector()
        self._execution_context = _DummyExecutionContext(node_pool)

    def get_state_reader(self):
        return self._state_reader

    def get_stack_inspector(self):
        return self._stack_inspector

    def get_llm_executor(self):
        return None

    def get_execution_context(self):
        return self._execution_context


def _make_plugin(node_pool):
    cap_registry = _DummyCapabilityRegistry()
    kr = _DummyKernelRegistry(node_pool)
    plugin = IDbgPlugin()
    plugin.setup(_DummyCapabilities(kr, cap_registry))
    return plugin


class TestIdbgSpec:
    def test_vtable_exports_new_print_methods(self):
        funcs = __ibcext_vtable__()["functions"]
        assert "print_vars" in funcs
        assert "protection_map" in funcs
        assert "show_retry_stack" in funcs
        assert "show_protection_map" in funcs
        assert "show_env" in funcs


class TestIdbgProtectionMap:
    def test_protection_map_collects_llmexcept_links(self):
        node_pool = {
            "target_1": {"_type": "IbExprStmt"},
            "handler_1": {"_type": "IbLLMExceptionalStmt", "target": "target_1", "body": []},
            "cond_1": {"_type": "IbBehaviorExpr"},
            "filtered_1": {"_type": "IbFilteredExpr", "expr": "cond_1", "filter": "f1"},
            "handler_2": {"_type": "IbLLMExceptionalStmt", "target": "cond_1", "body": []},
            "for_1": {"_type": "IbFor", "iter": "filtered_1", "llmexcept_handler": "handler_2"},
        }
        plugin = _make_plugin(node_pool)
        mapping = plugin.protection_map()

        assert mapping["target_1"] == "handler_1"
        assert mapping["cond_1"] == "handler_2"

    def test_show_protection_map_prints_output(self, capsys):
        node_pool = {
            "target_1": {"_type": "IbExprStmt"},
            "handler_1": {"_type": "IbLLMExceptionalStmt", "target": "target_1", "body": []},
        }
        plugin = _make_plugin(node_pool)
        plugin.show_protection_map()
        out = capsys.readouterr().out
        assert "[IDBG] llmexcept 保护映射:" in out
        assert "target_1 -> handler_1" in out
