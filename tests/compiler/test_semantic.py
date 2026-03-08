import unittest
from tests.compiler.base import BaseCompilerTest
from core.domain.symbols import (
    STATIC_INT, STATIC_STR, STATIC_BOOL, STATIC_FLOAT
)

class TestSemantic(BaseCompilerTest):
    """
    语义分析测试：基于标准 Fixture 验证符号表和类型系统。
    """

    def test_basics_semantic(self):
        artifact = self.assert_compile_success("standard/basics.ibci")
        res = self.get_main_result(artifact)
        self.assertEqual(res.symbol_table.resolve("a").type_info, STATIC_INT)
        self.assertEqual(res.symbol_table.resolve("result").type_info, STATIC_INT)

    def test_oop_semantic(self):
        artifact = self.assert_compile_success("standard/oop.ibci")
        res = self.get_main_result(artifact)
        animal_sym = res.symbol_table.resolve("Animal")
        self.assertTrue(animal_sym.type_info.is_class)
        self.assertIsNotNone(animal_sym.type_info.resolve_member("speak"))

    def test_control_flow_semantic(self):
        artifact = self.assert_compile_success("standard/control_flow.ibci")
        res = self.get_main_result(artifact)
        self.assertEqual(res.symbol_table.resolve("local_var").type_info, STATIC_INT)

    def test_standard_smoke_semantic(self):
        # 编译全能标准语法样板
        self.assert_compile_success("standard/core_syntax.ibci")

if __name__ == "__main__":
    unittest.main()
