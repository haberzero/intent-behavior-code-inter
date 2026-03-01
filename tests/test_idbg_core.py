
import unittest
import os
from core.engine import IBCIEngine
from core.runtime.interpreter.interpreter import Interpreter
from core.runtime.interpreter.runtime_context import RuntimeContext
from core.runtime.interpreter.llm_executor import LLMExecutor
from core.runtime.ext.capabilities import ExtensionCapabilities
from ibc_modules.idbg import create_implementation

class TestIDbgCore(unittest.TestCase):
    def setUp(self):
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.engine = IBCIEngine(root_dir=self.root_dir)
        self.engine._prepare_interpreter(output_callback=None)
        self.idbg = create_implementation()
        
        # 模拟能力注入
        caps = ExtensionCapabilities()
        caps.state_reader = self.engine.interpreter.context
        caps.stack_inspector = self.engine.interpreter
        caps.llm_provider = self.engine.interpreter.llm_executor.llm_callback
        
        self.idbg.setup(caps)

    def test_vars_basic(self):
        """测试基础变量导出"""
        ctx = self.engine.interpreter.context
        ctx.define_variable("a", 10)
        ctx.define_variable("b", "hello")
        ctx.define_variable("c", [1, 2, 3], is_const=True)
        
        vars_dict = self.idbg.vars()
        
        self.assertIn("a", vars_dict)
        self.assertEqual(vars_dict["a"]["value"], 10)
        self.assertEqual(vars_dict["a"]["type"], "int")
        
        self.assertIn("b", vars_dict)
        self.assertEqual(vars_dict["b"]["value"], "hello")
        self.assertEqual(vars_dict["b"]["type"], "str")
        
        self.assertIn("c", vars_dict)
        self.assertEqual(vars_dict["c"]["value"], [1, 2, 3])
        self.assertTrue(vars_dict["c"]["is_const"])

    def test_vars_filtering(self):
        """测试内置对象过滤"""
        ctx = self.engine.interpreter.context
        # 模拟一个复杂对象
        class ComplexObj: pass
        ctx.define_variable("complex", ComplexObj())
        ctx.define_variable("idbg", self.idbg) # 应该被过滤
        ctx.define_variable("valid_var", 42)
        
        vars_dict = self.idbg.vars()
        
        self.assertIn("valid_var", vars_dict)
        self.assertNotIn("complex", vars_dict)
        self.assertNotIn("idbg", vars_dict)

    def test_last_llm_capture(self):
        """测试 LLM 调用捕获"""
        # 在 IES 架构中，LLMProvider (即 ai 模块) 负责记录 last_call_info
        provider = self.idbg._capabilities.llm_provider
        
        # 模拟一次调用记录
        mock_info = {
            "sys_prompt": "sys",
            "user_prompt": "user",
            "response": "res",
            "type": "test"
        }
        # 模拟 Provider 的行为
        if hasattr(provider, "_last_call_info"):
            provider._last_call_info = mock_info
        elif hasattr(provider, "last_call_info"):
            provider.last_call_info = mock_info
        
        last = self.idbg.last_llm()
        self.assertEqual(last, mock_info)

    def test_env_info(self):
        """测试环境信息获取"""
        interp = self.engine.interpreter
        interp.instruction_count = 123
        interp.call_stack_depth = 5
        
        env = self.idbg.env()
        self.assertEqual(env["instruction_count"], 123)
        self.assertEqual(env["call_stack_depth"], 5)
        self.assertIn("active_intents", env)

    def test_safety_null_context(self):
        """测试空上下文安全性"""
        idbg_safe = create_implementation()
        # 未调用 setup
        self.assertEqual(idbg_safe.vars(), {})
        self.assertEqual(idbg_safe.last_llm(), {})
        self.assertEqual(idbg_safe.env(), {})

    def test_vars_nested_scopes(self):
        """测试嵌套作用域下的变量导出"""
        ctx = self.engine.interpreter.context
        ctx.define_variable("global_v", 1)
        
        ctx.enter_scope()
        ctx.define_variable("local_v", 2)
        
        # 再次进入作用域并遮蔽
        ctx.enter_scope()
        ctx.define_variable("local_v", 3)
        
        vars_dict = self.idbg.vars()
        
        self.assertIn("global_v", vars_dict)
        self.assertEqual(vars_dict["global_v"]["value"], 1)
        
        self.assertIn("local_v", vars_dict)
        self.assertEqual(vars_dict["local_v"]["value"], 3) # 应该是最内层的
        
if __name__ == "__main__":
    unittest.main()
