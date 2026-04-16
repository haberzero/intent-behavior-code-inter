"""
tests/sdk/test_check_plugin.py

Unit tests for ibci_sdk.check module.

Coverage:
  - CheckResult data structure
  - check_plugin on valid plugins (ibci_math, ibci_json, etc.)
  - check_plugin on invalid/missing directories
  - check_plugin detects missing _spec.py
  - check_plugin detects missing methods
  - check_plugin detects IbStatefulPlugin incomplete implementations
"""

import os
import tempfile
import pytest

from ibci_sdk.check import check_plugin, CheckResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULES_DIR = os.path.join(REPO_ROOT, "ibci_modules")


# ---------------------------------------------------------------------------
# 1. CheckResult structure
# ---------------------------------------------------------------------------

class TestCheckResult:
    def test_ok_when_no_errors(self):
        result = CheckResult(plugin_dir="/fake")
        assert result.ok is True

    def test_not_ok_when_errors(self):
        result = CheckResult(plugin_dir="/fake", errors=["something wrong"])
        assert result.ok is False

    def test_str_representation_ok(self):
        result = CheckResult(plugin_dir="/fake")
        text = str(result)
        assert "All checks passed" in text

    def test_str_representation_error(self):
        result = CheckResult(plugin_dir="/fake", errors=["missing _spec.py"])
        text = str(result)
        assert "ERROR" in text
        assert "missing _spec.py" in text

    def test_str_representation_warning(self):
        result = CheckResult(plugin_dir="/fake", warnings=["optional field"])
        text = str(result)
        assert "WARN" in text


# ---------------------------------------------------------------------------
# 2. Valid plugin checks (existing ibci_modules)
# ---------------------------------------------------------------------------

class TestCheckValidPlugins:
    @pytest.mark.parametrize("plugin_name", [
        "ibci_math", "ibci_json", "ibci_time", "ibci_schema",
    ])
    def test_non_invasive_plugins_pass(self, plugin_name):
        plugin_dir = os.path.join(MODULES_DIR, plugin_name)
        if not os.path.isdir(plugin_dir):
            pytest.skip(f"Plugin {plugin_name} not found")
        result = check_plugin(plugin_dir)
        assert result.ok, f"{plugin_name} failed: {result.errors}"

    def test_ibci_net_passes(self):
        plugin_dir = os.path.join(MODULES_DIR, "ibci_net")
        if not os.path.isdir(plugin_dir):
            pytest.skip("ibci_net not found")
        result = check_plugin(plugin_dir)
        assert result.ok, f"ibci_net failed: {result.errors}"


# ---------------------------------------------------------------------------
# 3. Invalid plugin scenarios
# ---------------------------------------------------------------------------

