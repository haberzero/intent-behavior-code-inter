import unittest
from core.base.source_atomic import Severity, Location


class TestSeverity(unittest.TestCase):
    """测试 Severity 枚举"""

    def test_severity_values(self):
        """验证 Severity 枚举的所有成员"""
        self.assertEqual(Severity.HINT.value, 1)
        self.assertEqual(Severity.INFO.value, 2)
        self.assertEqual(Severity.WARNING.value, 3)
        self.assertEqual(Severity.ERROR.value, 4)
        self.assertEqual(Severity.FATAL.value, 5)

    def test_severity_count(self):
        """验证 Severity 枚举成员数量"""
        members = list(Severity)
        self.assertEqual(len(members), 5)

    def test_severity_is_enum(self):
        """验证 Severity 是枚举类型"""
        from enum import Enum
        self.assertTrue(issubclass(Severity, Enum))


class TestLocation(unittest.TestCase):
    """测试 Location 数据类"""

    def test_location_creation_defaults(self):
        """测试默认创建"""
        loc = Location()
        self.assertIsNone(loc.file_path)
        self.assertEqual(loc.line, 0)
        self.assertEqual(loc.column, 0)
        self.assertEqual(loc.length, 1)
        self.assertIsNone(loc.end_line)
        self.assertIsNone(loc.end_column)
        self.assertIsNone(loc.context_line)

    def test_location_creation_with_values(self):
        """测试带值创建"""
        loc = Location(
            file_path="test.ibci",
            line=10,
            column=5,
            length=3,
            end_line=10,
            end_column=8,
            context_line="var x = 42"
        )
        self.assertEqual(loc.file_path, "test.ibci")
        self.assertEqual(loc.line, 10)
        self.assertEqual(loc.column, 5)
        self.assertEqual(loc.length, 3)
        self.assertEqual(loc.end_line, 10)
        self.assertEqual(loc.end_column, 8)
        self.assertEqual(loc.context_line, "var x = 42")

    def test_location_str_with_file(self):
        """测试带文件路径的 __str__"""
        loc = Location(file_path="test.ibci", line=10, column=5)
        result = str(loc)
        self.assertEqual(result, "test.ibci:line 10, column 5")

    def test_location_str_without_file(self):
        """测试不带文件路径的 __str__"""
        loc = Location(line=10, column=5)
        result = str(loc)
        self.assertEqual(result, "line 10, column 5")

    def test_location_equality(self):
        """测试 Location 相等性"""
        loc1 = Location(file_path="a.ibci", line=1, column=1)
        loc2 = Location(file_path="a.ibci", line=1, column=1)
        loc3 = Location(file_path="b.ibci", line=1, column=1)
        self.assertEqual(loc1, loc2)
        self.assertNotEqual(loc1, loc3)

    def test_location_is_dataclass(self):
        """验证 Location 是 dataclass"""
        from dataclasses import is_dataclass
        self.assertTrue(is_dataclass(Location))


class TestLocationEdgeCases(unittest.TestCase):
    """测试 Location 边界情况"""

    def test_location_with_zero_values(self):
        """测试零值"""
        loc = Location(line=0, column=0)
        self.assertEqual(loc.line, 0)
        self.assertEqual(loc.column, 0)

    def test_location_with_large_values(self):
        """测试大数值"""
        loc = Location(line=1000000, column=50000)
        self.assertEqual(loc.line, 1000000)
        self.assertEqual(loc.column, 50000)

    def test_location_multiline(self):
        """测试多行位置"""
        loc = Location(line=5, column=10, end_line=10, end_column=20)
        self.assertEqual(loc.line, 5)
        self.assertEqual(loc.end_line, 10)
        self.assertGreater(loc.end_line, loc.line)


if __name__ == "__main__":
    unittest.main()
