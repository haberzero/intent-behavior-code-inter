import unittest
from core.kernel.types.descriptors import (
    TypeDescriptor,
    ListMetadata,
    DictMetadata,
    FunctionMetadata,
    ClassMetadata,
    BoundMethodMetadata,
    LazyDescriptor,
    INT_DESCRIPTOR,
    STR_DESCRIPTOR,
    FLOAT_DESCRIPTOR,
    BOOL_DESCRIPTOR,
    VOID_DESCRIPTOR,
    ANY_DESCRIPTOR,
    VAR_DESCRIPTOR,
    CALLABLE_DESCRIPTOR,
    LIST_DESCRIPTOR,
    DICT_DESCRIPTOR,
)
from core.kernel.axioms.primitives import (
    IntAxiom, StrAxiom, FloatAxiom, BoolAxiom, ListAxiom, DictAxiom, DynamicAxiom
)
from core.kernel.types.registry import MetadataRegistry
from core.kernel.factory import create_default_registry


class TestTypeDescriptorIsAssignableTo(unittest.TestCase):
    """测试 TypeDescriptor.is_assignable_to() 基类实现"""

    def test_reference_equality_same_instance(self):
        """引用相等：同一实例应该返回 True"""
        desc = TypeDescriptor(name="int")
        self.assertTrue(desc.is_assignable_to(desc))

    def test_name_based_structural_compatibility(self):
        """名称匹配：不同实例但相同名称和类型应该结构兼容"""
        desc1 = TypeDescriptor(name="int")
        desc2 = TypeDescriptor(name="int")
        self.assertTrue(desc1.is_assignable_to(desc2))

    def test_structural_compatibility_same_type_and_name(self):
        """结构兼容：相同类型和名称应该返回 True"""
        desc1 = TypeDescriptor(name="MyType", is_nullable=True)
        desc2 = TypeDescriptor(name="MyType", is_nullable=False)
        self.assertTrue(desc1.is_assignable_to(desc2))

    def test_structural_compatibility_different_names(self):
        """结构兼容：不同名称应该返回 False"""
        desc1 = TypeDescriptor(name="TypeA")
        desc2 = TypeDescriptor(name="TypeB")
        self.assertFalse(desc1.is_assignable_to(desc2))

    def test_structural_compatibility_different_types(self):
        """结构兼容：不同类型应该返回 False"""
        desc1 = TypeDescriptor(name="int")
        desc2 = ListMetadata(name="int")
        self.assertFalse(desc1.is_assignable_to(desc2))


class TestTypeDescriptorIsAssignableToWithAxiom(unittest.TestCase):
    """测试带公理的 TypeDescriptor.is_assignable_to()"""

    def test_axiom_compatible_same_primitive(self):
        """公理兼容：相同原子类型应该兼容"""
        int_desc = TypeDescriptor(name="int", is_nullable=False)
        int_desc._axiom = IntAxiom()
        self.assertTrue(int_desc.is_assignable_to(int_desc))

    def test_axiom_compatible_int_to_any(self):
        """公理兼容：int 应该兼容 Any (var)"""
        int_desc = TypeDescriptor(name="int", is_nullable=False)
        int_desc._axiom = IntAxiom()

        var_desc = TypeDescriptor(name="var", is_nullable=True)
        var_desc._axiom = DynamicAxiom(name="var")

        self.assertTrue(int_desc.is_assignable_to(var_desc))

    def test_axiom_not_compatible_int_to_str(self):
        """公理不兼容：int 不应该兼容 str"""
        int_desc = TypeDescriptor(name="int", is_nullable=False)
        int_desc._axiom = IntAxiom()

        str_desc = TypeDescriptor(name="str", is_nullable=False)
        str_desc._axiom = StrAxiom()

        self.assertFalse(int_desc.is_assignable_to(str_desc))


