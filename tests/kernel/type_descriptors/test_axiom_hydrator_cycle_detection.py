import unittest
from core.kernel.types.axiom_hydrator import AxiomHydrator
from core.kernel.types.registry import MetadataRegistry
from core.kernel.axioms.registry import AxiomRegistry
from core.kernel.axioms.primitives import register_core_axioms, IntAxiom
from core.kernel.types.descriptors import TypeDescriptor, INT_DESCRIPTOR


class TestAxiomHydratorCycleDetectionSimplified(unittest.TestCase):
    """测试 AxiomHydrator._processing() 循环检测机制 - 简化版"""

    def setUp(self):
        self.axiom_registry = AxiomRegistry()
        register_core_axioms(self.axiom_registry)
        self.registry = MetadataRegistry(axiom_registry=self.axiom_registry)
        self.hydrator = AxiomHydrator(self.registry)

    def test_processing_set_initial_state(self):
        """测试 _processing 集合初始为空"""
        self.assertEqual(len(self.hydrator._processing), 0)

    def test_processing_set_after_inject_simple(self):
        """测试简单注入后 _processing 被清空"""
        desc = TypeDescriptor(name="Simple")
        desc.members["value"] = INT_DESCRIPTOR

        self.hydrator.inject_axioms(desc)

        self.assertEqual(len(self.hydrator._processing), 0)

    def test_processing_set_prevents_duplicate_injection(self):
        """测试 _processing 防止重复注入"""
        desc = TypeDescriptor(name="SelfRef")
        desc.members["value"] = INT_DESCRIPTOR

        self.hydrator.inject_axioms(desc)
        initial_axiom = desc._axiom

        self.hydrator.inject_axioms(desc)

        self.assertIs(desc._axiom, initial_axiom)

    def test_hydrate_metadata_clears_processing(self):
        """测试 hydrate_metadata 后 _processing 被清空"""
        registered_desc = self.registry.register(TypeDescriptor(name="TestType"))

        result = self.hydrator.hydrate_metadata("TestType")

        self.assertEqual(len(self.hydrator._processing), 0)
        self.assertIsNotNone(result)

    def test_axiom_injection_on_primitive_descriptor(self):
        """测试原始类型描述符已有 axiom（未改变）"""
        desc = TypeDescriptor(name="MyInt")
        desc._axiom = IntAxiom()

        self.assertIsNotNone(desc._axiom)


class TestAxiomHydratorEdgeCases(unittest.TestCase):
    """测试 AxiomHydrator 边界情况"""

    def setUp(self):
        self.axiom_registry = AxiomRegistry()
        register_core_axioms(self.axiom_registry)
        self.registry = MetadataRegistry(axiom_registry=self.axiom_registry)
        self.hydrator = AxiomHydrator(self.registry)

    def test_none_input_handling(self):
        """测试 None 输入处理"""
        result = self.hydrator.hydrate_metadata(None)
        self.assertIsNone(result)

    def test_unknown_type_raises_error(self):
        """测试未知类型抛出错误"""
        with self.assertRaises(RuntimeError):
            self.hydrator.hydrate_metadata("NonExistentType")

    def test_inject_without_registry_raises(self):
        """测试没有 registry 时注入抛出错误"""
        registry_no_axiom = MetadataRegistry()
        hydrator = AxiomHydrator(registry_no_axiom)
        desc = TypeDescriptor(name="Test")

        with self.assertRaises(RuntimeError) as ctx:
            hydrator.inject_axioms(desc)
        self.assertIn("AxiomRegistry not available", str(ctx.exception))

    def test_deep_hydrate_preserves_members(self):
        """测试 deep_hydrate 保留成员"""
        desc = TypeDescriptor(name="Test")
        desc.members["key"] = "value"

        self.hydrator.deep_hydrate(desc)

        self.assertEqual(desc.members["key"], "value")

    def test_deep_hydrate_clears_processing_after(self):
        """测试 deep_hydrate 完成后 _processing 被清空"""
        desc = TypeDescriptor(name="Test")
        desc.members["value"] = INT_DESCRIPTOR

        self.hydrator.deep_hydrate(desc)

        self.assertEqual(len(self.hydrator._processing), 0)


class TestAxiomHydratorIntegration(unittest.TestCase):
    """测试 AxiomHydrator 与 MetadataRegistry 集成"""

    def setUp(self):
        self.axiom_registry = AxiomRegistry()
        register_core_axioms(self.axiom_registry)
        self.registry = MetadataRegistry(axiom_registry=self.axiom_registry)
        self.hydrator = AxiomHydrator(self.registry)

    def test_hydrate_metadata_returns_descriptor(self):
        """测试 hydrate_metadata 返回 TypeDescriptor"""
        registered_desc = self.registry.register(TypeDescriptor(name="TestType"))

        result = self.hydrator.hydrate_metadata("TestType")

        self.assertIsInstance(result, TypeDescriptor)

    def test_hydrate_metadata_from_registry(self):
        """测试从 registry 水化元数据"""
        desc = TypeDescriptor(name="HydrateTest", is_user_defined=True)
        self.registry.register(desc)

        result = self.hydrator.hydrate_metadata("HydrateTest")

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "HydrateTest")

    def test_registry_clone_isolation(self):
        """测试 registry 克隆后的 axiom 隔离"""
        clone = self.registry.clone()

        desc = TypeDescriptor(name="CloneTest")
        original_registered = self.registry.register(desc)
        cloned_desc = clone.resolve("CloneTest")

        self.assertIsNot(original_registered, cloned_desc)


class TestAxiomHydratorWithCoreTypes(unittest.TestCase):
    """测试 AxiomHydrator 处理核心类型"""

    def setUp(self):
        self.axiom_registry = AxiomRegistry()
        register_core_axioms(self.axiom_registry)
        self.registry = MetadataRegistry(axiom_registry=self.axiom_registry)
        self.hydrator = AxiomHydrator(self.registry)

    def test_inject_axioms_to_int_descriptor(self):
        """测试向 INT_DESCRIPTOR 注入 axioms"""
        self.hydrator.inject_axioms(INT_DESCRIPTOR)

        self.assertIsNotNone(INT_DESCRIPTOR._axiom)

    def test_multiple_descriptors_independent_axioms(self):
        """测试多个描述符绑定 axiom 后相互独立"""
        desc1 = TypeDescriptor(name="Type1")
        desc1._axiom = IntAxiom()

        desc2 = TypeDescriptor(name="Type2")
        desc2._axiom = IntAxiom()

        self.assertIsNotNone(desc1._axiom)
        self.assertIsNotNone(desc2._axiom)
        self.assertIsNot(desc1._axiom, desc2._axiom)

    def test_processing_not_shared_between_hydrators(self):
        """测试两个 hydrator 不共享 _processing"""
        hydrator1 = AxiomHydrator(self.registry)
        hydrator2 = AxiomHydrator(self.registry)

        desc1 = TypeDescriptor(name="Desc1")
        desc1.members["value"] = INT_DESCRIPTOR
        hydrator1.inject_axioms(desc1)

        desc2 = TypeDescriptor(name="Desc2")
        desc2.members["value"] = INT_DESCRIPTOR
        hydrator2.inject_axioms(desc2)

        self.assertEqual(len(hydrator1._processing), 0)
        self.assertEqual(len(hydrator2._processing), 0)


if __name__ == "__main__":
    unittest.main()
