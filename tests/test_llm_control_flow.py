import unittest
import sys
import os
import textwrap

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.diagnostics.issue_tracker import IssueTracker
from typedef.exception_types import LLMUncertaintyError
from app.engine import IBCIEngine

class TestLLMControlFlow(unittest.TestCase):
    def run_code(self, code, llm_responses=None):
        engine = IBCIEngine()
        # Mock LLM
        llm_call_count = 0
        def mock_llm(sys_prompt, user_prompt, scene="general"):
            nonlocal llm_call_count
            if llm_responses and llm_call_count < len(llm_responses):
                res = llm_responses[llm_call_count]
                llm_call_count += 1
                return res
            return "1"

        outputs = []
        def output_callback(msg):
            outputs.append(msg)

        # 创建临时文件
        test_file = os.path.abspath("tmp_llm_flow.ibci")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(code).strip() + "\n")
            
        try:
            # 准备解释器但手动设置回调
            engine._prepare_interpreter(output_callback=output_callback)
            # 配置 ai 模块
            ai = engine.interpreter.service_context.interop.get_package("ai")
            ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
            engine.interpreter.llm_executor.llm_callback = mock_llm
            
            ast_cache = engine.scheduler.compile_project(test_file)
            result = engine.interpreter.interpret(ast_cache[test_file])
            return outputs, result, engine.interpreter
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_llm_except_bubble_up(self):
        code = """
        if ~~is it raining?~~:
            print("rain")
        llmexcept:
            print("uncertain")
        """
        # 1. LLM returns valid "1"
        outputs, _, _ = self.run_code(code, ["1"])
        self.assertEqual(outputs, ["rain"])

        # 2. LLM returns invalid "maybe"
        outputs, _, _ = self.run_code(code, ["maybe"])
        self.assertEqual(outputs, ["uncertain"])

    def test_llm_retry_mechanism(self):
        code = """
        import ai
        int count = 0
        if ~~check something~~:
            print("success")
        llmexcept:
            count = count + 1
            if count < 2:
                ai.set_retry_hint("please be more specific, return 1 or 0")
                retry
            else:
                print("failed after retry")
        """
        # LLM returns "maybe" first, then "1"
        outputs, _, _ = self.run_code(code, ["maybe", "1"])
        self.assertEqual(outputs, ["success"])

        # LLM returns "maybe" twice
        outputs, _, _ = self.run_code(code, ["maybe", "maybe"])
        self.assertEqual(outputs, ["failed after retry"])

    def test_scene_tagging(self):
        code = textwrap.dedent("""
        if ~~condition~~:
            pass
        """).strip() + "\n"
        
        engine = IBCIEngine()
        test_file = os.path.abspath("tmp_scene_test.ibci")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(code)
        
        try:
            ast_cache = engine.scheduler.compile_project(test_file)
            ast_node = ast_cache[test_file]
            
            if_stmt = ast_node.body[0]
            self.assertEqual(if_stmt.test.scene_tag.name, "BRANCH")
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_nested_llm_except(self):
        code = """
        if ~~outer~~:
            if ~~inner~~:
                print("inner success")
            llmexcept:
                print("inner failed")
        llmexcept:
            print("outer failed")
        """
        # Case 1: Outer fails
        outputs, _, _ = self.run_code(code, ["invalid"])
        self.assertEqual(outputs, ["outer failed"])

        # Case 2: Inner fails
        outputs, _, _ = self.run_code(code, ["1", "invalid"])
        self.assertEqual(outputs, ["inner failed"])

    def test_loop_llm_except(self):
        code = """
        for ~~should I continue?~~:
            print("looping")
        llmexcept:
            print("loop error")
        """
        # 1. Fail immediately
        outputs, _, _ = self.run_code(code, ["invalid"])
        self.assertEqual(outputs, ["loop error"])

    def test_while_llm_except(self):
        code = """
        int count = 0
        while ~~should I continue?~~:
            print("looping")
            count = count + 1
            if count > 0:
                # make it fail on second check
                pass 
        llmexcept:
            print("while error")
        """
        # Loop once then fail
        outputs, _, _ = self.run_code(code, ["1", "invalid"])
        self.assertEqual(outputs, ["looping", "while error"])

if __name__ == '__main__':
    unittest.main()
