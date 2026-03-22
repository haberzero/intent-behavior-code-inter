import unittest
from core.kernel.factory import create_default_registry
from core.kernel.types.descriptors import (
    INT_DESCRIPTOR,
    STR_DESCRIPTOR,
    LIST_DESCRIPTOR,
    DICT_DESCRIPTOR,
)


class TestMetadataRegistry(unittest.TestCase):
    """测试 MetadataRegistry"""

    def setUp(self):
        """每个测试前创建新的注册表"""
        self.registry = create_default_registry()

    def test_initialization(self):
        """测试初始化后有基础类型"""
        self.assertIsNotNone(self.registry)

    def test_resolve_primitive_types(self):
        """测试解析原始类型"""
        for type_name in ["int", "str", "float", "bool"]:
            desc = self.registry.resolve(type_name)
            self.assertIsNotNone(desc, f"Should resolve {type_name}")
            self.assertEqual(desc.name, type_name)

    def test_resolve_nonexistent_type(self):
        """测试解析不存在的类型"""
        desc = self.registry.resolve("nonexistent_type_xyz")
        self.assertIsNone(desc)

    def test_resolve_with_module_path(self):
        """测试带模块路径的解析 - module_path 与 key 构建相关"""
        desc = self.registry.resolve("int", module_path=None)
        self.assertIsNotNone(desc)


class TestTypeFactory(unittest.TestCase):
    """测试 TypeFactory 工厂方法"""

    def setUp(self):
        """每个测试前创建新的注册表"""
        self.registry = create_default_registry()

    def test_create_primitive(self):
        """测试创建原始类型"""
        factory = self.registry.factory
        desc = factory.create_primitive("MyInt", is_nullable=False)

        self.assertEqual(desc.name, "MyInt")
        self.assertFalse(desc.is_nullable)

    def test_create_list(self):
        """测试创建列表类型"""
        factory = self.registry.factory
        desc = factory.create_list(INT_DESCRIPTOR)

        self.assertIsNotNone(desc.element_type)
        self.assertEqual(desc.element_type, INT_DESCRIPTOR)

    def test_create_dict(self):
        """测试创建字典类型"""
        factory = self.registry.factory
        desc = factory.create_dict(STR_DESCRIPTOR, INT_DESCRIPTOR)

        self.assertIsNotNone(desc.key_type)
        self.assertIsNotNone(desc.value_type)

    def test_create_function(self):
        """测试创建函数类型"""
        factory = self.registry.factory
        desc = factory.create_function([INT_DESCRIPTOR], STR_DESCRIPTOR)

        self.assertEqual(desc.name, "callable")
        self.assertEqual(len(desc.param_types), 1)
        self.assertIs(desc.return_type, STR_DESCRIPTOR)


class TestRegistryIsolation(unittest.TestCase):
    """测试注册表隔离"""

    def test_multiple_registries_are_isolated(self):
        """测试多个注册表实例是隔离的"""
        registry1 = create_default_registry()
        registry2 = create_default_registry()

        desc1 = registry1.resolve("int")
        desc2 = registry2.resolve("int")

        self.assertIsNot(desc1, desc2)

    def test_clone_creates_isolated_copy(self):
        """测试克隆创建隔离副本"""
        registry = create_default_registry()
        cloned = registry.clone()

        self.assertIsNot(registry, cloned)


class TestRegistryAxiomBinding(unittest.TestCase):
    """测试注册表与公理绑定"""

    def setUp(self):
        """每个测试前创建新的注册表"""
        self.registry = create_default_registry()

    def test_primitive_has_axiom_bound(self):
        """测试原始类型绑定了公理"""
        int_desc = self.registry.resolve("int")
        self.assertIsNotNone(int_desc._axiom)

        str_desc = self.registry.resolve("str")
        self.assertIsNotNone(str_desc._axiom)

    def test_list_has_axiom_bound(self):
        """测试列表类型绑定了公理"""
        list_desc = self.registry.resolve("list")
        self.assertIsNotNone(list_desc._axiom)

    def test_dict_has_axiom_bound(self):
        """测试字典类型绑定了公理"""
        dict_desc = self.registry.resolve("dict")
        self.assertIsNotNone(dict_desc._axiom)


if __name__ == "__main__":
    unittest.main()
