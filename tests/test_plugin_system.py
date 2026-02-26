import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.support.host_interface import HostInterface
from core.compiler.semantic.types import ModuleType, ANY_TYPE
from core.types.symbol_types import SymbolType

class MockPlugin:
    def __init__(self):
        self.version = "1.0.0"
        
    def add(self, a, b):
        return a + b
        
    def _internal(self):
        return "hidden"

class TestPluginSystem(unittest.TestCase):
    def test_host_interface_reflection(self):
        """验证 HostInterface 是否能通过反射正确推断 Python 对象的成员"""
        host = HostInterface()
        plugin = MockPlugin()
        
        # 注册插件，不提供元数据
        host.register_module("my_plugin", plugin)
        
        # 获取推断出的类型信息
        mod_type = host.get_module_type("my_plugin")
        self.assertIsInstance(mod_type, ModuleType)
        
        scope = mod_type.scope
        
        # 1. 验证函数推断
        sym_add = scope.resolve("add")
        self.assertIsNotNone(sym_add)
        self.assertEqual(sym_add.type, SymbolType.FUNCTION)
        # 默认推断出的类型应为 ANY_TYPE
        self.assertEqual(sym_add.type_info, ANY_TYPE)
        
        # 2. 验证变量推断
        # 注意：反射 dir() 出来的实例属性可能需要实例已经初始化。
        # 对于类对象，dir() 可能只看到类方法。
        # 我们的 MockPlugin 实例有 version 属性。
        sym_version = scope.resolve("version")
        self.assertIsNotNone(sym_version)
        self.assertEqual(sym_version.type, SymbolType.VARIABLE)
        
        # 3. 验证私有成员过滤
        sym_internal = scope.resolve("_internal")
        self.assertIsNone(sym_internal)

    def test_host_interface_manual_metadata(self):
        """验证手动提供元数据时应优先使用"""
        from core.types.scope_types import ScopeNode, ScopeType
        from core.compiler.semantic.types import FunctionType, INT_TYPE
        
        host = HostInterface()
        
        custom_scope = ScopeNode(ScopeType.GLOBAL)
        custom_scope.define("add", SymbolType.FUNCTION).type_info = FunctionType([INT_TYPE, INT_TYPE], INT_TYPE)
        custom_metadata = ModuleType(custom_scope)
        
        host.register_module("math_plugin", None, custom_metadata)
        
        mod_type = host.get_module_type("math_plugin")
        self.assertEqual(mod_type.scope.resolve("add").type_info.name, "function")
        self.assertEqual(mod_type.scope.resolve("add").type_info.return_type, INT_TYPE)

if __name__ == '__main__':
    unittest.main()
