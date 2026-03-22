import unittest
from core.kernel.types.descriptors import (
    TypeDescriptor,
    ListMetadata,
    DictMetadata,
    FunctionMetadata,
    INT_DESCRIPTOR,
    STR_DESCRIPTOR,
    FLOAT_DESCRIPTOR,
    BOOL_DESCRIPTOR,
)


class TestTypeDescriptor(unittest.TestCase):
    """测试 TypeDescriptor 基类"""

    def test_type_descriptor_creation_defaults(self):
        """测试默认创建"""
        desc = TypeDescriptor()
        self.assertEqual(desc.name, "")
        self.assertIsNone(desc.module_path)
        self.assertTrue(desc.is_nullable)
        self.assertTrue(desc.is_user_defined)
        self.assertEqual(len(desc.members), 0)

    def test_type_descriptor_creation_with_values(self):
        """测试带值创建"""
        desc = TypeDescriptor(
            name="int",
            module_path="core.kernel",
            is_nullable=False,
            is_user_defined=False
        )
        self.assertEqual(desc.name, "int")
        self.assertEqual(desc.module_path, "core.kernel")
        self.assertFalse(desc.is_nullable)
        self.assertFalse(desc.is_user_defined)

    def test_type_descriptor_kind(self):
        """测试 kind 属性"""
        desc = TypeDescriptor(name="test")
        self.assertEqual(desc.kind, "TypeDescriptor")

    def test_type_descriptor_equality(self):
        """测试相等性"""
        desc1 = TypeDescriptor(name="int")
        desc2 = TypeDescriptor(name="int")
        desc3 = TypeDescriptor(name="str")

        self.assertEqual(desc1, desc2)
        self.assertNotEqual(desc1, desc3)

    def test_type_descriptor_equality_different_types(self):
        """测试不同类型的相等性"""
        desc = TypeDescriptor(name="int")
        list_desc = ListMetadata(name="list")

        self.assertNotEqual(desc, list_desc)

    def test_type_descriptor_clone(self):
        """测试克隆"""
        original = TypeDescriptor(name="test", is_nullable=False)
        cloned = original.clone()

        self.assertIsNot(original, cloned)
        self.assertEqual(original.name, cloned.name)
        self.assertEqual(original.is_nullable, cloned.is_nullable)
        self.assertIsNone(cloned._registry)
        self.assertIsNone(cloned._axiom)

    def test_type_descriptor_clone_preserves_members(self):
        """测试克隆保留成员"""
        desc = TypeDescriptor(name="test")
        sym = object()
        desc.members["x"] = sym

        cloned = desc.clone()
        self.assertIsNot(desc.members, cloned.members)
        self.assertIs(cloned.members["x"], sym)

    def test_type_descriptor_get_base_axiom_name(self):
        """测试获取基础公理名称"""
        desc = TypeDescriptor(name="MyType")
        self.assertEqual(desc.get_base_axiom_name(), "MyType")

    def test_type_descriptor_get_signature(self):
        """测试获取签名（基类返回 None）"""
        desc = TypeDescriptor(name="test")
        self.assertIsNone(desc.get_signature())


class TestListMetadata(unittest.TestCase):
    """测试 ListMetadata"""

    def test_list_metadata_creation(self):
        """测试创建列表元数据"""
        desc = ListMetadata(name="list", is_nullable=True)
        self.assertEqual(desc.name, "list")
        self.assertTrue(desc.is_nullable)

    def test_list_metadata_equality(self):
        """测试列表元数据相等性"""
        list1 = ListMetadata(name="list")
        list2 = ListMetadata(name="list")

        self.assertEqual(list1, list2)

    def test_list_metadata_clone(self):
        """测试列表元数据克隆"""
        original = ListMetadata(name="list")
        cloned = original.clone()

        self.assertIsNot(original, cloned)
        self.assertEqual(original.name, cloned.name)

    def test_list_metadata_get_base_axiom_name(self):
        """测试获取基础公理名称"""
        desc = ListMetadata(name="list")
        self.assertEqual(desc.get_base_axiom_name(), "list")


class TestDictMetadata(unittest.TestCase):
    """测试 DictMetadata"""

    def test_dict_metadata_creation(self):
        """测试创建字典元数据"""
        desc = DictMetadata(name="dict", is_nullable=True)
        self.assertEqual(desc.name, "dict")
        self.assertTrue(desc.is_nullable)

    def test_dict_metadata_clone(self):
        """测试字典元数据克隆"""
        original = DictMetadata(name="dict")
        cloned = original.clone()

        self.assertIsNot(original, cloned)
        self.assertEqual(original.name, cloned.name)


class TestFunctionMetadata(unittest.TestCase):
    """测试 FunctionMetadata"""

    def test_function_metadata_creation(self):
        """测试创建函数元数据"""
        desc = FunctionMetadata(name="my_func")
        self.assertEqual(desc.name, "my_func")
        self.assertEqual(desc.param_types, [])
        self.assertIsNone(desc.return_type)

    def test_function_metadata_with_signature(self):
        """测试带签名的函数元数据"""
        int_desc = INT_DESCRIPTOR
        str_desc = STR_DESCRIPTOR

        desc = FunctionMetadata(
            name="my_func",
            param_types=[int_desc],
            return_type=str_desc
        )

        self.assertEqual(len(desc.param_types), 1)
        self.assertIs(desc.param_types[0], int_desc)
        self.assertIs(desc.return_type, str_desc)

    def test_function_metadata_get_signature(self):
        """测试获取签名"""
        int_desc = INT_DESCRIPTOR
        str_desc = STR_DESCRIPTOR

        desc = FunctionMetadata(
            name="my_func",
            param_types=[int_desc],
            return_type=str_desc
        )

        sig = desc.get_signature()
        self.assertIsNotNone(sig)

        params, ret = sig
        self.assertEqual(len(params), 1)
        self.assertIs(params[0], int_desc)
        self.assertIs(ret, str_desc)

    def test_function_metadata_get_base_axiom_name(self):
        """测试获取基础公理名称（函数返回 callable）"""
        desc = FunctionMetadata(name="my_func")
        self.assertEqual(desc.get_base_axiom_name(), "callable")


class TestDescriptorConstants(unittest.TestCase):
    """测试预定义常量描述符"""

    def test_int_descriptor(self):
        """测试 INT_DESCRIPTOR"""
        self.assertEqual(INT_DESCRIPTOR.name, "int")
        self.assertFalse(INT_DESCRIPTOR.is_nullable)

    def test_str_descriptor(self):
        """测试 STR_DESCRIPTOR"""
        self.assertEqual(STR_DESCRIPTOR.name, "str")
        self.assertFalse(STR_DESCRIPTOR.is_nullable)

    def test_float_descriptor(self):
        """测试 FLOAT_DESCRIPTOR"""
        self.assertEqual(FLOAT_DESCRIPTOR.name, "float")
        self.assertFalse(FLOAT_DESCRIPTOR.is_nullable)

    def test_bool_descriptor(self):
        """测试 BOOL_DESCRIPTOR"""
        self.assertEqual(BOOL_DESCRIPTOR.name, "bool")
        self.assertFalse(BOOL_DESCRIPTOR.is_nullable)

    def test_descriptors_are_singletons(self):
        """验证预定义描述符是单例"""
        self.assertIs(INT_DESCRIPTOR, INT_DESCRIPTOR)
        self.assertIs(STR_DESCRIPTOR, STR_DESCRIPTOR)


if __name__ == "__main__":
    unittest.main()
