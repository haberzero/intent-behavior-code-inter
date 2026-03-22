import unittest
from core.kernel.axioms.primitives import (
    IntAxiom, FloatAxiom, BoolAxiom, StrAxiom, ListAxiom, DictAxiom, DynamicAxiom
)
from core.kernel.types.descriptors import (
    TypeDescriptor, INT_DESCRIPTOR, FLOAT_DESCRIPTOR, STR_DESCRIPTOR,
    LIST_DESCRIPTOR, DICT_DESCRIPTOR, BOOL_DESCRIPTOR
)


class TestIntAxiomIsCompatible(unittest.TestCase):
    """测试 IntAxiom.is_compatible 方法"""

    def setUp(self):
        self.axiom = IntAxiom()

    def test_int_compatible_with_int(self):
        """int 与 int 兼容"""
        int_desc = TypeDescriptor(name="int")
        int_desc._axiom = IntAxiom()
        self.assertTrue(self.axiom.is_compatible(int_desc))

    def test_int_not_compatible_with_str(self):
        """int 与 str 不兼容"""
        str_desc = TypeDescriptor(name="str")
        str_desc._axiom = StrAxiom()
        self.assertFalse(self.axiom.is_compatible(str_desc))

    def test_int_not_compatible_with_float(self):
        """int 与 float 不兼容"""
        float_desc = TypeDescriptor(name="float")
        float_desc._axiom = FloatAxiom()
        self.assertFalse(self.axiom.is_compatible(float_desc))

    def test_int_not_compatible_with_bool(self):
        """int 与 bool 不兼容"""
        bool_desc = TypeDescriptor(name="bool")
        bool_desc._axiom = BoolAxiom()
        self.assertFalse(self.axiom.is_compatible(bool_desc))


class TestFloatAxiomIsCompatible(unittest.TestCase):
    """测试 FloatAxiom.is_compatible 方法"""

    def setUp(self):
        self.axiom = FloatAxiom()

    def test_float_compatible_with_float(self):
        """float 与 float 兼容"""
        float_desc = TypeDescriptor(name="float")
        float_desc._axiom = FloatAxiom()
        self.assertTrue(self.axiom.is_compatible(float_desc))

    def test_float_not_compatible_with_int(self):
        """float 与 int 不兼容"""
        int_desc = TypeDescriptor(name="int")
        int_desc._axiom = IntAxiom()
        self.assertFalse(self.axiom.is_compatible(int_desc))


class TestBoolAxiomIsCompatible(unittest.TestCase):
    """测试 BoolAxiom.is_compatible 方法"""

    def setUp(self):
        self.axiom = BoolAxiom()

    def test_bool_compatible_with_bool(self):
        """bool 与 bool 兼容"""
        bool_desc = TypeDescriptor(name="bool")
        bool_desc._axiom = BoolAxiom()
        self.assertTrue(self.axiom.is_compatible(bool_desc))

    def test_bool_not_compatible_with_int(self):
        """bool 与 int 不兼容"""
        int_desc = TypeDescriptor(name="int")
        int_desc._axiom = IntAxiom()
        self.assertFalse(self.axiom.is_compatible(int_desc))


class TestStrAxiomIsCompatible(unittest.TestCase):
    """测试 StrAxiom.is_compatible 方法"""

    def setUp(self):
        self.axiom = StrAxiom()

    def test_str_compatible_with_str(self):
        """str 与 str 兼容"""
        str_desc = TypeDescriptor(name="str")
        str_desc._axiom = StrAxiom()
        self.assertTrue(self.axiom.is_compatible(str_desc))

    def test_str_not_compatible_with_int(self):
        """str 与 int 不兼容"""
        int_desc = TypeDescriptor(name="int")
        int_desc._axiom = IntAxiom()
        self.assertFalse(self.axiom.is_compatible(int_desc))


class TestListAxiomIsCompatible(unittest.TestCase):
    """测试 ListAxiom.is_compatible 方法"""

    def setUp(self):
        self.axiom = ListAxiom()

    def test_list_compatible_with_list(self):
        """list 与 list 兼容"""
        list_desc = TypeDescriptor(name="list")
        list_desc._axiom = ListAxiom()
        self.assertTrue(self.axiom.is_compatible(list_desc))

    def test_list_not_compatible_with_str(self):
        """list 与 str 不兼容"""
        str_desc = TypeDescriptor(name="str")
        str_desc._axiom = StrAxiom()
        self.assertFalse(self.axiom.is_compatible(str_desc))


class TestDictAxiomIsCompatible(unittest.TestCase):
    """测试 DictAxiom.is_compatible 方法"""

    def setUp(self):
        self.axiom = DictAxiom()

    def test_dict_compatible_with_dict(self):
        """dict 与 dict 兼容"""
        dict_desc = TypeDescriptor(name="dict")
        dict_desc._axiom = DictAxiom()
        self.assertTrue(self.axiom.is_compatible(dict_desc))

    def test_dict_not_compatible_with_list(self):
        """dict 与 list 不兼容"""
        list_desc = TypeDescriptor(name="list")
        list_desc._axiom = ListAxiom()
        self.assertFalse(self.axiom.is_compatible(list_desc))


class TestDynamicAxiomIsCompatible(unittest.TestCase):
    """测试 DynamicAxiom.is_compatible 方法"""

    def setUp(self):
        self.axiom = DynamicAxiom(name="var")

    def test_var_compatible_with_everything(self):
        """var (Any) 与任何类型兼容"""
        types = [
            TypeDescriptor(name="int"),
            TypeDescriptor(name="str"),
            TypeDescriptor(name="float"),
            TypeDescriptor(name="bool"),
            TypeDescriptor(name="list"),
            TypeDescriptor(name="dict"),
        ]
        for desc in types:
            desc._axiom = IntAxiom()
            self.assertTrue(self.axiom.is_compatible(desc))


if __name__ == "__main__":
    unittest.main()
