
import unittest
import textwrap
from core.compiler.parser.parser import Parser
from core.compiler.lexer.lexer import Lexer
from core.compiler.semantic.semantic_analyzer import SemanticAnalyzer
from core.compiler.semantic.types import UserDefinedType
from core.types import parser_types as ast
from core.support.diagnostics.issue_tracker import IssueTracker

class TestSemanticAnalysis(unittest.TestCase):
    def setUp(self):
        self.issue_tracker = IssueTracker()
        self.analyzer = SemanticAnalyzer(self.issue_tracker)

    def parse_and_analyze(self, code):
        code = textwrap.dedent(code).strip() + "\n"
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        
        parser = Parser(tokens, self.issue_tracker)
        try:
            module = parser.parse()
        except Exception as e:
            if hasattr(e, 'diagnostics'):
                for d in e.diagnostics:
                    print(f"Parser Error: {d.message} at line {d.location.line}")
            raise e
        
        # Don't raise here if we want to assert on errors
        try:
            self.analyzer.analyze(module)
        except Exception as e:
            if hasattr(e, 'diagnostics'):
                for d in e.diagnostics:
                    print(f"Semantic Error: {d.message} at line {d.location.line}")
            else:
                print(f"Analyzer Exception: {e}")
            # Semantic analyzer might raise if issue_tracker.check_errors() is called at the end
            pass
            
        return module

    def test_inheritance_valid(self):
        code = """
        class Animal:
            func speak():
                pass
        
        class Dog(Animal):
            func bark():
                pass
        """
        self.parse_and_analyze(code)
        self.assertFalse(self.issue_tracker.has_errors())
        
        # Verify types
        dog_sym = self.analyzer.scope_manager.resolve("Dog")
        self.assertIsInstance(dog_sym.type_info, UserDefinedType)
        self.assertEqual(dog_sym.type_info.parent.class_name, "Animal")

    def test_inheritance_invalid_missing_base(self):
        code = """
        class Dog(UnknownAnimal):
            func bark():
                pass
        """
        self.parse_and_analyze(code)
        self.assertTrue(self.issue_tracker.has_errors())
        self.assertIn("Base class 'UnknownAnimal' is not defined", self.issue_tracker.diagnostics[0].message)

    def test_inheritance_invalid_not_a_class(self):
        code = """
        int x = 1
        class Dog(x):
            func bark():
                pass
        """
        self.parse_and_analyze(code)
        self.assertTrue(self.issue_tracker.has_errors())
        self.assertIn("Base class 'x' must be a defined class", self.issue_tracker.diagnostics[0].message)

    def test_type_assignment_compatibility(self):
        code = """
        class Animal:
            pass
        class Dog(Animal):
            pass
        class Cat(Animal):
            pass
        
        Animal a = Dog()
        Animal b = Cat()
        Dog d = Dog()
        
        # Invalid
        Dog e = Cat()
        """
        self.parse_and_analyze(code)
        errors = self.issue_tracker.diagnostics
        self.assertTrue(len(errors) > 0)
        self.assertIn("Type mismatch", errors[0].message)
        self.assertIn("Cat", errors[0].message)
        self.assertIn("Dog", errors[0].message)

if __name__ == "__main__":
    unittest.main()
