import unittest
from core.kernel.factory import create_default_registry


class TestFactoryCreateDefaultRegistry(unittest.TestCase):
    """测试 create_default_registry 工厂函数"""

    def test_create_default_registry_returns_registry(self):
        """验证返回的是 MetadataRegistry 实例"""
        registry = create_default_registry()
        self.assertIsNotNone(registry)

    def test_create_default_registry_registers_primitive_types(self):
        """验证注册了所有原始类型"""
        registry = create_default_registry()

        expected_types = ["int", "str", "float", "bool", "void", "any", "auto",
                          "callable", "list", "dict", "None", "behavior",
                          "bound_method", "Exception", "module"]

        for type_name in expected_types:
            resolved = registry.resolve(type_name)
            self.assertIsNotNone(resolved, f"Type '{type_name}' should be registered")

    def test_int_descriptor_has_axiom(self):
        """验证 int 类型描述符绑定了公理"""
        registry = create_default_registry()
        int_desc = registry.resolve("int")
        self.assertIsNotNone(int_desc)
        self.assertIsNotNone(int_desc._axiom)

    def test_str_descriptor_has_axiom(self):
        """验证 str 类型描述符绑定了公理"""
        registry = create_default_registry()
        str_desc = registry.resolve("str")
        self.assertIsNotNone(str_desc)
        self.assertIsNotNone(str_desc._axiom)

    def test_list_descriptor_has_axiom(self):
        """验证 list 类型描述符绑定了公理"""
        registry = create_default_registry()
        list_desc = registry.resolve("list")
        self.assertIsNotNone(list_desc)
        self.assertIsNotNone(list_desc._axiom)

    def test_dict_descriptor_has_axiom(self):
        """验证 dict 类型描述符绑定了公理"""
        registry = create_default_registry()
        dict_desc = registry.resolve("dict")
        self.assertIsNotNone(dict_desc)
        self.assertIsNotNone(dict_desc._axiom)

    def test_primitive_types_are_not_nullable(self):
        """验证原始类型（除 any/auto 外）不可空"""
        registry = create_default_registry()

        non_nullable = ["int", "str", "float", "bool"]
        for type_name in non_nullable:
            desc = registry.resolve(type_name)
            self.assertIsNotNone(desc)
            self.assertFalse(desc.is_nullable, f"Type '{type_name}' should not be nullable")

    def test_any_and_auto_are_nullable(self):
        """验证 any 和 auto 可为空"""
        registry = create_default_registry()
        nullable = ["any", "auto"]
        for type_name in nullable:
            desc = registry.resolve(type_name)
            self.assertIsNotNone(desc)
            self.assertTrue(desc.is_nullable, f"Type '{type_name}' should be nullable")

    def test_registry_isolation(self):
        """验证多个 registry 实例是隔离的"""
        registry1 = create_default_registry()
        registry2 = create_default_registry()

        int_desc1 = registry1.resolve("int")
        int_desc2 = registry2.resolve("int")

        self.assertIsNot(int_desc1, int_desc2)


if __name__ == "__main__":
    unittest.main()
