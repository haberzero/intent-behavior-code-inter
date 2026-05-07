from core.kernel.factory import create_default_registry
from core.runtime.loader.artifact_rehydrator import ArtifactRehydrator
from core.kernel.spec.specs import OptionalSpec


class TestM2OptionalArtifactRehydrator:
    def test_hydrate_optional_specialization(self):
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
        spec = rehydrator.hydrate("type_root.Optional[int]")

        assert isinstance(spec, OptionalSpec)
        assert spec.name == "Optional[int]"
        assert spec.wrapped_type_name == "int"
        assert registry.resolve("Optional[int]") is not None

