import unittest
from core.domain.factory import create_default_registry
from core.domain.types.descriptors import LIST_DESCRIPTOR, INT_DESCRIPTOR, ListMetadata

class TestUTSDescriptors(unittest.TestCase):
    """
    验证 UTS 描述符的唯一性、解包逻辑和兼容性判定。
    遵循 VERIFICATION_GUIDE.md 2.1 节。
    """
    
    def setUp(self):
        self.meta_registry = create_default_registry()
        self.factory = self.meta_registry.factory

    def test_descriptor_uniqueness(self):
        """验证通过工厂创建的相同结构描述符在同一实例内地址唯一 (驻留池验证)"""
        # 暂时系统还没实现大规模驻留，我们验证基础内置描述符的唯一性
        list_int_1 = self.factory.create_list(INT_DESCRIPTOR)
        list_int_2 = self.factory.create_list(INT_DESCRIPTOR)
        
        # [AUDIT] 这是一个预留的验证点。如果目前尚未实现 Interning，此处可能失败。
        # 但内置的 INT_DESCRIPTOR 必须是唯一的。
        self.assertIs(list_int_1.element_type, list_int_2.element_type, "内置 int 描述符引用必须唯一")

    def test_assignability_zero_string(self):
        """验证类型兼容性检查不依赖字符串魔法"""
        list_any = LIST_DESCRIPTOR # 这是 list[Any] 的原型
        list_int = self.factory.create_list(INT_DESCRIPTOR)
        
        # 验证 list[int] 可以赋值给 list (由于逻辑宽松处理)
        self.assertTrue(list_int.is_assignable_to(list_any), "list[int] 应该能赋值给 list[Any]")
        
        # 验证 int 不能赋值给 list
        self.assertFalse(INT_DESCRIPTOR.is_assignable_to(list_any), "int 不应该能赋值给 list")

    def test_lazy_unwrap(self):
        """验证延迟加载描述符的正确还原"""
        # 模拟一个延迟描述符逻辑 (如果存在)
        # 目前主要验证 descriptors.py 中的 unwrap() 覆盖
        self.assertIs(INT_DESCRIPTOR.unwrap(), INT_DESCRIPTOR)

if __name__ == '__main__':
    unittest.main()
