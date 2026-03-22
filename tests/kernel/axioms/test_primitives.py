import unittest
from core.kernel.axioms.registry import AxiomRegistry
from core.kernel.axioms.primitives import (
    IntAxiom,
    StrAxiom,
    FloatAxiom,
    BoolAxiom,
    ListAxiom,
    DictAxiom,
    register_core_axioms,
)


class TestAxiomRegistry(unittest.TestCase):
    """测试 AxiomRegistry"""

    def setUp(self):
        """每个测试前创建新的注册表"""
        self.registry = AxiomRegistry()

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(len(self.registry._axioms), 0)

    def test_register_axiom(self):
        """测试注册公理"""
        axiom = IntAxiom()
        self.registry.register(axiom)

        self.assertEqual(len(self.registry._axioms), 1)
        self.assertIs(self.registry._axioms["int"], axiom)

    def test_get_axiom_existing(self):
        """测试获取已注册的公理"""
        axiom = IntAxiom()
        self.registry.register(axiom)

        retrieved = self.registry.get_axiom("int")
        self.assertIs(retrieved, axiom)

    def test_get_axiom_nonexisting(self):
        """测试获取未注册的公理"""
        retrieved = self.registry.get_axiom("nonexistent")
        self.assertIsNone(retrieved)

    def test_get_all_names(self):
        """测试获取所有公理名称"""
        self.registry.register(IntAxiom())
        self.registry.register(StrAxiom())

        names = self.registry.get_all_names()
        self.assertEqual(len(names), 2)
        self.assertIn("int", names)
        self.assertIn("str", names)

    def test_clear(self):
        """测试清空注册表"""
        self.registry.register(IntAxiom())
        self.registry.clear()

        self.assertEqual(len(self.registry._axioms), 0)


class TestRegisterCoreAxioms(unittest.TestCase):
    """测试 register_core_axioms"""

    def test_register_core_axioms(self):
        """测试注册所有核心公理"""
        registry = AxiomRegistry()
        register_core_axioms(registry)

        expected_axioms = ["int", "str", "float", "bool", "list", "dict",
                         "None", "callable", "behavior", "bound_method",
                         "Exception", "var", "Any"]

        for name in expected_axioms:
            axiom = registry.get_axiom(name)
            self.assertIsNotNone(axiom, f"Axiom '{name}' should be registered")


class TestIntAxiom(unittest.TestCase):
    """测试 IntAxiom"""

    def setUp(self):
        """每个测试前创建新的 axiom"""
        self.axiom = IntAxiom()

    def test_axiom_name(self):
        """测试公理名称"""
        self.assertEqual(self.axiom.name, "int")

    def test_is_dynamic_false(self):
        """测试不是动态类型"""
        self.assertFalse(self.axiom.is_dynamic())

    def test_is_class_false(self):
        """测试不是类类型"""
        self.assertFalse(self.axiom.is_class())

    def test_is_module_false(self):
        """测试不是模块类型"""
        self.assertFalse(self.axiom.is_module())

    def test_get_parent_axiom_name(self):
        """测试获取父公理名称（默认继承自 Object）"""
        self.assertEqual(self.axiom.get_parent_axiom_name(), "Object")

    def test_resolve_specialization_int(self):
        """测试特化解析"""
        result = self.axiom.resolve_specialization(INT_DESCRIPTOR)
        self.assertIsNotNone(result)


class TestStrAxiom(unittest.TestCase):
    """测试 StrAxiom"""

    def setUp(self):
        """每个测试前创建新的 axiom"""
        self.axiom = StrAxiom()

    def test_axiom_name(self):
        """测试公理名称"""
        self.assertEqual(self.axiom.name, "str")

    def test_is_dynamic_false(self):
        """测试不是动态类型"""
        self.assertFalse(self.axiom.is_dynamic())

    def test_can_convert_from(self):
        """测试可转换来源"""
        self.assertTrue(self.axiom.can_convert_from("int"))
        self.assertTrue(self.axiom.can_convert_from("str"))
        self.assertFalse(self.axiom.can_convert_from("list"))


class TestFloatAxiom(unittest.TestCase):
    """测试 FloatAxiom"""

    def setUp(self):
        """每个测试前创建新的 axiom"""
        self.axiom = FloatAxiom()

    def test_axiom_name(self):
        """测试公理名称"""
        self.assertEqual(self.axiom.name, "float")

    def test_can_convert_from(self):
        """测试可转换来源"""
        self.assertTrue(self.axiom.can_convert_from("int"))
        self.assertTrue(self.axiom.can_convert_from("float"))


class TestBoolAxiom(unittest.TestCase):
    """测试 BoolAxiom"""

    def setUp(self):
        """每个测试前创建新的 axiom"""
        self.axiom = BoolAxiom()

    def test_axiom_name(self):
        """测试公理名称"""
        self.assertEqual(self.axiom.name, "bool")

    def test_get_parent_axiom_name(self):
        """测试父公理名称"""
        self.assertEqual(self.axiom.get_parent_axiom_name(), "int")


class TestListAxiom(unittest.TestCase):
    """测试 ListAxiom"""

    def setUp(self):
        """每个测试前创建新的 axiom"""
        self.axiom = ListAxiom()

    def test_axiom_name(self):
        """测试公理名称"""
        self.assertEqual(self.axiom.name, "list")

    def test_resolve_specialization(self):
        """测试特化解析"""
        from core.kernel.types.descriptors import INT_DESCRIPTOR

        result = self.axiom.resolve_specialization(INT_DESCRIPTOR)
        self.assertIsNotNone(result)


class TestDictAxiom(unittest.TestCase):
    """测试 DictAxiom"""

    def setUp(self):
        """每个测试前创建新的 axiom"""
        self.axiom = DictAxiom()

    def test_axiom_name(self):
        """测试公理名称"""
        self.assertEqual(self.axiom.name, "dict")


if __name__ == "__main__":
    unittest.main()
