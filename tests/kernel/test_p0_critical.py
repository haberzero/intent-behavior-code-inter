import unittest
from core.kernel.symbols import Symbol, VariableSymbol, SymbolKind
from core.kernel.types.descriptors import TypeDescriptor, INT_DESCRIPTOR, STR_DESCRIPTOR


class TestSymbolWalkReferencesBehavior(unittest.TestCase):
    """[P0] 测试 Symbol.walk_references() 修改 self.descriptor 的行为"""

    def test_walk_references_modifies_self_descriptor(self):
        """验证 walk_references 确实修改了 self.descriptor（这是设计意图）"""
        original_desc = INT_DESCRIPTOR
        sym = VariableSymbol(name="x", kind=SymbolKind.VARIABLE, descriptor=original_desc)

        self.assertIs(sym.descriptor, original_desc)

        def transform_callback(desc):
            return STR_DESCRIPTOR

        sym.walk_references(transform_callback)

        self.assertIs(sym.descriptor, STR_DESCRIPTOR)

    def test_walk_references_with_none_descriptor(self):
        """验证 descriptor 为 None 时的行为"""
        sym = VariableSymbol(name="x", kind=SymbolKind.VARIABLE)
        self.assertIsNone(sym.descriptor)

        sym.walk_references(lambda d: d)

        self.assertIsNone(sym.descriptor)

    def test_walk_references_returns_none(self):
        """验证 walk_references 返回 None（就地修改）"""
        sym = VariableSymbol(name="x", kind=SymbolKind.VARIABLE, descriptor=INT_DESCRIPTOR)

        result = sym.walk_references(lambda d: STR_DESCRIPTOR)

        self.assertIsNone(result)

    def test_walk_references_callback_receives_original_descriptor(self):
        """验证回调接收到原始 descriptor"""
        received = []

        sym = VariableSymbol(name="x", kind=SymbolKind.VARIABLE, descriptor=INT_DESCRIPTOR)

        def tracking_callback(desc):
            received.append(desc)
            return desc

        sym.walk_references(tracking_callback)

        self.assertEqual(len(received), 1)
        self.assertIs(received[0], INT_DESCRIPTOR)


class TestTypeDescriptorCloneWithMemo(unittest.TestCase):
    """[P0] 测试 TypeDescriptor.clone() 使用 memo 的行为"""

    def test_clone_uses_memo_to_prevent_duplicate(self):
        """验证 memo 字典防止重复克隆同一对象"""
        shared_desc = TypeDescriptor(name="Shared")
        class_a = TypeDescriptor(name="ClassA")
        class_b = TypeDescriptor(name="ClassB")

        class_a.members["shared"] = Symbol(name="s1", kind=SymbolKind.VARIABLE, descriptor=shared_desc)
        class_b.members["shared"] = Symbol(name="s2", kind=SymbolKind.VARIABLE, descriptor=shared_desc)

        memo = {}
        cloned_a = class_a.clone(memo)
        cloned_b = class_b.clone(memo)

        self.assertIs(cloned_a.members["shared"].descriptor,
                      cloned_b.members["shared"].descriptor)

    def test_clone_resets_runtime_bindings(self):
        """验证克隆后的描述符重置了运行时绑定"""
        desc = TypeDescriptor(name="TestType")
        desc._registry = "some_registry"
        desc._axiom = "some_axiom"

        cloned = desc.clone()

        self.assertIsNone(cloned._registry)
        self.assertIsNone(cloned._axiom)

    def test_clone_deeply_nested_types(self):
        """测试深层嵌套类型的克隆"""
        from core.kernel.types.descriptors import ListMetadata, DictMetadata, FunctionMetadata

        nested_list = ListMetadata(
            element_type=FunctionMetadata(
                name="nested_func",
                param_types=[ListMetadata(element_type=INT_DESCRIPTOR)],
                return_type=DictMetadata(key_type=STR_DESCRIPTOR, value_type=INT_DESCRIPTOR)
            )
        )

        cloned = nested_list.clone()

        self.assertIsNot(cloned, nested_list)
        self.assertIsNot(cloned.element_type, nested_list.element_type)
        self.assertIsNot(cloned.element_type.return_type, nested_list.element_type.return_type)


