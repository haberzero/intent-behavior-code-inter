
import unittest
import os
import tempfile
import shutil
from core.engine import IBCIEngine
from core.domain.issue import InterpreterError

class TestInterpreterModule(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.engine = IBCIEngine(root_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _write_file(self, name, content):
        path = os.path.join(self.test_dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # 确保以换行符结尾，满足 Parser 严格要求
        if not content.endswith("\n"):
            content += "\n"
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def test_circular_import(self):
        """测试循环引用：a -> b, b -> a"""
        self._write_file("a.ibci", "import b\nvar val_a = 1\nfunc get_b_val() -> int:\n    return b.val_b\n")
        self._write_file("b.ibci", "import a\nvar val_b = 2\nfunc get_a_val() -> int:\n    return a.val_a\n")
        
        main_code = """
import a
import b
print(a.get_b_val())
print(b.get_a_val())
"""
        outputs = []
        self.engine.run_string(main_code, output_callback=lambda x: outputs.append(str(x)))
        
        self.assertIn("2", outputs)
        self.assertIn("1", outputs)

    def test_scope_isolation(self):
        """测试作用域隔离：模块 A 的变量不应该泄露到模块 B"""
        self._write_file("mod_a.ibci", "var secret = 100\n")
        self._write_file("mod_b.ibci", "import mod_a\nfunc check() -> int:\n    return secret\n") # 错误：不应该能直接访问 secret
        
        main_code = """
import mod_b
print(mod_b.check())
"""
        # 在新架构中，这种未定义变量的访问会在编译阶段被拦截 (Semantic Analysis)
        # 我们通过 silent=True 让 Engine 抛出原始异常
        from core.domain.issue import CompilerError, InterpreterError
        with self.assertRaises((InterpreterError, CompilerError)) as cm:
            self.engine.run_string(main_code, silent=True)
        
        if isinstance(cm.exception, InterpreterError):
            error_msg = str(cm.exception)
        else:
            # CompilerError: 检查所有诊断信息
            error_msg = " ".join([d.message for d in cm.exception.diagnostics])
        
        self.assertIn("secret", error_msg)

    def test_import_as_alias(self):
        """测试 import as 别名"""
        self._write_file("math_tool.ibci", "func add(int a, int b) -> int:\n    return a + b\n")
        
        main_code = """
import math_tool as mt
print(mt.add(10, 20))
"""
        outputs = []
        self.engine.run_string(main_code, output_callback=lambda x: outputs.append(str(x)))
        self.assertIn("30", outputs)

    def test_from_import_star(self):
        """测试 from mod import *"""
        self._write_file("utils.ibci", "var x = 1\nvar y = 2\nfunc f() -> int:\n    return 3\n")
        
        main_code = """
from utils import *
print(x)
print(y)
print(f())
"""
        outputs = []
        self.engine.run_string(main_code, output_callback=lambda x: outputs.append(str(x)))
        self.assertIn("1", outputs)
        self.assertIn("2", outputs)
        self.assertIn("3", outputs)

if __name__ == '__main__':
    unittest.main()
