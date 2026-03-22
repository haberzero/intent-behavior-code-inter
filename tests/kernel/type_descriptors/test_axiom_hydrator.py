import unittest
from core.kernel.types.axiom_hydrator import AxiomHydrator
from core.kernel.types.registry import MetadataRegistry
from core.kernel.axioms.registry import AxiomRegistry
from core.kernel.axioms.primitives import register_core_axioms
from core.kernel.types.descriptors import TypeDescriptor, ListMetadata, INT_DESCRIPTOR


class TestAxiomHydratorBasic(unittest.TestCase):
    """测试 AxiomHydrator 基本功能（不触发无限递归的测试）"""

    def setUp(self):
        self.axiom_registry = AxiomRegistry()
        register_core_axioms(self.axiom_registry)
        self.registry = MetadataRegistry(axiom_registry=self.axiom_registry)
        self.hydrator = AxiomHydrator(self.registry)

    def test_hydrator_has_registry(self):
        """测试 hydrator 持有 registry 引用"""
        self.assertIsNotNone(self.hydrator._registry)
        self.assertIs(self.hydrator._registry, self.registry)

    def test_hydrator_processing_set_initially_empty(self):
        """测试 _processing set 初始为空"""
        self.assertEqual(len(self.hydrator._processing), 0)


class TestAxiomHydratorEdgeCases(unittest.TestCase):
    """测试边界情况"""

    def setUp(self):
        self.axiom_registry = AxiomRegistry()
        register_core_axioms(self.axiom_registry)
        self.registry = MetadataRegistry(axiom_registry=self.axiom_registry)
        self.hydrator = AxiomHydrator(self.registry)

    def test_hydrate_metadata_handles_none(self):
        """测试 hydrate_metadata 处理 None 输入"""
        result = self.hydrator.hydrate_metadata(None)
        self.assertIsNone(result)

    def test_hydrate_metadata_handles_string_type_name(self):
        """测试 hydrate_metadata 处理字符串类型名"""
        self.registry.register(TypeDescriptor(name="int"))
        result = self.hydrator.hydrate_metadata("int")
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "int")

    def test_hydrate_metadata_raises_for_unknown_string(self):
        """测试 hydrate_metadata 对未知类型名抛出异常"""
        with self.assertRaises(RuntimeError) as ctx:
            self.hydrator.hydrate_metadata("nonexistent_type_xyz")
        self.assertIn("not found in registry", str(ctx.exception))

    def test_deep_hydrate_handles_empty_members(self):
        """测试 deep_hydrate 处理空 members"""
        desc = TypeDescriptor(name="test")
        self.hydrator.deep_hydrate(desc)
        self.assertEqual(desc.members, {})

    def test_deep_hydrate_preserves_non_symbol_members(self):
        """测试 deep_hydrate 保留没有 walk_references 的成员"""
        desc = TypeDescriptor(name="test")
        desc.members["plain_value"] = "just a string"
        self.hydrator.deep_hydrate(desc)
        self.assertEqual(desc.members["plain_value"], "just a string")


class TestAxiomHydratorInjectAxiomsEdge(unittest.TestCase):
    """测试 inject_axioms 边界情况"""

    def setUp(self):
        self.axiom_registry = AxiomRegistry()
        register_core_axioms(self.axiom_registry)

    def test_inject_raises_when_no_registry(self):
        """测试当没有公理注册表时抛出 RuntimeError"""
        registry_without_axioms = MetadataRegistry()
        hydrator = AxiomHydrator(registry_without_axioms)
        desc = TypeDescriptor(name="int")

        with self.assertRaises(RuntimeError) as ctx:
            hydrator.inject_axioms(desc)
        self.assertIn("AxiomRegistry not available", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
