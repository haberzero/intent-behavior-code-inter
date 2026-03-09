import unittest
import os
from tests.compiler.base import BaseCompilerTest
from core.foundation.module_spec_builder import SpecBuilder

class TestPluginClass(BaseCompilerTest):
    """
    插件类测试：验证通过元数据注入的外部类型在编译阶段的合法性。
    """

    def test_plugin_class_declaration(self):
        # 1. 模拟插件定义一个类
        spec = (SpecBuilder("db_plugin")
            .cls("Database")
                .field("connection_string", "str")
                .method("connect", params=["str"], returns="bool")
            .build())
        self.engine.register_plugin("db_plugin", {}, type_metadata=spec)
        
        # 2. 动态创建测试代码
        code = """
import db_plugin
db_plugin.Database db = db_plugin.Database()
db.connection_string = "localhost"
bool success = db.connect("admin")
"""
        test_file = os.path.join(self.test_root, "plugin_ok.ibci")
        with open(test_file, "w") as f:
            f.write(code)
            
        self.assert_compile_success(test_file)

    def test_plugin_class_type_mismatch(self):
        # 1. 模拟插件定义
        spec = (SpecBuilder("db_plugin")
            .cls("Database")
                .field("port", "int")
            .build())
        self.engine.register_plugin("db_plugin", {}, type_metadata=spec)
        
        # 2. 动态创建测试代码
        code = """
import db_plugin
db_plugin.Database db = db_plugin.Database()
db.port = "8080" # Error: Cannot assign str to int
"""
        test_file = os.path.join(self.test_root, "plugin_fail.ibci")
        with open(test_file, "w") as f:
            f.write(code)
            
        self.assert_compile_fail(test_file)

if __name__ == "__main__":
    unittest.main()
