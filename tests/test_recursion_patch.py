import unittest
import sys
from core.engine import IBCIEngine
from core.runtime.interpreter.interpreter import Interpreter

class TestRecursionPatch(unittest.TestCase):
    def test_recursion_limit_patch(self):
        # 模拟设置一个不安全的 max_call_stack (比如 1000, 4000 > 1000)
        engine = IBCIEngine()
        # 强制设置一个很高的 limit
        interpreter = Interpreter(engine.issue_tracker, max_call_stack=2000)
        
        # 校验是否被修正
        python_limit = sys.getrecursionlimit()
        safe_limit = (python_limit - 100) // 4
        self.assertEqual(interpreter.max_call_stack, safe_limit)
        print(f"Recursion patch test passed. max_call_stack adjusted to {safe_limit}")

if __name__ == "__main__":
    unittest.main()
