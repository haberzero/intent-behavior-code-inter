import pytest

from core.kernel.factory import create_default_registry
from core.runtime.loader.artifact_rehydrator import ArtifactRehydrator
from core.kernel.spec.specs import OptionalSpec


class TestM2OptionalArtifactRehydrator:
    def test_legacy_kind_protocol_rejected_by_default(self):
        registry = create_default_registry()
        type_pool = {
            "type_root.int": {
                "uid": "type_root.int",
                "kind": "IbSpec",
                "name": "int",
                "module_path": None,
                "is_nullable": False,
                "is_user_defined": False,
            },
            "type_root.Optional[int]": {
                "uid": "type_root.Optional[int]",
                "kind": "OptionalSpec",
                "name": "Optional[int]",
                "module_path": None,
                "is_nullable": True,
                "is_user_defined": False,
                "wrapped_type_name": "int",
                "wrapped_type_module": None,
            },
        }

        rehydrator = ArtifactRehydrator(type_pool=type_pool, registry=registry)
        with pytest.raises(ValueError, match="deprecated legacy kind token"):
            rehydrator.hydrate("type_root.Optional[int]")

    def test_hydrate_optional_specialization_with_legacy_compat_enabled(self):
        registry = create_default_registry()
        type_pool = {
            "type_root.int": {
                "uid": "type_root.int",
                "kind": "IbSpec",
                "name": "int",
                "module_path": None,
                "is_nullable": False,
                "is_user_defined": False,
            },
            "type_root.Optional[int]": {
                "uid": "type_root.Optional[int]",
                "kind": "OptionalSpec",
                "name": "Optional[int]",
                "module_path": None,
                "is_nullable": True,
                "is_user_defined": False,
                "wrapped_type_name": "int",
                "wrapped_type_module": None,
            },
        }

        rehydrator = ArtifactRehydrator(
            type_pool=type_pool,
            registry=registry,
            enable_legacy_kind_compat=True,
        )
        spec = rehydrator.hydrate("type_root.Optional[int]")

        assert isinstance(spec, OptionalSpec)
        assert spec.name == "Optional[int]"
        assert spec.wrapped_type_name == "int"
        assert registry.resolve("Optional[int]") is not None

    def test_legacy_kind_field_rejected_by_default(self):
        registry = create_default_registry()
        type_pool = {
            "type_root.int": {
                "uid": "type_root.int",
                "kind": "primitive",
                "legacy_kind": "IbSpec",
                "name": "int",
                "module_path": None,
                "is_nullable": False,
                "is_user_defined": False,
            }
        }

        rehydrator = ArtifactRehydrator(type_pool=type_pool, registry=registry)
        with pytest.raises(ValueError, match="deprecated legacy_kind"):
            rehydrator.hydrate("type_root.int")

    def test_hydrate_optional_specialization_new_kind_protocol(self):
        registry = create_default_registry()
        type_pool = {
            "type_root.int": {
                "uid": "type_root.int",
                "kind": "primitive",
                "name": "int",
                "module_path": None,
                "is_nullable": False,
                "is_user_defined": False,
            },
            "type_root.Optional[int]": {
                "uid": "type_root.Optional[int]",
                "kind": "optional",
                "name": "Optional[int]",
                "module_path": None,
                "is_nullable": True,
                "is_user_defined": False,
                "wrapped_type_name": "int",
                "wrapped_type_module": None,
            },
        }

        rehydrator = ArtifactRehydrator(type_pool=type_pool, registry=registry)
        spec = rehydrator.hydrate("type_root.Optional[int]")

        assert isinstance(spec, OptionalSpec)
        assert spec.kind == "optional"
        assert spec.wrapped_type_name == "int"
