import unittest
import textwrap
import io
from contextlib import redirect_stdout
from core.engine import IBCIEngine
from tests.ibc_test_case import IBCTestCase

class TestCoreDebugger(IBCTestCase):
    def test_core_debug_output(self):
        # Configure core debugger via engine
        config = {
            "GENERAL": "BASIC",
            "LEXER": "BASIC",
            "PARSER": "BASIC",
            "SEMANTIC": "BASIC",
            "INTERPRETER": "DETAIL",
            "LLM": "DATA"
        }
        
        code = textwrap.dedent("""
            import ai
            ai.set_config("TESTONLY", "test", "test")
            int a = 1 + 2
            print(a)
            @ "Think about the number"
            @~ 返回 $a ~
        """)
        
        # Capture stdout to verify debug prints
        f = io.StringIO()
        with redirect_stdout(f):
            # Use create_engine to ensure clean state and correct config
            self.core_debug_config = config
            engine = self.create_engine()
            success = engine.run_string(code)
        
        output = f.getvalue()
        
        # Verify presence of debug tags
        self.assertTrue(success)
        self.assertIn("[CORE_DBG][GENERAL][BASIC]", output)
        self.assertIn("[CORE_DBG][LEXER][BASIC]", output)
        self.assertIn("[CORE_DBG][PARSER][BASIC]", output)
        self.assertIn("[CORE_DBG][SEMANTIC][BASIC]", output)
        self.assertIn("[CORE_DBG][INTERPRETER][DETAIL]", output)
        self.assertIn("[CORE_DBG][LLM][BASIC]", output)
        self.assertIn("[CORE_DBG][LLM][DATA]", output)
        
        # Verify specific content
        self.assertIn("Starting tokenization...", output)
        self.assertIn("Starting parsing...", output)
        self.assertIn("Starting semantic analysis...", output)
        self.assertIn("Starting execution...", output)
        self.assertIn("Calling LLM", output)
        self.assertIn("System Prompt:", output)

    def test_core_debug_disabled(self):
        # Ensure environment doesn't interfere with this test
        import os
        old_env = os.environ.get("IBC_TEST_CORE_DEBUG")
        if old_env:
            del os.environ["IBC_TEST_CORE_DEBUG"]
        
        try:
            # No config passed
            self.core_debug_config = None
            engine = self.create_engine()
            
            code = "print(1)"
            
            f = io.StringIO()
            with redirect_stdout(f):
                engine.run_string(code)
            
            output = f.getvalue()
            
            # Should only contain the print output, no debug tags
            self.assertNotIn("[CORE_DBG]", output)
            self.assertEqual(output.strip(), "1")
        finally:
            if old_env:
                os.environ["IBC_TEST_CORE_DEBUG"] = old_env

if __name__ == "__main__":
    unittest.main()
