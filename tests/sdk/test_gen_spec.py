"""
tests/sdk/test_gen_spec.py

Unit tests for ibci_sdk.gen_spec module.

Coverage:
  - _py_type_to_ibci mapping (all primitive types, Optional, List, Dict, unknown)
  - gen_spec output structure (metadata function, vtable function)
  - gen_spec with methods of various signatures
  - gen_spec with class-level annotations (variables)
  - gen_spec skip_private / skip_setup options
  - gen_spec_file writes to disk
"""

import os
import tempfile
import pytest
from typing import Optional, List, Dict, Any

from ibci_sdk.gen_spec import gen_spec, gen_spec_file, _py_type_to_ibci


# ---------------------------------------------------------------------------
# 1. _py_type_to_ibci mapping
# ---------------------------------------------------------------------------

class TestTypeMapping:
    def test_str(self):
        assert _py_type_to_ibci(str) == "str"

    def test_int(self):
        assert _py_type_to_ibci(int) == "int"

    def test_float(self):
        assert _py_type_to_ibci(float) == "float"

    def test_bool(self):
        assert _py_type_to_ibci(bool) == "bool"

    def test_list(self):
        assert _py_type_to_ibci(list) == "list"

    def test_dict(self):
        assert _py_type_to_ibci(dict) == "dict"

    def test_none_type(self):
        assert _py_type_to_ibci(type(None)) == "void"

    def test_none_literal(self):
        assert _py_type_to_ibci(None) == "void"

    def test_typing_list(self):
        assert _py_type_to_ibci(List[str]) == "list"

    def test_typing_dict(self):
        assert _py_type_to_ibci(Dict[str, int]) == "dict"

    def test_optional_maps_to_any(self):
        assert _py_type_to_ibci(Optional[int]) == "any"

    def test_unknown_type_maps_to_any(self):
        class CustomType:
            pass
        assert _py_type_to_ibci(CustomType) == "any"

    def test_string_forward_ref(self):
        assert _py_type_to_ibci("str") == "str"
        assert _py_type_to_ibci("int") == "int"
        assert _py_type_to_ibci("Any") == "any"
        assert _py_type_to_ibci("unknown_forward") == "any"

    def test_empty_param(self):
        """inspect.Parameter.empty should map to 'any'."""
        import inspect
        assert _py_type_to_ibci(inspect.Parameter.empty) == "any"


# ---------------------------------------------------------------------------
# 2. gen_spec output structure
# ---------------------------------------------------------------------------

class SamplePlugin:
    """A sample plugin for testing."""
    version: str

    def hello(self, name: str) -> str:
        """Say hello."""
        return f"Hello, {name}"

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    def no_return(self, x: float) -> None:
        """No return value."""
        pass

    def no_annotation(self, x):
        """No type annotations."""
        pass

    def _private_method(self):
        """Should be skipped by default."""
        pass

    def setup(self, capabilities):
        """Framework hook, should be skipped by default."""
        pass


