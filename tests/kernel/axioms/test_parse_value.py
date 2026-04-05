import unittest
from core.kernel.axioms.primitives import (
    IntAxiom, FloatAxiom, BoolAxiom, StrAxiom, ListAxiom, DictAxiom, DynamicAxiom
)


class TestIntAxiomParseValue(unittest.TestCase):
    """测试 IntAxiom.parse_value 方法"""

    def setUp(self):
        self.axiom = IntAxiom()

    def test_parse_positive_integer(self):
        """测试解析正整数"""
        self.assertEqual(self.axiom.parse_value("42"), 42)
        self.assertEqual(self.axiom.parse_value("12345"), 12345)

    def test_parse_negative_integer(self):
        """测试解析负整数"""
        self.assertEqual(self.axiom.parse_value("-42"), -42)
        self.assertEqual(self.axiom.parse_value("-12345"), -12345)

    def test_parse_integer_with_text(self):
        """测试从混合文本中提取整数"""
        self.assertEqual(self.axiom.parse_value("The answer is 42"), 42)
        self.assertEqual(self.axiom.parse_value("Value: -99 in sentence"), -99)

    def test_parse_integer_with_spaces(self):
        """测试带空格的整数"""
        self.assertEqual(self.axiom.parse_value("  100  "), 100)

    def test_parse_integer_raises_on_no_number(self):
        """测试无数字时抛出 ValueError"""
        with self.assertRaises(ValueError):
            self.axiom.parse_value("no number here")


class TestFloatAxiomParseValue(unittest.TestCase):
    """测试 FloatAxiom.parse_value 方法"""

    def setUp(self):
        self.axiom = FloatAxiom()

    def test_parse_positive_float(self):
        """测试解析正浮点数"""
        self.assertEqual(self.axiom.parse_value("3.14"), 3.14)
        self.assertEqual(self.axiom.parse_value("123.456"), 123.456)

    def test_parse_negative_float(self):
        """测试解析负浮点数"""
        self.assertEqual(self.axiom.parse_value("-3.14"), -3.14)
        self.assertEqual(self.axiom.parse_value("-123.456"), -123.456)

    def test_parse_float_without_decimal(self):
        """测试解析没有小数点的数字"""
        self.assertEqual(self.axiom.parse_value("42"), 42.0)

    def test_parse_float_with_text(self):
        """测试从混合文本中提取浮点数"""
        self.assertEqual(self.axiom.parse_value("Pi is approximately 3.14159"), 3.14159)

    def test_parse_float_raises_on_no_number(self):
        """测试无数字时抛出 ValueError"""
        with self.assertRaises(ValueError):
            self.axiom.parse_value("no number here")


class TestBoolAxiomParseValue(unittest.TestCase):
    """测试 BoolAxiom.parse_value 方法"""

    def setUp(self):
        self.axiom = BoolAxiom()

    def test_parse_true_values(self):
        """测试解析各种 True 值"""
        self.assertTrue(self.axiom.parse_value("true"))
        self.assertTrue(self.axiom.parse_value("True"))
        self.assertTrue(self.axiom.parse_value("1"))
        self.assertTrue(self.axiom.parse_value("yes"))
        self.assertTrue(self.axiom.parse_value("on"))

    def test_parse_false_values(self):
        """测试解析各种 False 值"""
        self.assertFalse(self.axiom.parse_value("false"))
        self.assertFalse(self.axiom.parse_value("False"))
        self.assertFalse(self.axiom.parse_value("0"))
        self.assertFalse(self.axiom.parse_value("no"))
        self.assertFalse(self.axiom.parse_value("off"))

    def test_parse_bool_with_spaces(self):
        """测试带空格的布尔值"""
        self.assertTrue(self.axiom.parse_value("  true  "))
        self.assertFalse(self.axiom.parse_value("  false  "))

    def test_parse_bool_searches_text(self):
        """测试从文本中搜索布尔值"""
        self.assertTrue(self.axiom.parse_value("The result is true"))