class TestListMetadataIsAssignableTo(unittest.TestCase):
    """测试 ListMetadata.is_assignable_to()"""

    def setUp(self):
        self.list_int = ListMetadata(name="list", element_type=INT_DESCRIPTOR)
        self.list_str = ListMetadata(name="list", element_type=STR_DESCRIPTOR)
        self.list_any = ListMetadata(name="list", element_type=ANY_DESCRIPTOR)
        self.list_raw = ListMetadata(name="list")

    def test_same_element_type(self):
        """相同元素类型应该兼容"""
        self.assertTrue(self.list_int.is_assignable_to(self.list_int))

    def test_different_element_type(self):
        """不同元素类型不应该兼容"""
        self.assertFalse(self.list_int.is_assignable_to(self.list_str))

    def test_any_element_type_covariance(self):
        """协变：list[int] 应该可以赋值给 list[Any]"""
        self.assertTrue(self.list_int.is_assignable_to(self.list_any))

    def test_raw_list_to_generic(self):
        """原始 list 应该可以赋值给 list[Any]"""
        self.assertTrue(self.list_raw.is_assignable_to(self.list_any))

    def test_raw_list_to_list_descriptor(self):
        """原始 list 应该可以赋值给 LIST_DESCRIPTOR"""
        self.assertTrue(self.list_raw.is_assignable_to(LIST_DESCRIPTOR))

    def test_list_to_list_descriptor(self):
        """list[int] 应该可以赋值给 LIST_DESCRIPTOR"""
        self.assertTrue(self.list_int.is_assignable_to(LIST_DESCRIPTOR))

    def test_list_to_non_list(self):
        """list 不应该可以赋值给非 list 类型"""
        self.assertFalse(self.list_int.is_assignable_to(STR_DESCRIPTOR))


class TestDictMetadataIsAssignableTo(unittest.TestCase):
    """测试 DictMetadata.is_assignable_to()"""

    def setUp(self):
        self.dict_str_int = DictMetadata(name="dict", key_type=STR_DESCRIPTOR, value_type=INT_DESCRIPTOR)
        self.dict_str_str = DictMetadata(name="dict", key_type=STR_DESCRIPTOR, value_type=STR_DESCRIPTOR)
        self.dict_any_any = DictMetadata(name="dict", key_type=ANY_DESCRIPTOR, value_type=ANY_DESCRIPTOR)
        self.dict_raw = DictMetadata(name="dict")

    def test_same_key_value_types(self):
        """相同键值类型应该兼容"""
        self.assertTrue(self.dict_str_int.is_assignable_to(self.dict_str_int))

    def test_different_value_types(self):
        """值类型不同不应该兼容"""
        self.assertFalse(self.dict_str_int.is_assignable_to(self.dict_str_str))

    def test_any_types_covariance(self):
        """协变：dict[str, int] 应该可以赋值给 dict[Any, Any]"""
        self.assertTrue(self.dict_str_int.is_assignable_to(self.dict_any_any))

    def test_raw_dict_to_any(self):
        """原始 dict 应该可以赋值给 dict[Any, Any]"""
        self.assertTrue(self.dict_raw.is_assignable_to(self.dict_any_any))

    def test_raw_dict_to_dict_descriptor(self):
        """原始 dict 应该可以赋值给 DICT_DESCRIPTOR"""
        self.assertTrue(self.dict_raw.is_assignable_to(DICT_DESCRIPTOR))

    def test_dict_to_dict_descriptor(self):
        """dict[str, int] 应该可以赋值给 DICT_DESCRIPTOR"""
        self.assertTrue(self.dict_str_int.is_assignable_to(DICT_DESCRIPTOR))

    def test_dict_to_non_dict(self):
        """dict 不应该可以赋值给非 dict 类型"""
        self.assertFalse(self.dict_str_int.is_assignable_to(STR_DESCRIPTOR))


class TestFunctionMetadataIsAssignableTo(unittest.TestCase):
    """测试 FunctionMetadata.is_assignable_to()"""

    def test_same_signature(self):
        """相同签名应该兼容"""
        func1 = FunctionMetadata(
            name="func",
            param_types=[INT_DESCRIPTOR],
            return_type=STR_DESCRIPTOR
        )
        func2 = FunctionMetadata(
            name="func",
            param_types=[INT_DESCRIPTOR],
            return_type=STR_DESCRIPTOR
        )
        self.assertTrue(func1.is_assignable_to(func2))

    def test_callable_descriptor(self):
        """任何函数都应该可以赋值给 callable"""
        func = FunctionMetadata(
            name="func",
            param_types=[INT_DESCRIPTOR],
            return_type=STR_DESCRIPTOR
        )
        self.assertTrue(func.is_assignable_to(CALLABLE_DESCRIPTOR))

    def test_return_type_covariance_int_to_any(self):
        """返回类型协变：int -> Any"""
        func_int = FunctionMetadata(
            name="func",
            param_types=[],
            return_type=INT_DESCRIPTOR
        )
        func_any = FunctionMetadata(
            name="func",
            param_types=[],
            return_type=ANY_DESCRIPTOR
        )
        self.assertTrue(func_int.is_assignable_to(func_any))

    def test_return_type_not_covariant_any_to_int(self):
        """返回类型不协变：Any -> int 应该失败"""
        func_any = FunctionMetadata(
            name="func",
            param_types=[],
            return_type=ANY_DESCRIPTOR
        )
        func_int = FunctionMetadata(
            name="func",
            param_types=[],
            return_type=INT_DESCRIPTOR
        )
        self.assertFalse(func_any.is_assignable_to(func_int))

    def test_param_contravariance_same_type(self):
        """参数逆变：相同类型参数应该兼容"""
        func_str = FunctionMetadata(
            name="func",
            param_types=[STR_DESCRIPTOR],
            return_type=INT_DESCRIPTOR
        )
        func_str2 = FunctionMetadata(
            name="func",
            param_types=[STR_DESCRIPTOR],
            return_type=INT_DESCRIPTOR
        )
        self.assertTrue(func_str.is_assignable_to(func_str2))

    def test_param_not_contravariant_reverse(self):
        """参数不逆变：不同名称的参数类型不兼容"""
        func_obj = FunctionMetadata(
            name="func",
            param_types=[TypeDescriptor(name="object")],
            return_type=INT_DESCRIPTOR
        )
        func_str = FunctionMetadata(
            name="func",
            param_types=[STR_DESCRIPTOR],
            return_type=INT_DESCRIPTOR
        )
        self.assertFalse(func_obj.is_assignable_to(func_str))

    def test_param_count_mismatch(self):
        """参数数量不匹配应该返回 False"""
        func1 = FunctionMetadata(
            name="func",
            param_types=[INT_DESCRIPTOR],
            return_type=STR_DESCRIPTOR
        )
        func2 = FunctionMetadata(
            name="func",
            param_types=[INT_DESCRIPTOR, STR_DESCRIPTOR],
            return_type=STR_DESCRIPTOR
        )
        self.assertFalse(func1.is_assignable_to(func2))


