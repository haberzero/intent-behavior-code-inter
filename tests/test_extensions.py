import unittest
import sys
import os
import textwrap

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.engine import IBCIEngine
from core.support.host_interface import HostInterface
from core.compiler.semantic.types import ModuleType, ANY_TYPE, INT_TYPE, FunctionType
from core.types.symbol_types import SymbolType
from core.types.scope_types import ScopeNode, ScopeType
from tests.ibc_test_case import IBCTestCase

class MockPlugin:
    def __init__(self):
        self.version = "1.0.0"
    def add(self, a, b): return a + b
    def _internal(self): return "hidden"

class TestExtensions(IBCTestCase):
    """
    Consolidated tests for Plugin System and Mock Directives.
    Covers host interface reflection, manual metadata, and special test directives.
    """

    def setUp(self):
        super().setUp()
        self.outputs = []

    def run_code(self, code):
        # Use inherited create_engine to support core_debug
        engine = self.create_engine()
        test_file = os.path.abspath("tmp_extensions_test.ibci")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(code).strip() + "\n")
            
        def output_callback(msg):
            self.outputs.append(msg)
            
        try:
            engine._prepare_interpreter(output_callback=output_callback)
            # Ensure ai module is in TESTONLY mode for mock directives
            ai = engine.interpreter.service_context.interop.get_package("ai")
            ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
            
            ast_cache = engine.scheduler.compile_project(test_file)
            engine.interpreter.interpret(ast_cache[test_file])
            return engine.interpreter
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    # --- Host Interface & Reflection ---

    def test_host_interface_reflection(self):
        """验证 HostInterface 是否能通过反射正确推断 Python 对象的成员并过滤私有成员"""
        host = HostInterface()
        plugin = MockPlugin()
        host.register_module("my_plugin", plugin)
        
        mod_type = host.get_module_type("my_plugin")
        scope = mod_type.scope
        
        # Verify function and variable inference
        self.assertEqual(scope.resolve("add").type, SymbolType.FUNCTION)
        self.assertEqual(scope.resolve("version").type, SymbolType.VARIABLE)
        
        # Verify private member filtering
        self.assertIsNone(scope.resolve("_internal"))

    def test_host_interface_manual_metadata(self):
        """验证手动提供元数据时应优先于反射推断"""
        host = HostInterface()
        custom_scope = ScopeNode(ScopeType.GLOBAL)
        custom_scope.define("add", SymbolType.FUNCTION).type_info = FunctionType([INT_TYPE, INT_TYPE], INT_TYPE)
        custom_metadata = ModuleType(custom_scope)
        
        host.register_module("math_plugin", None, custom_metadata)
        
        mod_type = host.get_module_type("math_plugin")
        add_sym = mod_type.scope.resolve("add")
        self.assertEqual(add_sym.type_info.name, "function")
        self.assertEqual(add_sym.type_info.return_type, INT_TYPE)

    # --- Mock Directives (Testing Features) ---

    def test_mock_fail_and_boolean_directives(self):
        """验证 MOCK:FAIL, MOCK:TRUE/FALSE 等指令对 AI 控制流的精确控制"""
        code = """
        if @~MOCK:FAIL~:
            print("SUCCESS")
        llmexcept:
            print("CAUGHT_MOCK_FAIL")
            
        if @~MOCK:FALSE~:
            print("TRUE_BRANCH")
        else:
            print("FALSE_BRANCH")
        """
        self.run_code(code)
        self.assertIn("CAUGHT_MOCK_FAIL", self.outputs)
        self.assertIn("FALSE_BRANCH", self.outputs)

    def test_mock_repair_lifecycle(self):
        """验证 MOCK:REPAIR 模拟 失败->维修->重试 的完整生命周期"""
        code = """
        import ai
        int attempts = 0
        if @~MOCK:REPAIR~:
            print("REPAIRED_SUCCESS")
        llmexcept:
            attempts = attempts + 1
            ai.set_retry_hint("Fixed it!")
            retry
        """
        self.run_code(code)
        # Flow: MOCK:REPAIR -> fails -> llmexcept -> retry -> success
        self.assertIn("REPAIRED_SUCCESS", self.outputs)

    def test_mock_text_interpolation(self):
        """验证常规模拟输出及其在 User Prompt 中的表现"""
        code = """
        str res = @~hello world~
        print(res)
        """
        self.run_code(code)
        self.assertTrue(any("[MOCK]" in o for o in self.outputs))
        self.assertTrue(any("hello world" in o for o in self.outputs))

if __name__ == '__main__':
    unittest.main()
