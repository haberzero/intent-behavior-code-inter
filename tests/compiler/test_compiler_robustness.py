import unittest
from tests.compiler.base import BaseCompilerTest
from core.compiler.serialization.serializer import FlatSerializer

class TestCompilerRobustness(BaseCompilerTest):
    """
    编译器健壮性测试：验证各种错误场景（基于 Standard Error Fixtures）及序列化。
    """

    def test_type_errors(self):
        # 验证类型不匹配检测 (基于标准错误 Fixture)
        self.assert_compile_fail("standard/error_scenarios/type_errors.ibci")

    def test_scope_errors(self):
        # 验证作用域冲突及 global 声明校验
        self.assert_compile_fail("standard/error_scenarios/scope_errors.ibci")

    def test_oop_errors(self):
        # 验证继承冲突及非法成员访问
        self.assert_compile_fail("standard/error_scenarios/oop_errors.ibci")

    def test_serialization_integrity(self):
        # 使用 standard/core_syntax.ibci 验证全语法树的序列化完整性
        artifact = self.assert_compile_success("standard/core_syntax.ibci")
        res = self.get_main_result(artifact)
        
        serializer = FlatSerializer()
        flat_data = serializer.serialize_result(res)
        
        # Verify pools exist
        pools = flat_data["pools"]
        self.assertIn("nodes", pools)
        self.assertIn("symbols", pools)
        self.assertIn("types", pools)
        self.assertIn("scopes", pools)
        
        # Verify symbol pool has 'Animal'
        animal_sym_uid = None
        for uid, sym in pools["symbols"].items():
            if sym["name"] == "Animal":
                animal_sym_uid = uid
                break
        self.assertIsNotNone(animal_sym_uid)
        
        # Verify type pool has corresponding class type
        animal_type_uid = pools["symbols"][animal_sym_uid].get("type_uid")
        self.assertIn(animal_type_uid, pools["types"])
        self.assertEqual(pools["types"][animal_type_uid]["name"], "Animal")

if __name__ == "__main__":
    unittest.main()