class TestClassMetadataIsAssignableTo(unittest.TestCase):
    """测试 ClassMetadata.is_assignable_to()"""

    def setUp(self):
        self.registry = create_default_registry()

    def test_same_class(self):
        """同类应该兼容"""
        class_a = ClassMetadata(name="MyClass", is_user_defined=True)
        class_a._registry = self.registry
        class_b = ClassMetadata(name="MyClass", is_user_defined=True)
        class_b._registry = self.registry
        self.assertTrue(class_a.is_assignable_to(class_b))

    def test_parent_class_compatibility(self):
        """父类应该兼容（通过继承链）"""
        parent = ClassMetadata(name="Parent", is_user_defined=True)
        registered_parent = self.registry.register(parent)

        child = ClassMetadata(name="Child", is_user_defined=True, parent_name="Parent")
        registered_child = self.registry.register(child)

        self.assertTrue(registered_child.is_assignable_to(registered_parent))

    def test_child_not_assignable_to_unrelated(self):
        """子类不应该兼容无关类"""
        class_a = ClassMetadata(name="ClassA", is_user_defined=True)
        class_a._registry = self.registry

        class_b = ClassMetadata(name="ClassB", is_user_defined=True)
        class_b._registry = self.registry

        self.assertFalse(class_a.is_assignable_to(class_b))

    def test_no_parent_returns_false(self):
        """无父类且结构不兼容应该返回 False"""
        orphan = ClassMetadata(name="Orphan", is_user_defined=True)
        orphan._registry = self.registry

        parent = ClassMetadata(name="Parent", is_user_defined=True)
        parent._registry = self.registry

        self.assertFalse(orphan.is_assignable_to(parent))


class TestBoundMethodMetadataIsAssignableTo(unittest.TestCase):
    """测试 BoundMethodMetadata.is_assignable_to()"""

    def test_callable_descriptor(self):
        """绑定方法应该可以赋值给 callable"""
        receiver = INT_DESCRIPTOR
        func = FunctionMetadata(
            name="method",
            param_types=[STR_DESCRIPTOR],
            return_type=BOOL_DESCRIPTOR
        )
        bound = BoundMethodMetadata(
            name="bound_method",
            receiver_type=receiver,
            function_type=func
        )
        self.assertTrue(bound.is_assignable_to(CALLABLE_DESCRIPTOR))

    def test_same_bound_method(self):
        """相同的绑定方法应该兼容"""
        receiver = INT_DESCRIPTOR
        func = FunctionMetadata(
            name="method",
            param_types=[STR_DESCRIPTOR],
            return_type=BOOL_DESCRIPTOR
        )
        bound1 = BoundMethodMetadata(
            name="bound_method",
            receiver_type=receiver,
            function_type=func
        )
        bound2 = BoundMethodMetadata(
            name="bound_method",
            receiver_type=receiver,
            function_type=func
        )
        self.assertTrue(bound1.is_assignable_to(bound2))

    def test_receiver_compatibility_same_type(self):
        """相同接收者类型应该兼容"""
        receiver = INT_DESCRIPTOR

        func = FunctionMetadata(
            name="method",
            param_types=[STR_DESCRIPTOR],
            return_type=BOOL_DESCRIPTOR
        )

        bound_receiver1 = BoundMethodMetadata(
            name="bound_method",
            receiver_type=receiver,
            function_type=func
        )
        bound_receiver2 = BoundMethodMetadata(
            name="bound_method",
            receiver_type=receiver,
            function_type=func
        )

        self.assertTrue(bound_receiver1.is_assignable_to(bound_receiver2))


