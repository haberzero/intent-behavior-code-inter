import unittest
import os
from core.engine import IBCIEngine
from core.runtime.objects.kernel import IbObject
from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser

class TestIntentInterpolation(unittest.TestCase):
    def setUp(self):
        # Ensure we are in the project root
        self.engine = IBCIEngine(root_dir=os.getcwd())

    def run_code(self, code: str, silent=False):
        # 创建临时文件 (确保在项目根目录下，以通过安全检查)
        import tempfile
        import textwrap
        code = textwrap.dedent(code).strip() + "\n"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ib', delete=False, dir=os.getcwd(), encoding='utf-8') as f:
            f.write(code)
            temp_path = f.name
        
        try:
            # 编译并运行
            from core.domain.issue import CompilerError
            try:
                artifact = self.engine.compile(temp_path)
            except CompilerError as e:
                if not silent:
                    from core.compiler.diagnostics.formatter import DiagnosticFormatter
                    print(f"\n[DIAGNOSTICS for code:\n{code}]\n" + 
                          DiagnosticFormatter.format_all(e.diagnostics, source_manager=self.engine.scheduler.source_manager))
                raise e
            
            # 拦截 LLM 调用以查看生成的 Prompt
            captured = []
            
            def mock_llm_call(sys_prompt, user_prompt, node_uid, **kwargs):
                captured.append({"sys": sys_prompt, "user": user_prompt})
                return "mocked response"
            
            from core.compiler.serialization.serializer import FlatSerializer
            serializer = FlatSerializer()
            artifact_dict = serializer.serialize_artifact(artifact)
            self.engine._prepare_interpreter(artifact_dict)
            
            self.engine.interpreter.service_context.llm_executor._call_llm = mock_llm_call
            self.engine.interpreter.run()
            return captured
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_syntax_variants(self):
        """测试不同语法形式下的插值意图，以定位解析器 Bug"""
        
        # 变体 1: 简写形式 @ $x
        self.run_code("""
        int x = 10
        @ $x
        str res = @~ hello ~
        """)

        # 变体 2: 显式 intent 块 (对比简写形式)
        self.run_code("""
        int x = 10
        intent $x:
            str res = @~ hello ~
        """)

        # 变体 3: 带引号的简写
        captured = self.run_code("""
        @ "Static Intent"
        str res = @~ hello ~
        """)
        self.assertIn("Static Intent", captured[0]['sys'])

    def test_basic_interpolation(self):
        """测试基础变量插值 @ $x"""
        code = """
        int x = 10
        @ $x
        str res = @~ say hello ~
        """
        captured = self.run_code(code)
        self.assertTrue(len(captured) > 0)
        sys_prompt = captured[0]["sys"]
        self.assertIn("10", sys_prompt)

    def test_complex_interpolation(self):
        """测试复杂路径插值 @ $u.name"""
        code = """
        class User:
            str name
        
        User u = User()
        u.name = "Alice"
        @ "Hello, "$u.name
        str res = @~ greeting ~
        """
        captured = self.run_code(code)
        self.assertTrue(len(captured) > 0)
        sys_prompt = captured[0]["sys"]
        self.assertIn("Hello, Alice", sys_prompt)

if __name__ == "__main__":
    unittest.main()
