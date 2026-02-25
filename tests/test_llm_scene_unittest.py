import unittest
import sys
import os
import textwrap

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from utils.interpreter.interpreter import Interpreter
from utils.diagnostics.issue_tracker import IssueTracker
from typedef import parser_types as ast

from typedef.diagnostic_types import CompilerError

class TestLLMScenePropagation(unittest.TestCase):
    def test_complex_condition_propagation(self):
        code = textwrap.dedent("""
        if ~~a~~ and (~~b~~ or ~~c~~):
            print("success")
        """).strip()
        issue_tracker = IssueTracker()
        lexer = Lexer(code + "\n")
        tokens = lexer.tokenize()
        parser = Parser(tokens, issue_tracker)
        try:
            module = parser.parse()
        except CompilerError as e:
            for d in e.diagnostics:
                print(f"ERROR: {d.message} at {d.location}")
            raise e
        
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

    def test_testonly_branch_logic(self):
        code = textwrap.dedent("""
        import ai
        ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
        if ~~is this true?~~:
            print("YES")
        else:
            print("NO")
        """).strip()
        issue_tracker = IssueTracker()
        lexer = Lexer(code + "\n")
        tokens = lexer.tokenize()
        parser = Parser(tokens, issue_tracker)
        try:
            module = parser.parse()
        except CompilerError as e:
            for d in e.diagnostics:
                print(f"ERROR: {d.message} at {d.location}")
            raise e
        
        outputs = []
        def output_callback(msg):
            outputs.append(msg)
            
        interpreter = Interpreter(issue_tracker, output_callback=output_callback)
        interpreter.interpret(module)
        
        # In TESTONLY mode, BRANCH scene should return "1", triggering the YES branch
        self.assertEqual(outputs, ["YES"])

if __name__ == '__main__':
    unittest.main()