class TestLazyDescriptorIsAssignableTo(unittest.TestCase):
    """测试 LazyDescriptor.is_assignable_to()"""

    def setUp(self):
        self.registry = create_default_registry()

    def test_delegates_to_resolved_descriptor(self):
        """应该委托给解析后的描述符"""
        lazy_int = LazyDescriptor(name="int", module_path="core.kernel")
        lazy_int._resolved = INT_DESCRIPTOR
        lazy_int._registry = self.registry

        self.assertTrue(lazy_int.is_assignable_to(INT_DESCRIPTOR))
        self.assertTrue(lazy_int.is_assignable_to(lazy_int))

    def test_without_resolution_returns_false_for_different_names(self):
        """未解析时应该基于名称比较"""
        lazy_a = LazyDescriptor(name="TypeA")
        lazy_b = LazyDescriptor(name="TypeB")

        self.assertFalse(lazy_a.is_assignable_to(lazy_b))


class TestIsAssignableToEdgeCases(unittest.TestCase):
    """边界情况和极端场景测试"""

    def test_none_handling(self):
        """处理 None 值"""
        desc = TypeDescriptor(name="int")
        result = desc.is_assignable_to(None)
        self.assertFalse(result)

    def test_void_compatibility(self):
        """void 类型兼容性"""
        void = TypeDescriptor(name="void", is_nullable=False)
        result = void.is_assignable_to(VOID_DESCRIPTOR)
        self.assertTrue(result)

    def test_var_dynamic_compatibility(self):
        """var (动态类型) 兼容性"""
        var = TypeDescriptor(name="var", is_nullable=True)
        var._axiom = DynamicAxiom(name="var")

        int_desc = TypeDescriptor(name="int", is_nullable=False)
        int_desc._axiom = IntAxiom()

        self.assertTrue(int_desc.is_assignable_to(var))
        self.assertFalse(var.is_assignable_to(int_desc))


class TestIsAssignableToWithPredefinedDescriptors(unittest.TestCase):
    """测试预定义描述符之间的赋值兼容性"""

    def test_int_descriptor_assignable_to_any(self):
        """INT_DESCRIPTOR 应该可以赋值给 ANY_DESCRIPTOR"""
        self.assertTrue(INT_DESCRIPTOR.is_assignable_to(ANY_DESCRIPTOR))

    def test_str_descriptor_assignable_to_any(self):
        """STR_DESCRIPTOR 应该可以赋值给 ANY_DESCRIPTOR"""
        self.assertTrue(STR_DESCRIPTOR.is_assignable_to(ANY_DESCRIPTOR))

    def test_float_descriptor_assignable_to_any(self):
        """FLOAT_DESCRIPTOR 应该可以赋值给 ANY_DESCRIPTOR"""
        self.assertTrue(FLOAT_DESCRIPTOR.is_assignable_to(ANY_DESCRIPTOR))

    def test_bool_descriptor_assignable_to_any(self):
        """BOOL_DESCRIPTOR 应该可以赋值给 ANY_DESCRIPTOR"""
        self.assertTrue(BOOL_DESCRIPTOR.is_assignable_to(ANY_DESCRIPTOR))

    def test_any_not_assignable_to_int(self):
        """ANY_DESCRIPTOR 不应该可以赋值给 INT_DESCRIPTOR"""
        self.assertFalse(ANY_DESCRIPTOR.is_assignable_to(INT_DESCRIPTOR))

    def test_list_descriptor_is_assignable_to_callable(self):
        """LIST_DESCRIPTOR 不应该可以赋值给 CALLABLE_DESCRIPTOR"""
        self.assertFalse(LIST_DESCRIPTOR.is_assignable_to(CALLABLE_DESCRIPTOR))

    def test_int_not_assignable_to_bool(self):
        """INT_DESCRIPTOR 不应该可以赋值给 BOOL_DESCRIPTOR"""
        self.assertFalse(INT_DESCRIPTOR.is_assignable_to(BOOL_DESCRIPTOR))

    def test_float_not_assignable_to_int(self):
        """FLOAT_DESCRIPTOR 不应该可以赋值给 INT_DESCRIPTOR"""
        self.assertFalse(FLOAT_DESCRIPTOR.is_assignable_to(INT_DESCRIPTOR))


if __name__ == "__main__":
    unittest.main()