class TestStrAxiomParseValue(unittest.TestCase):
    """测试 StrAxiom.parse_value 方法"""

    def setUp(self):
        self.axiom = StrAxiom()

    def test_parse_simple_string(self):
        """测试解析简单字符串"""
        self.assertEqual(self.axiom.parse_value("hello"), "hello")

    def test_parse_string_with_spaces(self):
        """测试解析带空格的字符串"""
        self.assertEqual(self.axiom.parse_value("  hello world  "), "hello world")

    def test_parse_string_with_markdown_code_block(self):
        """测试解析 markdown 代码块包裹的字符串"""
        result = self.axiom.parse_value("```json\n  hello world\n```")
        self.assertEqual(result, "hello world")

    def test_parse_string_with_markdown_code_block_text(self):
        """测试解析 text 代码块包裹的字符串"""
        result = self.axiom.parse_value("```text\n  hello\n```")
        self.assertEqual(result, "hello")

    def test_parse_empty_string(self):
        """测试解析空字符串"""
        self.assertEqual(self.axiom.parse_value(""), "")


class TestListAxiomParseValue(unittest.TestCase):
    """测试 ListAxiom.parse_value 方法"""

    def setUp(self):
        self.axiom = ListAxiom()

    def test_parse_simple_list(self):
        """测试解析简单 JSON 数组"""
        result = self.axiom.parse_value("[1, 2, 3]")
        self.assertEqual(result, [1, 2, 3])

    def test_parse_list_with_spaces(self):
        """测试解析带空格的数组"""
        result = self.axiom.parse_value("  [1, 2, 3]  ")
        self.assertEqual(result, [1, 2, 3])

    def test_parse_empty_list(self):
        """测试解析空数组"""
        result = self.axiom.parse_value("[]")
        self.assertEqual(result, [])

    def test_parse_nested_list(self):
        """测试解析嵌套数组"""
        result = self.axiom.parse_value("[[1, 2], [3, 4]]")
        self.assertEqual(result, [[1, 2], [3, 4]])

    def test_parse_list_with_text_around(self):
        """测试从混合文本中提取数组"""
        result = self.axiom.parse_value("Here is the list: [1, 2, 3] end")
        self.assertEqual(result, [1, 2, 3])


class TestDictAxiomParseValue(unittest.TestCase):
    """测试 DictAxiom.parse_value 方法"""

    def setUp(self):
        self.axiom = DictAxiom()

    def test_parse_simple_dict(self):
        """测试解析简单 JSON 对象"""
        result = self.axiom.parse_value('{"a": 1, "b": 2}')
        self.assertEqual(result, {"a": 1, "b": 2})

    def test_parse_empty_dict(self):
        """测试解析空对象"""
        result = self.axiom.parse_value("{}")
        self.assertEqual(result, {})

    def test_parse_nested_dict(self):
        """测试解析嵌套对象"""
        result = self.axiom.parse_value('{"outer": {"inner": 42}}')
        self.assertEqual(result, {"outer": {"inner": 42}})

    def test_parse_dict_with_spaces(self):
        """测试解析带空格的对象"""
        result = self.axiom.parse_value('  {"a": 1}  ')
        self.assertEqual(result, {"a": 1})


class TestDynamicAxiomParseValue(unittest.TestCase):
    """测试 DynamicAxiom.parse_value 方法"""

    def setUp(self):
        self.axiom = DynamicAxiom(name="auto")

    def test_parse_returns_stripped_string(self):
        """测试 Any 类型直接返回去除首尾空格的字符串"""
        self.assertEqual(self.axiom.parse_value("hello"), "hello")
        self.assertEqual(self.axiom.parse_value("  hello  "), "hello")
        self.assertEqual(self.axiom.parse_value("123"), "123")


if __name__ == "__main__":
    unittest.main()
