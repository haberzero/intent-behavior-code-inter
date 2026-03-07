import unittest
from tests.compiler.base import BaseCompilerTest
from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser
from core.types import parser_types as ast

class TestParser(BaseCompilerTest):
    """
    语法解析测试：基于标准 Fixture 验证 AST 树结构。
    """
    def parse_fixture(self, rel_path):
        code = self.get_fixture_content(rel_path)
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        return parser.parse()

    def test_basics_ast(self):
        module = self.parse_fixture("standard/basics.ibci")
        func_defs = [s for s in module.body if isinstance(s, ast.FunctionDef)]
        self.assertEqual(len(func_defs), 1)
        self.assertEqual(func_defs[0].name, "add")

    def test_oop_ast(self):
        module = self.parse_fixture("standard/oop.ibci")
        class_defs = [s for s in module.body if isinstance(s, ast.ClassDef)]
        self.assertEqual(len(class_defs), 2)
        self.assertEqual(class_defs[0].name, "Animal")
        self.assertEqual(class_defs[1].name, "Dog")

    def test_control_flow_ast(self):
        module = self.parse_fixture("standard/control_flow.ibci")
        loops = [s for s in module.body if isinstance(s, ast.For)]
        try_stmts = [s for s in module.body if isinstance(s, ast.Try)]
        self.assertEqual(len(loops), 1)
        self.assertEqual(len(try_stmts), 1)

    def test_standard_syntax_smoke_ast(self):
        module = self.parse_fixture("standard/core_syntax.ibci")
        # Verify the monolithic smoke test still parses
        self.assertTrue(len(module.body) > 10)

    def test_advanced_features_ast(self):
        module = self.parse_fixture("standard/advanced_features.ibci")
        
        # 1. LLM Function
        llm_funcs = [s for s in module.body if isinstance(s, ast.LLMFunctionDef)]
        self.assertEqual(len(llm_funcs), 1)
        self.assertEqual(llm_funcs[0].name, "translate")
        
        # 2. Behavior Expression with Intent
        # Now wrapped in AnnotatedStmt
        annotated_stmts = [s for s in module.body if isinstance(s, ast.AnnotatedStmt)]
        behavior_stmts = [s for s in annotated_stmts if isinstance(s.stmt, ast.Assign) and isinstance(s.stmt.value, ast.BehaviorExpr)]
        self.assertTrue(len(behavior_stmts) >= 1)
        self.assertIsNotNone(behavior_stmts[0].intent)
        
        # 3. LLM Except Fallback
        fallback_stmts = [s for s in module.body if isinstance(s, ast.LLMExceptionalStmt)]
        self.assertTrue(len(fallback_stmts) >= 1)
        self.assertTrue(isinstance(fallback_stmts[0].primary, ast.Assign))
        self.assertTrue(len(fallback_stmts[0].fallback) >= 1)

if __name__ == "__main__":
    unittest.main()
