import unittest
import os
import sys
import json
import textwrap

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine import IBCIEngine
from core.runtime.ext.capabilities import ExtensionCapabilities
from ibc_modules.idbg import create_implementation
from tests.ibc_test_case import IBCTestCase

class TestIDbg(IBCTestCase):
    """
    Consolidated tests for IDbg module.
    Covers core functionality, integration with IBCI code, and safety/robustness.
    """

    def setUp(self):
        super().setUp()
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # self.engine is already created by IBCTestCase.setUp()
        # but here we need to ensure it's pointing to the correct root_dir if needed
        # Actually self.engine = self.create_engine(root_dir=self.root_dir) is safer
        self.engine = self.create_engine(root_dir=self.root_dir)
        self.engine._prepare_interpreter(output_callback=None)
        self.idbg = create_implementation()
        
        # Inject capabilities
        caps = ExtensionCapabilities()
        caps.state_reader = self.engine.interpreter.context
        caps.stack_inspector = self.engine.interpreter
        caps.llm_provider = self.engine.interpreter.llm_executor.llm_callback
        self.idbg.setup(caps)

    # --- Core Functionality ---

    def test_vars_export_and_filtering(self):
        """测试基础变量导出与内置对象过滤"""
        ctx = self.engine.interpreter.context
        ctx.define_variable("a", 10)
        ctx.define_variable("b", "hello")
        ctx.define_variable("c", [1, 2, 3], is_const=True)
        
        # 模拟一个复杂对象和内置对象
        class ComplexObj: pass
        ctx.define_variable("complex", ComplexObj())
        ctx.define_variable("idbg_inst", self.idbg)
        
        vars_dict = self.idbg.vars()
        
        # Verify normal variables
        self.assertEqual(vars_dict["a"]["value"], 10)
        self.assertEqual(vars_dict["a"]["type"], "int")
        self.assertEqual(vars_dict["b"]["value"], "hello")
        self.assertTrue(vars_dict["c"]["is_const"])
        
        # Verify filtering
        self.assertNotIn("complex", vars_dict)
        self.assertNotIn("idbg_inst", vars_dict)

    def test_last_llm_capture(self):
        """测试 LLM 调用捕获"""
        # IES architecture: LLMProvider (ai module) records last_call_info
        # We simulate this via the injected provider
        provider = self.idbg._capabilities.llm_provider
        mock_info = {
            "sys_prompt": "sys",
            "user_prompt": "user",
            "response": "res",
            "scene": "test"
        }
        
        # In actual execution, ai_pkg instance stores this
        ai_pkg = self.engine.interpreter.service_context.interop.get_package("ai")
        ai_pkg._last_call_info = mock_info
        
        last = self.idbg.last_llm()
        self.assertEqual(last, mock_info)

    def test_env_info(self):
        """测试环境信息获取（指令计数、调用栈、意图栈）"""
        interp = self.engine.interpreter
        interp.instruction_count = 123
        interp.call_stack_depth = 5
        
        env = self.idbg.env()
        self.assertEqual(env["instruction_count"], 123)
        self.assertEqual(env["call_stack_depth"], 5)
        self.assertIn("active_intents", env)

    def test_vars_nested_scopes(self):
        """测试嵌套作用域下的变量导出与遮蔽"""
        ctx = self.engine.interpreter.context
        ctx.define_variable("global_v", 1)
        
        ctx.enter_scope()
        ctx.define_variable("local_v", 2)
        
        ctx.enter_scope()
        ctx.define_variable("local_v", 3) # Shadowing
        
        vars_dict = self.idbg.vars()
        self.assertEqual(vars_dict["global_v"]["value"], 1)
        self.assertEqual(vars_dict["local_v"]["value"], 3)

    # --- Integration with IBCI Code ---

    def test_idbg_in_ibci_code(self):
        """测试在 ibci 代码中导入并调用 idbg"""
        code = textwrap.dedent("""
            import idbg
            int test_val = 123
            dict v = idbg.vars()
        """).strip() + "\n"
        # Run manually to avoid file I/O for simple code
        from core.compiler.lexer.lexer import Lexer
        from core.compiler.parser.parser import Parser
        
        lexer = Lexer(code.strip())
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast_node = parser.parse()
        
        self.engine.interpreter.interpret(ast_node)
        
        v_result = self.engine.interpreter.context.get_variable("v")
        self.assertIn("test_val", v_result)
        self.assertEqual(v_result["test_val"]["value"], 123)

    # --- Safety & Robustness ---

    def test_circular_reference_safety(self):
        """测试循环引用情况下的 vars() 导出安全性"""
        ctx = self.engine.interpreter.context
        a = [1]
        b = [a]
        a.append(b) # a -> b -> a
        
        ctx.define_variable("circular", a)
        
        # Should not crash with infinite recursion
        vars_dict = self.idbg.vars()
        self.assertIn("circular", vars_dict)
        self.assertEqual(vars_dict["circular"]["value"], a)

    def test_deep_nesting_and_large_data(self):
        """测试深层嵌套作用域和大数据量情况"""
        ctx = self.engine.interpreter.context
        
        # Deep nesting
        for i in range(50):
            ctx.enter_scope()
            ctx.define_variable(f"v_{i}", i)
            
        # Large data
        large_list = list(range(1000))
        ctx.define_variable("large", large_list)
        
        vars_dict = self.idbg.vars()
        self.assertEqual(vars_dict["v_49"]["value"], 49)
        self.assertEqual(vars_dict["large"]["value"], large_list)

    def test_uninitialized_safety(self):
        """测试未初始化（未调用 setup）时的安全性"""
        idbg_safe = create_implementation()
        self.assertEqual(idbg_safe.vars(), {})
        self.assertEqual(idbg_safe.last_llm(), {})
        self.assertEqual(idbg_safe.env(), {})

if __name__ == "__main__":
    unittest.main()
