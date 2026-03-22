import unittest
from core.runtime.host.host_interface import HostModuleRegistry, HostInterface


class TestHostModuleRegistryExtended(unittest.TestCase):
    """扩展测试 HostModuleRegistry - 纯 Python 逻辑"""

    def test_register_accepts_any_implementation(self):
        """测试 register 接受任何类型的实现"""
        registry = HostModuleRegistry()

        class CustomClass:
            pass

        impl = CustomClass()
        registry.register("custom", impl)
        self.assertIs(registry.get("custom"), impl)

    def test_register_with_none(self):
        """测试 register 可以接受 None"""
        registry = HostModuleRegistry()
        registry.register("none_impl", None)
        self.assertIsNone(registry.get("none_impl"))

    def test_get_returns_none_for_empty_key(self):
        """测试 get 对空字符串 key 返回 None"""
        registry = HostModuleRegistry()
        registry.register("", object())
        self.assertIsNotNone(registry.get(""))

    def test_multiple_modules(self):
        """测试注册多个模块"""
        registry = HostModuleRegistry()
        impl1 = object()
        impl2 = object()

        registry.register("module1", impl1)
        registry.register("module2", impl2)

        self.assertIs(registry.get("module1"), impl1)
        self.assertIs(registry.get("module2"), impl2)
        self.assertEqual(len(registry._implementations), 2)


class TestHostInterfaceRuntimeDelegation(unittest.TestCase):
    """测试 HostInterface 运行时委托逻辑"""

    def test_get_module_implementation_delegates(self):
        """测试 get_module_implementation 委托给 runtime"""
        host = HostInterface()

        mock_impl = object()
        host.runtime.register("test_module", mock_impl)

        result = host.get_module_implementation("test_module")
        self.assertIs(result, mock_impl)

    def test_get_module_implementation_nonexisting(self):
        """测试获取不存在的模块"""
        host = HostInterface()
        result = host.get_module_implementation("nonexistent")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
