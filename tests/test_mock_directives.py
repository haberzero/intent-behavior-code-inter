import unittest
import sys
import os
import textwrap

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.support.diagnostics.issue_tracker import IssueTracker
from core.engine import IBCIEngine

class TestMockDirectives(unittest.TestCase):
    def setUp(self):
        self.issue_tracker = IssueTracker()
        self.outputs = []

    def run_code(self, code):
        engine = IBCIEngine()
        test_file = os.path.abspath("tmp_mock_directives.ibci")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(code).strip() + "\n")
            
        def output_callback(msg):
            self.outputs.append(msg)
            
        try:
            engine._prepare_interpreter(output_callback=output_callback)
            # Ensure TESTONLY mode
            ai = engine.interpreter.service_context.interop.get_package("ai")
            ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
            
            ast_cache = engine.scheduler.compile_project(test_file)
            engine.interpreter.interpret(ast_cache[test_file])
            return engine.interpreter
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_mock_fail_directive(self):
        """验证 MOCK:FAIL 指令能触发 llmexcept"""
        code = """
        if @~MOCK:FAIL~:
            print("SUCCESS")
        llmexcept:
            print("CAUGHT_MOCK_FAIL")
        """
        self.run_code(code)
        self.assertEqual(self.outputs, ["CAUGHT_MOCK_FAIL"])

    def test_mock_boolean_directives(self):
        """验证 MOCK:TRUE/FALSE 指令能精确控制分支"""
        code = """
        if @~MOCK:FALSE~:
            print("TRUE_BRANCH")
        else:
            print("FALSE_BRANCH")
            
        if @~MOCK:TRUE~:
            print("TRUE_BRANCH_2")
        """
        self.run_code(code)
        self.assertIn("FALSE_BRANCH", self.outputs)
        self.assertIn("TRUE_BRANCH_2", self.outputs)
        self.assertNotIn("TRUE_BRANCH", self.outputs)

    def test_mock_repair_loop(self):
        """验证 MOCK:REPAIR 能够模拟 失败->维修->重试 的完整生命周期"""
        code = """
        import ai
        int attempts = 0
        if @~MOCK:REPAIR~:
            print("REPAIRED_SUCCESS")
        llmexcept:
            attempts = attempts + 1
            print("REPAIRING_ATTEMPT_" + (str)attempts)
            ai.set_retry_hint("Fixed it!")
            retry
        """
        self.run_code(code)
        # 流程应该是：
        # 1. 第一次判断 @~MOCK:REPAIR~ -> 返回 MOCK_UNCERTAIN_RESPONSE -> 触发 llmexcept
        # 2. llmexcept 执行 -> 打印 ATTEMPT_1 -> 设置 retry_hint -> 执行 retry
        # 3. 第二次判断 @~MOCK:REPAIR~ -> 检测到 retry_hint -> 返回 "1" -> 进入 if 块
        # 4. 打印 REPAIRED_SUCCESS
        self.assertEqual(self.outputs, ["REPAIRING_ATTEMPT_1", "REPAIRED_SUCCESS"])

    def test_mock_text_marker(self):
        """验证常规模拟输出带有 [MOCK] 标记"""
        code = """
        str res = @~hello world~
        print(res)
        """
        self.run_code(code)
        self.assertTrue(any("[MOCK]" in o for o in self.outputs))
        self.assertTrue(any("hello world" in o for o in self.outputs))

if __name__ == '__main__':
    unittest.main()
