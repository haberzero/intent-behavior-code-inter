import unittest
from core.runtime.host.host_interface import HostModuleRegistry, HostInterface


class TestHostModuleRegistry(unittest.TestCase):
    """测试 HostModuleRegistry 类"""

    def setUp(self):
        """每个测试前创建新的 registry"""
        self.registry = HostModuleRegistry()

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(len(self.registry._implementations), 0)

    def test_register(self):
        """测试注册模块"""
        mock_impl = object()
        self.registry.register("test_module", mock_impl)
        self.assertEqual(len(self.registry._implementations), 1)
        self.assertIs(self.registry._implementations["test_module"], mock_impl)

    def test_get_existing(self):
        """测试获取已注册的模块"""
        mock_impl = object()
        self.registry.register("test_module", mock_impl)
        result = self.registry.get("test_module")
        self.assertIs(result, mock_impl)

    def test_get_nonexisting(self):
        """测试获取未注册的模块"""
        result = self.registry.get("nonexistent")
        self.assertIsNone(result)

    def test_register_overwrite(self):
        """测试覆盖已注册的模块"""
        mock_impl1 = object()
        mock_impl2 = object()
        self.registry.register("test_module", mock_impl1)
        self.registry.register("test_module", mock_impl2)
        self.assertEqual(len(self.registry._implementations), 1)
        self.assertIs(self.registry._implementations["test_module"], mock_impl2)


class TestHostInterfacePure(unittest.TestCase):
    """测试 HostInterface 纯 Python 逻辑（不涉及 kernel 依赖）"""

    def test_runtime_attribute_is_host_module_registry(self):
        """测试 HostInterface.runtime 属性是 HostModuleRegistry 实例"""
        host = HostInterface()
        self.assertIsInstance(host.runtime, HostModuleRegistry)

    def test_get_module_implementation_delegates_to_runtime(self):
        """测试 get_module_implementation 正确委托给 runtime"""
        host = HostInterface()
        mock_impl = object()
        host.runtime.register("test_module", mock_impl)

        result = host.get_module_implementation("test_module")
        self.assertIs(result, mock_impl)

    def test_get_module_implementation_nonexisting(self):
        """测试获取未注册的模块实现"""
        host = HostInterface()
        result = host.get_module_implementation("nonexistent")
        self.assertIsNone(result)


class TestHostModuleRegistryIntegration(unittest.TestCase):
    """测试 HostModuleRegistry 集成场景"""

    def test_multiple_modules(self):
        """测试注册多个模块"""
        registry = HostModuleRegistry()
        impl1 = object()
        impl2 = object()
        impl3 = object()

        registry.register("module1", impl1)
        registry.register("module2", impl2)
        registry.register("module3", impl3)

        self.assertIs(registry.get("module1"), impl1)
        self.assertIs(registry.get("module2"), impl2)
        self.assertIs(registry.get("module3"), impl3)
        self.assertEqual(len(registry._implementations), 3)

    def test_module_lifecycle(self):
        """测试模块注册生命周期"""
        registry = HostModuleRegistry()
        impl = object()

        self.assertIsNone(registry.get("lifecycle"))
        registry.register("lifecycle", impl)
        self.assertIs(registry.get("lifecycle"), impl)

    def test_different_modules_same_impl(self):
        """测试不同模块可以注册相同的实现"""
        registry = HostModuleRegistry()
        shared_impl = object()

        registry.register("module_a", shared_impl)
        registry.register("module_b", shared_impl)

        self.assertIs(registry.get("module_a"), shared_impl)
        self.assertIs(registry.get("module_b"), shared_impl)
        self.assertEqual(len(registry._implementations), 2)


if __name__ == "__main__":
    unittest.main()
