import pytest

from core.kernel.factory import create_default_registry
from core.runtime.loader.artifact_rehydrator import ArtifactRehydrator
from core.kernel.spec.specs import TypeDef


class TestM2OptionalArtifactRehydrator:
    def test_unsupported_kind_rejected(self):
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
                "kind": "TypeDef",
                "name": "Optional[int]",
                "module_path": None,
                "is_nullable": True,
                "is_user_defined": False,
                "wrapped_type_name": "int",
                "wrapped_type_module": None,
            },
        }

        rehydrator = ArtifactRehydrator(type_pool=type_pool, registry=registry)
        with pytest.raises(ValueError, match="unsupported kind"):
            rehydrator.hydrate("type_root.Optional[int]")

    def test_unsupported_kind_rejected_for_other_invalid_token(self):
        registry = create_default_registry()
        type_pool = {
            "type_root.list[int]": {
                "uid": "type_root.list[int]",
                "kind": "ListMetadata",
                "name": "list[int]",
                "module_path": None,
                "is_nullable": False,
                "is_user_defined": False,
                "element_type_uid": "type_root.int",
            },
            "type_root.int": {
                "uid": "type_root.int",
                "kind": "primitive",
                "name": "int",
                "module_path": None,
                "is_nullable": False,
                "is_user_defined": False,
            },
        }

        rehydrator = ArtifactRehydrator(type_pool=type_pool, registry=registry)
        with pytest.raises(ValueError, match="unsupported kind"):
            rehydrator.hydrate("type_root.list[int]")

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

        assert isinstance(spec, TypeDef)
        assert spec.kind == "optional"
        assert spec.wrapped_type.head == "int"
