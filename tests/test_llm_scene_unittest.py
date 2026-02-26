import unittest
import sys
import os
import textwrap

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.types import parser_types as ast
from core.types.diagnostic_types import CompilerError
from core.engine import IBCIEngine

class TestLLMScenePropagation(unittest.TestCase):
    def test_complex_condition_propagation(self):
        code = textwrap.dedent("""
        if ~~a~~ and (~~b~~ or ~~c~~):
            print("success")
        """).strip()
        
        engine = IBCIEngine()
        test_file = os.path.abspath("tmp_propagation_test.ibci")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(code + "\n")
            
        try:
            ast_cache = engine.scheduler.compile_project(test_file)
            module = ast_cache[test_file]
            
            if_stmt = module.body[0]
            self.assertIsInstance(if_stmt, ast.If)
            
            # Helper to find all behavior exprs
            behavior_exprs = []
            def collect(node):
                if isinstance(node, ast.BehaviorExpr):
                    behavior_exprs.append(node)
                for field_name, value in node.__dict__.items():
                    if isinstance(value, ast.ASTNode):
                        collect(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, ast.ASTNode):
                                collect(item)
                                
            collect(if_stmt.test)
            
            self.assertEqual(len(behavior_exprs), 3)
            for expr in behavior_exprs:
                self.assertEqual(expr.scene_tag, ast.Scene.BRANCH, 
                                 f"Behavior expression '{expr.segments}' should have BRANCH scene tag")
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_testonly_branch_logic(self):
        code = textwrap.dedent("""
        import ai
        ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
        if ~~is this true?~~:
            print("YES")
        else:
            print("NO")
        """).strip()
        
        engine = IBCIEngine()
        test_file = os.path.abspath("tmp_branch_logic.ibci")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(code + "\n")
            
        try:
            outputs = []
            def output_callback(msg):
                outputs.append(msg)
                
            success = engine.run(test_file, output_callback=output_callback)
            self.assertTrue(success)
            
            # In TESTONLY mode, BRANCH scene should return "1", triggering the YES branch
            self.assertEqual(outputs, ["YES"])
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

if __name__ == '__main__':
    unittest.main()
