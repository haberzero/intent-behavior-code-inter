import unittest
from tests.interpreter.base import BaseInterpreterTest
from core.domain.issue import InterpreterError, CompilerError

class TestErrorHandling(BaseInterpreterTest):
    """
    测试解释器的错误处理机制：运行时异常捕获与诊断报告。
    """
    def test_type_mismatch_at_runtime(self):
        """测试运行时类型不匹配错误"""
        code = """
        int x = "hello" # 静态编译阶段会报错
        """
        with self.assertRaises(CompilerError) as cm:
            self.run_code(code)
        
        # 校验诊断代码 SEM_003
        error_codes = [d.code for d in cm.exception.diagnostics]
        self.assertIn("SEM_003", error_codes)

    def test_undefined_variable_at_runtime(self):
        """测试静态作用域检查：未定义变量访问"""
        code = """
        print(unknown_var)
        """
        with self.assertRaises(CompilerError) as cm:
            self.run_code(code)
        
        # 校验诊断代码 SEM_001
        error_codes = [d.code for d in cm.exception.diagnostics]
        self.assertIn("SEM_001", error_codes)

    def test_argument_count_mismatch(self):
        """测试参数数量不匹配错误"""
        code = """
        func add(int a, int b) -> int:
            return a + b
        
        add(1) # 少一个参数
        """
        with self.assertRaises(CompilerError) as cm:
            self.run_code(code)
        
        # 校验诊断代码 SEM_005
        error_codes = [d.code for d in cm.exception.diagnostics]
        self.assertIn("SEM_005", error_codes)

    def test_member_not_found(self):
        """测试成员不存在访问错误"""
        code = """
        class Point:
            var x = 0
            
        Point p = Point()
        print(p.z) # z 属性不存在
        """
        with self.assertRaises(CompilerError) as cm:
            self.run_code(code)
            
        # 校验诊断代码 SEM_001
        error_codes = [d.code for d in cm.exception.diagnostics]
        self.assertIn("SEM_001", error_codes)

if __name__ == '__main__':
    unittest.main()
