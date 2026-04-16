"""
tests/runtime/test_plugin_lifecycle.py

Unit tests for the plugin lifecycle, capability system, and stateful/stateless protocols.

Coverage:
  - IbPlugin base class
  - IbStatelessPlugin marker
  - IbStatefulPlugin protocol
  - PluginCapabilities injection
  - Plugin exposure and revocation
  - Plugin state save/restore
"""

import pytest
from core.extension.ibcext import IbPlugin, IbStatelessPlugin, IbStatefulPlugin
from core.extension.capabilities import PluginCapabilities


# ---------------------------------------------------------------------------
# 1. IbPlugin base class
# ---------------------------------------------------------------------------

class TestIbPlugin:
    def test_plugin_id_default(self):
        class MyPlugin(IbPlugin):
            pass
        p = MyPlugin()
        assert "MyPlugin" in p.plugin_id

    def test_plugin_id_custom(self):
        class MyPlugin(IbPlugin):
            pass
        p = MyPlugin(plugin_id="my_custom_id")
        assert p.plugin_id == "my_custom_id"

    def test_setup_stores_capabilities(self):
        class MyPlugin(IbPlugin):
            pass
        p = MyPlugin()
        caps = PluginCapabilities()
        p.setup(caps)
        assert p._capabilities is caps

    def test_exposed_capabilities_initially_empty(self):
        class MyPlugin(IbPlugin):
            pass
        p = MyPlugin()
        assert p.get_exposed_capabilities() == {}


# ---------------------------------------------------------------------------
# 2. IbStatelessPlugin marker
# ---------------------------------------------------------------------------

class TestIbStatelessPlugin:
    def test_is_mixin(self):
        class MyStateless(IbStatelessPlugin):
            def setup(self, capabilities):
                pass
        p = MyStateless()
        assert isinstance(p, IbStatelessPlugin)

    def test_no_abstract_methods(self):
        """IbStatelessPlugin should not require any abstract method implementations."""
        class Minimal(IbStatelessPlugin):
            pass
        p = Minimal()  # Should not raise


# ---------------------------------------------------------------------------
# 3. IbStatefulPlugin protocol
# ---------------------------------------------------------------------------

class TestIbStatefulPlugin:
    def test_cannot_instantiate_without_implementation(self):
        """IbStatefulPlugin is ABC, cannot be instantiated directly."""
        with pytest.raises(TypeError):
            IbStatefulPlugin()

    def test_requires_save_and_restore(self):
        """Must implement both save_plugin_state and restore_plugin_state."""
        # Missing restore_plugin_state
        with pytest.raises(TypeError):
            class PartialPlugin(IbStatefulPlugin):
                def save_plugin_state(self):
                    return {}
            PartialPlugin()

    def test_complete_implementation(self):
        class CompletePlugin(IbStatefulPlugin):
            def __init__(self):
                self.data = {}

            def save_plugin_state(self):
                return {"data": dict(self.data)}

            def restore_plugin_state(self, state):
                self.data = state.get("data", {})

        p = CompletePlugin()
        p.data["key"] = "value"

        # Save
        saved = p.save_plugin_state()
        assert saved == {"data": {"key": "value"}}

        # Restore
        p2 = CompletePlugin()
        p2.restore_plugin_state(saved)
        assert p2.data == {"key": "value"}

    def test_save_restore_roundtrip(self):
        """Full save → modify → restore cycle."""
        class ConfigPlugin(IbStatefulPlugin):
            def __init__(self):
                self.config = {"timeout": 30, "retries": 3}

            def save_plugin_state(self):
                return {"config": dict(self.config)}

            def restore_plugin_state(self, state):
                self.config = state.get("config", {})

        p = ConfigPlugin()
        saved = p.save_plugin_state()

        # Modify state
        p.config["timeout"] = 60
        assert p.config["timeout"] == 60

        # Restore to saved state
        p.restore_plugin_state(saved)
        assert p.config["timeout"] == 30


# ---------------------------------------------------------------------------
# 4. PluginCapabilities
# ---------------------------------------------------------------------------

class TestPluginCapabilities:
    def test_default_fields_none(self):
        caps = PluginCapabilities()
        assert caps.llm_provider is None
        assert caps.llm_executor is None
        assert caps.state_reader is None
        assert caps.service_context is None

    def test_expose_and_get(self):
        caps = PluginCapabilities()
        caps._capability_registry = MockCapabilityRegistry()
        caps.expose("test_cap", "test_provider")
        # Just ensure no crash; the registry handles storage

    def test_revoke(self):
        caps = PluginCapabilities()
        caps._capability_registry = MockCapabilityRegistry()
        caps.expose("test_cap", "test_provider")
        caps.revoke("test_cap")
        # Just ensure no crash


class MockCapabilityRegistry:
    """Minimal mock for capability registry."""
    def __init__(self):
        self._store = {}

    def register(self, name, provider, plugin_id=None, priority=50, **kwargs):
        self._store[name] = provider

    def unregister(self, name, plugin_id=None, **kwargs):
        self._store.pop(name, None)

    def unregister_all(self, plugin_id=None, **kwargs):
        self._store.clear()


# ---------------------------------------------------------------------------
# 5. AI Plugin state roundtrip
# ---------------------------------------------------------------------------

class TestAIPluginStateful:
    def test_ai_plugin_implements_stateful(self):
        from ibci_modules.ibci_ai.core import AIPlugin
        p = AIPlugin()
        assert isinstance(p, IbStatefulPlugin)

    def test_ai_plugin_save_restore(self):
        from ibci_modules.ibci_ai.core import AIPlugin
        p = AIPlugin()
        # Use TESTONLY mode to avoid openai import
        p.set_config("TESTONLY", "TESTONLY", "TESTONLY")

        saved = p.save_plugin_state()
        assert saved["config"]["url"] == "TESTONLY"
        assert saved["config"]["key"] == "TESTONLY"
        assert saved["config"]["model"] == "TESTONLY"

        p2 = AIPlugin()
        p2.restore_plugin_state(saved)
        assert p2._config["url"] == "TESTONLY"
        assert p2._config["model"] == "TESTONLY"