class TestCheckInvalidPlugins:
    def test_nonexistent_directory(self):
        result = check_plugin("/definitely/not/a/real/path")
        assert not result.ok
        assert any("does not exist" in e for e in result.errors)

    def test_missing_spec_py(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create __init__.py but no _spec.py
            init_path = os.path.join(tmpdir, "__init__.py")
            with open(init_path, "w") as f:
                f.write("pass")
            result = check_plugin(tmpdir)
            assert not result.ok
            assert any("_spec.py not found" in e for e in result.errors)

    def test_missing_init_py(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = os.path.join(tmpdir, "_spec.py")
            with open(spec_path, "w") as f:
                f.write("""
def __ibcext_metadata__():
    return {"name": "test", "version": "1.0.0", "description": "test"}

def __ibcext_vtable__():
    return {"functions": {}}
""")
            result = check_plugin(tmpdir)
            assert not result.ok
            assert any("__init__.py not found" in e for e in result.errors)

    def test_spec_missing_metadata_function(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = os.path.join(tmpdir, "_spec.py")
            with open(spec_path, "w") as f:
                f.write("""
def __ibcext_vtable__():
    return {"functions": {}}
""")
            init_path = os.path.join(tmpdir, "__init__.py")
            with open(init_path, "w") as f:
                f.write("""
class Impl:
    pass
def create_implementation():
    return Impl()
""")
            result = check_plugin(tmpdir)
            assert not result.ok
            assert any("__ibcext_metadata__" in e for e in result.errors)

    def test_spec_missing_vtable_function(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = os.path.join(tmpdir, "_spec.py")
            with open(spec_path, "w") as f:
                f.write("""
def __ibcext_metadata__():
    return {"name": "test", "version": "1.0.0", "description": "test"}
""")
            init_path = os.path.join(tmpdir, "__init__.py")
            with open(init_path, "w") as f:
                f.write("""
class Impl:
    pass
def create_implementation():
    return Impl()
""")
            result = check_plugin(tmpdir)
            assert not result.ok
            assert any("__ibcext_vtable__" in e for e in result.errors)

    def test_missing_declared_method(self):
        """Vtable declares a method but implementation doesn't have it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = os.path.join(tmpdir, "_spec.py")
            with open(spec_path, "w") as f:
                f.write("""
def __ibcext_metadata__():
    return {"name": "test", "version": "1.0.0", "description": "test"}

def __ibcext_vtable__():
    return {
        "functions": {
            "do_something": {"param_types": ["str"], "return_type": "str"},
        }
    }
""")
            init_path = os.path.join(tmpdir, "__init__.py")
            with open(init_path, "w") as f:
                f.write("""
class Impl:
    pass
def create_implementation():
    return Impl()
""")
            result = check_plugin(tmpdir)
            assert not result.ok
            assert any("do_something" in e and "not found" in e for e in result.errors)

    def test_param_count_mismatch(self):
        """Vtable declares more params than implementation provides."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = os.path.join(tmpdir, "_spec.py")
            with open(spec_path, "w") as f:
                f.write("""
def __ibcext_metadata__():
    return {"name": "test", "version": "1.0.0", "description": "test"}

def __ibcext_vtable__():
    return {
        "functions": {
            "add": {"param_types": ["int", "int", "int"], "return_type": "int"},
        }
    }
""")
            init_path = os.path.join(tmpdir, "__init__.py")
            with open(init_path, "w") as f:
                f.write("""
class Impl:
    def add(self, a, b):
        return a + b
def create_implementation():
    return Impl()
""")
            result = check_plugin(tmpdir)
            assert not result.ok
            assert any("param" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# 4. IbStatefulPlugin incomplete detection
# ---------------------------------------------------------------------------

class TestCheckStateful:
    def test_incomplete_stateful_save_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = os.path.join(tmpdir, "_spec.py")
            with open(spec_path, "w") as f:
                f.write("""
def __ibcext_metadata__():
    return {"name": "test", "version": "1.0.0", "description": "test"}

def __ibcext_vtable__():
    return {"functions": {}}
""")
            init_path = os.path.join(tmpdir, "__init__.py")
            with open(init_path, "w") as f:
                f.write("""
class Impl:
    def save_plugin_state(self):
        return {}
def create_implementation():
    return Impl()
""")
            result = check_plugin(tmpdir)
            assert any("restore_plugin_state" in e for e in result.errors)

    def test_complete_stateful_no_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = os.path.join(tmpdir, "_spec.py")
            with open(spec_path, "w") as f:
                f.write("""
def __ibcext_metadata__():
    return {"name": "test", "version": "1.0.0", "description": "test"}

def __ibcext_vtable__():
    return {"functions": {}}
""")
            init_path = os.path.join(tmpdir, "__init__.py")
            with open(init_path, "w") as f:
                f.write("""
class Impl:
    def save_plugin_state(self):
        return {}
    def restore_plugin_state(self, state):
        pass
def create_implementation():
    return Impl()
""")
            result = check_plugin(tmpdir)
            # Should not have stateful-related errors
            assert not any("save_plugin_state" in e or "restore_plugin_state" in e for e in result.errors)
