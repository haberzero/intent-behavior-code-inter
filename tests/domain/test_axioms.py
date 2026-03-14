import unittest
from core.domain.factory import create_default_registry
from core.domain.types.descriptors import INT_DESCRIPTOR, LIST_DESCRIPTOR, EXCEPTION_DESCRIPTOR

class TestAxioms(unittest.TestCase):
    """
    验证公理系统的能力发现与行为逻辑。
    遵循 VERIFICATION_GUIDE.md 2.2 节。
    """
    
    def setUp(self):
        self.meta_registry = create_default_registry()

    def test_method_discovery(self):
        """验证基础公理能正确返回其预定义的方法元数据"""
        # 验证 ListAxiom
        list_desc = self.meta_registry.resolve("list")
        self.assertIsNotNone(list_desc._axiom)
        methods = list_desc._axiom.get_methods()
        
        self.assertIn("append", methods)
        self.assertIn("pop", methods)
        self.assertIn("len", methods)
        self.assertIn("__getitem__", methods)
        
        # 验证方法签名 (简单抽样)
        append_meta = methods["append"]
        self.assertEqual(append_meta.name, "append")
        self.assertEqual(len(append_meta.param_types), 1)

    def test_parser_capability(self):
        """验证 ParserCapability 能正确处理字符串到原生值的转换"""
        int_desc = self.meta_registry.resolve("int")
        parser = int_desc._axiom.get_parser_capability()
        self.assertIsNotNone(parser)
        
        self.assertEqual(parser.parse_value("123"), 123)
        self.assertEqual(parser.parse_value("  456  "), 456)
        
        bool_desc = self.meta_registry.resolve("bool")
        bool_parser = bool_desc._axiom.get_parser_capability()
        self.assertTrue(bool_parser.parse_value("true"))
        self.assertTrue(bool_parser.parse_value("1"))
        self.assertFalse(bool_parser.parse_value("false"))

if __name__ == '__main__':
    unittest.main()
