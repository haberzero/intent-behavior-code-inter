import unittest
import os
import shutil
from core.engine import IBCIEngine
from core.runtime.module_system.discovery import ModuleDiscoveryService
from core.runtime.module_system.loader import ModuleLoader

class TestModuleSystem(unittest.TestCase):
    def setUp(self):
        self.test_root = os.path.abspath("tmp_module_system_test")
        os.makedirs(self.test_root, exist_ok=True)
        self.plugins_dir = os.path.join(self.test_root, "plugins")
        os.makedirs(self.plugins_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_root):
            shutil.rmtree(self.test_root)

    def test_dynamic_plugin_discovery_and_loading(self):
        # 1. 创建一个模拟插件
        plugin_name = "hello_plugin"
        plugin_dir = os.path.join(self.plugins_dir, plugin_name)
        os.makedirs(plugin_dir, exist_ok=True)
        
        # 编写 spec.py
        with open(os.path.join(plugin_dir, "spec.py"), "w", encoding="utf-8") as f:
            f.write("""
from core.support.module_spec_builder import SpecBuilder
spec = (SpecBuilder("hello_plugin")
    .func("greet", params=["str"], returns="str")
    .build())
""")
            
        # 编写 __init__.py
        with open(os.path.join(plugin_dir, "__init__.py"), "w", encoding="utf-8") as f:
            f.write("""
class HelloPlugin:
    def greet(self, name: str) -> str:
        return f"Hello, {name} from plugin!"
implementation = HelloPlugin()
""")

        # 2. 使用 IBCIEngine 自动发现并加载
        engine = IBCIEngine(root_dir=self.test_root)
        
        # 验证元数据是否已发现
        self.assertTrue(engine.host_interface.is_external_module(plugin_name))
        
        # 3. 运行代码测试调用
        code = """
import hello_plugin
str msg = hello_plugin.greet("World")
print(msg)
"""
        test_file = os.path.join(self.test_root, "run_plugin.ibci")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(code)
            
        outputs = []
        def output_callback(msg):
            outputs.append(msg)
            
        success = engine.run(test_file, output_callback=output_callback)
        self.assertTrue(success)
        self.assertIn("Hello, World from plugin!", outputs)

    def test_builtin_priority(self):
        # 如果 plugins 中有一个同名模块，内置模块应该优先（或根据搜索路径顺序）
        # 目前 IBCIEngine 的搜索顺序是 [builtin, plugins]
        # discovery.py 中有 discovered_modules set 保证第一个发现的优先
        
        plugin_name = "math" # 内置模块名
        plugin_dir = os.path.join(self.plugins_dir, plugin_name)
        os.makedirs(plugin_dir, exist_ok=True)
        
        with open(os.path.join(plugin_dir, "spec.py"), "w", encoding="utf-8") as f:
            f.write("""
from core.support.module_spec_builder import SpecBuilder
spec = (SpecBuilder("math").func("fake_func").build())
""")
            
        engine = IBCIEngine(root_dir=self.test_root)
        
        # 验证 math 依然是内置的那个（检查是否有 sqrt 而不是 fake_func）
        math_meta = engine.host_interface.get_module_type("math")
        self.assertTrue(math_meta.scope.resolve("sqrt"))
        self.assertFalse(math_meta.scope.resolve("fake_func"))

if __name__ == '__main__':
    unittest.main()