class TestGenSpec:
    def test_output_is_string(self):
        result = gen_spec(SamplePlugin, name="sample")
        assert isinstance(result, str)

    def test_contains_metadata_function(self):
        result = gen_spec(SamplePlugin, name="sample", version="1.2.3")
        assert "def __ibcext_metadata__" in result
        assert '"name": "sample"' in result
        assert '"version": "1.2.3"' in result

    def test_contains_vtable_function(self):
        result = gen_spec(SamplePlugin, name="sample")
        assert "def __ibcext_vtable__" in result
        assert '"functions"' in result

    def test_hello_method_in_vtable(self):
        result = gen_spec(SamplePlugin, name="sample")
        assert '"hello"' in result
        assert "['str']" in result  # param_types

    def test_add_method_in_vtable(self):
        result = gen_spec(SamplePlugin, name="sample")
        assert '"add"' in result
        assert "['int', 'int']" in result

    def test_no_return_maps_to_void(self):
        result = gen_spec(SamplePlugin, name="sample")
        assert '"no_return"' in result
        # return_type should be 'void'
        assert "'void'" in result

    def test_no_annotation_maps_to_any(self):
        result = gen_spec(SamplePlugin, name="sample")
        assert '"no_annotation"' in result
        assert "'any'" in result

    def test_private_methods_skipped(self):
        result = gen_spec(SamplePlugin, name="sample", skip_private=True)
        assert "_private_method" not in result

    def test_private_methods_included_when_disabled(self):
        result = gen_spec(SamplePlugin, name="sample", skip_private=False)
        assert "_private_method" in result

    def test_setup_skipped_by_default(self):
        result = gen_spec(SamplePlugin, name="sample", skip_setup=True)
        assert '"setup"' not in result

    def test_setup_included_when_disabled(self):
        result = gen_spec(SamplePlugin, name="sample", skip_setup=False)
        assert '"setup"' in result

    def test_class_level_annotations_as_variables(self):
        result = gen_spec(SamplePlugin, name="sample")
        assert '"variables"' in result
        assert '"version"' in result

    def test_default_name_from_class(self):
        result = gen_spec(SamplePlugin)
        assert '"name": "sampleplugin"' in result

    def test_description(self):
        result = gen_spec(SamplePlugin, name="sample", description="A test plugin")
        assert '"description": "A test plugin"' in result

    def test_generated_code_is_valid_python(self):
        """The generated code should be syntactically valid Python."""
        result = gen_spec(SamplePlugin, name="sample")
        compile(result, "<gen_spec>", "exec")

    def test_generated_vtable_is_executable(self):
        """The generated vtable function should return a valid dict."""
        result = gen_spec(SamplePlugin, name="sample")
        namespace = {}
        exec(result, namespace)
        vtable = namespace["__ibcext_vtable__"]()
        assert isinstance(vtable, dict)
        assert "functions" in vtable
        assert isinstance(vtable["functions"], dict)
        assert "hello" in vtable["functions"]

    def test_generated_metadata_is_executable(self):
        result = gen_spec(SamplePlugin, name="sample", version="2.0.0")
        namespace = {}
        exec(result, namespace)
        meta = namespace["__ibcext_metadata__"]()
        assert meta["name"] == "sample"
        assert meta["version"] == "2.0.0"


# ---------------------------------------------------------------------------
# 3. gen_spec_file writes to disk
# ---------------------------------------------------------------------------

class TestGenSpecFile:
    def test_file_is_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "_spec.py")
            gen_spec_file(SamplePlugin, path, name="sample")
            assert os.path.exists(path)

    def test_file_content_matches_gen_spec(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "_spec.py")
            gen_spec_file(SamplePlugin, path, name="sample")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            expected = gen_spec(SamplePlugin, name="sample")
            assert content == expected


# ---------------------------------------------------------------------------
# 4. Edge cases
# ---------------------------------------------------------------------------

class TestGenSpecEdgeCases:
    def test_empty_class(self):
        class EmptyPlugin:
            pass
        result = gen_spec(EmptyPlugin, name="empty")
        assert "def __ibcext_vtable__" in result
        # Should generate valid Python even with no methods
        compile(result, "<gen_spec>", "exec")

    def test_class_with_only_private(self):
        class PrivateOnly:
            def _internal(self):
                pass
        result = gen_spec(PrivateOnly, name="private")
        assert '"functions"' in result
        # No methods in output
        assert "_internal" not in result

    def test_class_with_varargs_skipped(self):
        class VarArgsPlugin:
            def method(self, a: int, *args, **kwargs) -> str:
                pass
        result = gen_spec(VarArgsPlugin, name="varargs")
        # *args and **kwargs should not appear in param_types
        namespace = {}
        exec(result, namespace)
        vtable = namespace["__ibcext_vtable__"]()
        method_spec = vtable["functions"]["method"]
        assert method_spec["param_types"] == ["int"]

    def test_method_docstring_as_description(self):
        class DocPlugin:
            def documented(self) -> str:
                """This is the first line.
                And more details."""
                return "x"
        result = gen_spec(DocPlugin, name="doc")
        assert "This is the first line." in result
