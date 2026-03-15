from tests.base import BaseIBCTest
from core.runtime.objects.builtins import IbList, IbBehavior

class TestAutomationBinding(BaseIBCTest):
    """
    验证自动化绑定与执行 (Phase 3.2)。
    确保公理定义的方法能自动绑定到 Python 实现，且延迟执行逻辑正确。
    """

    def test_axiom_method_binding(self):
        """验证 list.append 是否通过公理自动化绑定"""
        # [IES 2.0] 使用 Engine 标准加载后的 Registry
        registry = self.engine.registry
        list_class = registry.get_class("list")
        self.assertIsNotNone(list_class)
        
        # 验证虚表中存在 append
        append_method = list_class.lookup_method("append")
        self.assertIsNotNone(append_method)
        
        # 创建实例并调用
        items = registry.box([])
        self.assertIsInstance(items, IbList)
        self.assertEqual(len(items.elements), 0)
        
        # 模拟消息传递调用 append
        val = registry.box(42)
        items.receive("append", [val])
        
        self.assertEqual(len(items.elements), 1)
        self.assertEqual(items.elements[0].to_native(), 42)

    def test_deferred_execution_wrapping(self):
        """验证 node_is_deferred 标记的节点在运行时被正确包裹为 IbBehavior"""
        code = """
        var x = @~ compute something ~
        """
        # 使用标准 run_code 执行
        self.run_code(code)
        
        # 从解释器上下文中获取变量 x
        x_val = self.engine.interpreter.runtime_context.get_variable("x")
        
        # 验证变量 x 的值是一个 IbBehavior 对象
        self.assertIsInstance(x_val, IbBehavior)
        # 验证其 node uid 存在且非空
        self.assertTrue(x_val.node.startswith("node_"))

if __name__ == "__main__":
    unittest.main()
