import unittest
import os
import shutil
from tests.compiler.base import BaseCompilerTest
from core.compiler.semantic.symbols import VariableSymbol, STATIC_INT, STATIC_STR
from core.support.module_spec_builder import SpecBuilder

class TestSchedulerDecoupling(BaseCompilerTest):
    """
    调度器与工程结构测试：验证多文件导入、循环引用及外部注入。
    """

    def test_variable_injection(self):
        # 注入 Python 原生对象
        vars = {
            "count": 10,
            "name": "Alice"
        }
        
        # 使用动态生成的 ibci 代码
        test_file = os.path.join(self.test_root, "injection_test.ibci")
        with open(test_file, "w") as f:
            f.write("int x = count\n")
            
        self.engine.run(test_file, variables=vars, prepare_interpreter=False)
        
        predefined = self.engine.scheduler.predefined_symbols
        self.assertIn("count", predefined)
        self.assertIsInstance(predefined["count"], VariableSymbol)
        self.assertEqual(predefined["count"].type_info, STATIC_INT)

    def test_external_plugin_registration(self):
        # 模拟插件注册
        spec = (SpecBuilder("math_plugin")
            .func("calc", params=["int"], returns="int")
            .build())
        
        self.engine.register_plugin("math_plugin", {"calc": lambda x: x}, type_metadata=spec)
        
        # 动态代码测试
        test_file = os.path.join(self.test_root, "plugin_test.ibci")
        with open(test_file, "w") as f:
            f.write("import math_plugin\nvar res = math_plugin.calc(1)\n")
            
        self.assert_compile_success(test_file)

    def test_valid_multi_file_imports(self):
        """测试合法的跨目录、多文件导入"""
        # 拷贝标准导入夹具的内容到测试根目录，以确保 import pkg.utils 能正确解析
        src_dir = self.get_fixture_path("standard/projects/valid_imports")
        for item in os.listdir(src_dir):
            s = os.path.join(src_dir, item)
            d = os.path.join(self.test_root, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
        
        # 编译主入口 (现在就在 test_root 下，使用绝对路径避免 assert_compile_success 再次尝试从 fixtures 目录拷贝)
        main_file = os.path.join(self.test_root, "main.ibci")
        self.assert_compile_success(main_file)

    def test_circular_dependency_detection(self):
        """测试循环引用检测"""
        src_dir = self.get_fixture_path("standard/projects/circular_imports")
        for item in os.listdir(src_dir):
            s = os.path.join(src_dir, item)
            d = os.path.join(self.test_root, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
        
        # a.ibci 现在在 test_root 下
        main_file = os.path.join(self.test_root, "a.ibci")
        self.assert_compile_fail(main_file)

if __name__ == "__main__":
    unittest.main()
