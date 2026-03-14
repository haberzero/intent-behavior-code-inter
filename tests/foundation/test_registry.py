import unittest
from core.foundation.registry import Registry
from core.domain.factory import create_default_registry
from core.domain.types.descriptors import TypeDescriptor

class TestRegistryContract(unittest.TestCase):
    """
    验证 Foundation Registry 的强契约、令牌防护和描述符一致性。
    遵循 VERIFICATION_GUIDE.md 2.3 节。
    """
    
    def setUp(self):
        self.registry = Registry()
        self.meta_registry = create_default_registry()
        self.kernel_token = self.registry.get_kernel_token()
        self.registry.register_metadata_registry(self.meta_registry, self.kernel_token)

    def test_token_protection(self):
        """验证非法令牌无法调用特权接口"""
        unauthorized_token = object()
        
        # 尝试使用非法令牌注册元数据注册表
        with self.assertRaises(PermissionError):
            self.registry.register_metadata_registry(self.meta_registry, unauthorized_token)
            
        # 验证令牌单次发放性
        second_kernel_token = self.registry.get_kernel_token()
        self.assertIsNone(second_kernel_token, "内核令牌不应被多次发放")

    def test_descriptor_consistency(self):
        """验证注册类时的描述符名称一致性 (Zero String Magic)"""
        class MockIbClass:
            name = "MyClass"
            descriptor = None
            
        # 故意制造不匹配的描述符
        wrong_desc = TypeDescriptor(name="WrongName")
        
        with self.assertRaisesRegex(ValueError, "Descriptor name 'WrongName' does not match registered name 'MyClass'"):
            self.registry.register_class("MyClass", MockIbClass, self.kernel_token, descriptor=wrong_desc)

    def test_seal_mechanism(self):
        """验证封印机制"""
        self.registry.seal_structure(self.kernel_token)
        
        # 封印后尝试修改核心工厂
        with self.assertRaisesRegex(PermissionError, "Structure is sealed"):
            self.registry.register_box_func(lambda x: x, self.kernel_token)

    def test_instance_isolation(self):
        """验证不同 Registry 实例间的元数据隔离"""
        registry2 = Registry()
        self.assertNotEqual(id(self.registry.get_kernel_token()), id(registry2.get_kernel_token()), 
                           "不同实例的令牌物理地址必须不同")

if __name__ == '__main__':
    unittest.main()
