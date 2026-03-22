import unittest
from core.kernel.types.descriptors import (
    TypeDescriptor, ListMetadata, DictMetadata, FunctionMetadata,
    BoundMethodMetadata, INT_DESCRIPTOR, STR_DESCRIPTOR
)


class MockCallback:
    """用于追踪回调调用情况的 mock"""

    def __init__(self):
        self.calls = []

    def __call__(self, desc):
        self.calls.append(desc)
        return desc


class TestTypeDescriptorWalkReferences(unittest.TestCase):
    """测试 TypeDescriptor.walk_references 方法"""

    def test_walk_references_calls_callback_for_each_member(self):
        """测试 walk_references 为每个成员调用回调"""
        desc = TypeDescriptor(name="test")

        class MockSymbol:
            def __init__(self):
                self.descriptor = STR_DESCRIPTOR
            def walk_references(self, callback):
                callback(self.descriptor)

        desc.members = {
            "field1": MockSymbol(),
            "field2": MockSymbol(),
        }

        callback = MockCallback()
        desc.walk_references(callback)

        self.assertEqual(len(callback.calls), 2)

    def test_walk_references_with_empty_members(self):
        """测试 walk_references 处理空 members"""
        desc = TypeDescriptor(name="test")
        callback = MockCallback()
        desc.walk_references(callback)
        self.assertEqual(len(callback.calls), 0)


class TestListMetadataWalkReferences(unittest.TestCase):
    """测试 ListMetadata.walk_references 方法"""

    def test_walk_references_calls_callback_for_element_type(self):
        """测试 walk_references 为 element_type 调用回调"""
        list_desc = ListMetadata(name="list", element_type=INT_DESCRIPTOR)

        callback = MockCallback()
        list_desc.walk_references(callback)

        self.assertEqual(len(callback.calls), 1)
        self.assertIs(callback.calls[0], INT_DESCRIPTOR)

    def test_walk_references_with_no_element_type(self):
        """测试 walk_references 处理无 element_type"""
        list_desc = ListMetadata(name="list")
        callback = MockCallback()
        list_desc.walk_references(callback)
        self.assertEqual(len(callback.calls), 0)


class TestDictMetadataWalkReferences(unittest.TestCase):
    """测试 DictMetadata.walk_references 方法"""

    def test_walk_references_calls_callback_for_key_and_value_types(self):
        """测试 walk_references 为 key_type 和 value_type 调用回调"""
        dict_desc = DictMetadata(
            name="dict",
            key_type=STR_DESCRIPTOR,
            value_type=INT_DESCRIPTOR
        )

        callback = MockCallback()
        dict_desc.walk_references(callback)

        self.assertEqual(len(callback.calls), 2)

    def test_walk_references_with_no_key_type(self):
        """测试 walk_references 处理无 key_type"""
        dict_desc = DictMetadata(name="dict", value_type=INT_DESCRIPTOR)
        callback = MockCallback()
        dict_desc.walk_references(callback)
        self.assertEqual(len(callback.calls), 1)


class TestFunctionMetadataWalkReferences(unittest.TestCase):
    """测试 FunctionMetadata.walk_references 方法"""

    def test_walk_references_calls_callback_for_return_type(self):
        """测试 walk_references 为 return_type 调用回调"""
        func_desc = FunctionMetadata(
            name="test_func",
            return_type=INT_DESCRIPTOR
        )

        callback = MockCallback()
        func_desc.walk_references(callback)

        self.assertEqual(len(callback.calls), 1)
        self.assertIs(callback.calls[0], INT_DESCRIPTOR)

    def test_walk_references_calls_callback_for_param_types(self):
        """测试 walk_references 为 param_types 调用回调"""
        func_desc = FunctionMetadata(
            name="test_func",
            param_types=[STR_DESCRIPTOR, INT_DESCRIPTOR]
        )

        callback = MockCallback()
        func_desc.walk_references(callback)

        self.assertEqual(len(callback.calls), 2)

    def test_walk_references_with_no_return_type(self):
        """测试 walk_references 处理无 return_type"""
        func_desc = FunctionMetadata(name="test_func")
        callback = MockCallback()
        func_desc.walk_references(callback)
        self.assertEqual(len(callback.calls), 0)


class TestBoundMethodMetadataWalkReferences(unittest.TestCase):
    """测试 BoundMethodMetadata.walk_references 方法"""

    def test_walk_references_calls_callback_for_receiver_and_function(self):
        """测试 walk_references 为 receiver_type 和 function_type 调用回调"""
        bound_desc = BoundMethodMetadata(
            name="bound_method",
            receiver_type=INT_DESCRIPTOR,
            function_type=FunctionMetadata(name="func")
        )

        callback = MockCallback()
        bound_desc.walk_references(callback)

        self.assertEqual(len(callback.calls), 2)

    def test_walk_references_with_no_receiver_type(self):
        """测试 walk_references 处理无 receiver_type"""
        bound_desc = BoundMethodMetadata(
            name="bound_method",
            function_type=FunctionMetadata(name="func")
        )
        callback = MockCallback()
        bound_desc.walk_references(callback)
        self.assertEqual(len(callback.calls), 1)


if __name__ == "__main__":
    unittest.main()
