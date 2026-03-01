
import unittest
import os
from core.engine import IBCIEngine
from core.runtime.ext.capabilities import ExtensionCapabilities
from ibc_modules.idbg import create_implementation

class TestIDbgSafety(unittest.TestCase):
    def setUp(self):
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.engine = IBCIEngine(root_dir=self.root_dir)
        self.engine._prepare_interpreter(output_callback=None)
        self.idbg = create_implementation()
        
        # 模拟能力注入
        caps = ExtensionCapabilities()
        caps.state_reader = self.engine.interpreter.context
        caps.stack_inspector = self.engine.interpreter
        
        self.idbg.setup(caps)

    def test_circular_reference_handling(self):
        """测试循环引用情况下的 vars() 导出（虽然 ibci 难以创建循环引用，但 Python 层面可能发生）"""
        ctx = self.engine.interpreter.context
        a = [1]
        b = [a]
        a.append(b) # a -> b -> a
        
        ctx.define_variable("circular", a)
        
        # vars() 本身不应该死循环，因为它只是返回引用
        vars_dict = self.idbg.vars()
        self.assertIn("circular", vars_dict)
        self.assertEqual(vars_dict["circular"]["value"], a)

    def test_deep_nesting(self):
        """测试深层嵌套作用域"""
        ctx = self.engine.interpreter.context
        initial_count = len(self.idbg.vars())
        
        for i in range(100):
            ctx.enter_scope()
            ctx.define_variable(f"v_{i}", i)
            
        vars_dict = self.idbg.vars()
        self.assertEqual(len(vars_dict), 100 + initial_count)
        self.assertEqual(vars_dict["v_99"]["value"], 99)
        self.assertEqual(vars_dict["v_0"]["value"], 0)

    def test_large_data(self):
        """测试大数据量情况"""
        ctx = self.engine.interpreter.context
        large_list = list(range(10000))
        ctx.define_variable("large", large_list)
        
        vars_dict = self.idbg.vars()
        self.assertEqual(vars_dict["large"]["value"], large_list)

if __name__ == "__main__":
    unittest.main()