class TestAxiomHydratorProcessingCycleDetection(unittest.TestCase):
    """[P0] 测试 AxiomHydrator._processing 防递归机制"""

    def setUp(self):
        from core.kernel.types.axiom_hydrator import AxiomHydrator
        from core.kernel.types.registry import MetadataRegistry
        from core.kernel.axioms.registry import AxiomRegistry
        from core.kernel.axioms.primitives import register_core_axioms

        self.axiom_registry = AxiomRegistry()
        register_core_axioms(self.axiom_registry)
        self.registry = MetadataRegistry(axiom_registry=self.axiom_registry)
        self.hydrator = AxiomHydrator(self.registry)

    def test_processing_set_tracks_hydration_state(self):
        """测试 _processing 集合追踪 hydration 状态"""
        desc = TypeDescriptor(name="TestType")

        self.assertEqual(len(self.hydrator._processing), 0)

        self.hydrator.hydrate_metadata(desc)

        self.assertEqual(len(self.hydrator._processing), 0)

    def test_processing_set_cleared_after_hydration(self):
        """测试 hydration 完成后 _processing 被清空"""
        desc = TypeDescriptor(name="TestType")

        self.hydrator.hydrate_metadata(desc)

        self.assertEqual(len(self.hydrator._processing), 0)

    def test_multiple_hydrations_independent(self):
        """测试多次 hydration 是独立的"""
        desc1 = TypeDescriptor(name="Type1")
        desc2 = TypeDescriptor(name="Type2")

        result1 = self.hydrator.hydrate_metadata(desc1)
        result2 = self.hydrator.hydrate_metadata(desc2)

        self.assertIsNotNone(result1)
        self.assertIsNotNone(result2)
        self.assertEqual(len(self.hydrator._processing), 0)


class TestHostInterfaceRegisterModule(unittest.TestCase):
    """[P0] 测试 HostInterface.register_module() 和 register_global_function()"""

    def test_register_module_basic(self):
        """测试基本模块注册"""
        from core.runtime.host.host_interface import HostInterface, HostModuleRegistry

        host = HostInterface()
        registry = HostModuleRegistry()

        class TestModule:
            def __init__(self):
                self.name = "test_module"

        impl = TestModule()
        registry.register("test", impl)

        retrieved = registry.get("test")
        self.assertIs(retrieved, impl)

    def test_register_module_via_host_interface(self):
        """测试通过 HostInterface 注册模块"""
        from core.runtime.host.host_interface import HostInterface
        from core.kernel.factory import create_default_registry

        registry = create_default_registry()
        host = HostInterface(external_registry=registry)

        class TestModule:
            pass

        impl = TestModule()
        metadata = registry.resolve("module")

        host.register_module("test", impl, metadata)
        retrieved = host.get_module_implementation("test")
        self.assertIs(retrieved, impl)

    def test_register_global_function_via_host_interface(self):
        """测试通过 HostInterface 注册全局函数"""
        from core.runtime.host.host_interface import HostInterface
        from core.kernel.factory import create_default_registry

        registry = create_default_registry()
        host = HostInterface(external_registry=registry)

        def my_func():
            pass

        metadata = registry.resolve("callable")
        host.register_global_function("my_func", my_func, metadata)

        self.assertIn("my_func", host.runtime._implementations)
        self.assertIs(host.runtime._implementations["my_func"], my_func)

    def test_host_interface_runtime_is_host_module_registry(self):
        """验证 HostInterface.runtime 是 HostModuleRegistry 实例"""
        from core.runtime.host.host_interface import HostInterface, HostModuleRegistry

        host = HostInterface()
        self.assertIsInstance(host.runtime, HostModuleRegistry)

    def test_host_module_registry_register_and_get(self):
        """测试 HostModuleRegistry 的基本注册和获取"""
        from core.runtime.host.host_interface import HostModuleRegistry

        registry = HostModuleRegistry()

        class TestModule:
            pass

        impl = TestModule()
        registry.register("test", impl)

        self.assertIs(registry.get("test"), impl)

    def test_host_module_registry_get_nonexistent(self):
        """测试获取未注册的模块"""
        from core.runtime.host.host_interface import HostModuleRegistry

        registry = HostModuleRegistry()
        self.assertIsNone(registry.get("nonexistent"))

    def test_host_interface_has_axiom_registry(self):
        """验证 HostInterface 正确绑定 AxiomRegistry"""
        from core.runtime.host.host_interface import HostInterface
        from core.kernel.factory import create_default_registry

        registry = create_default_registry()
        host = HostInterface(external_registry=registry)

        self.assertIsNotNone(host.get_axiom_registry())
        self.assertIs(host.get_axiom_registry(), registry.get_axiom_registry())

    def test_host_interface_without_registry_creates_own_axiom_registry(self):
        """验证 HostInterface() 不带参数时自动创建 AxiomRegistry"""
        from core.runtime.host.host_interface import HostInterface

        host = HostInterface()

        self.assertIsNotNone(host.get_axiom_registry())


if __name__ == "__main__":
    unittest.main()
