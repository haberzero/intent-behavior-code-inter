import unittest
import os
import sys
from core.engine import IBCIEngine

class DocValidator(unittest.TestCase):
    def setUp(self):
        self.engine = IBCIEngine()

    def assert_compile(self, code, label):
        filename = f"tmp_doc_test_{label}.ibci"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            self.engine.compile(os.path.abspath(filename))
            print(f"[LOG] {label}: Compilation PASSED")
        except Exception as e:
            print(f"[LOG] {label}: Compilation FAILED")
            if hasattr(self.engine, "issue_tracker"):
                for diag in self.engine.issue_tracker.diagnostics:
                    print(f"  - [{diag.severity.name}] {diag.code}: {diag.message}")
            self.fail(f"Documentation example '{label}' failed to compile.")
        finally:
            if os.path.exists(filename):
                os.remove(filename)

    def test_syntax_examples(self):
        # 1. 行为描述行与 Lambda
        self.assert_compile("""
str text = "hello"
var score = @~ 分析 $text ~
callable check = @~ 验证数据 ~
""", "lambda_behavior")

        # 2. 意图驱动分支与 retry
        self.assert_compile("""
if @~ 是否包含负面情绪 ~:
    print("Negative")
llmexcept:
    retry
""", "intent_branch")

        # 3. 条件驱动循环
        self.assert_compile("""
for @~ 还有待处理的任务吗 ~:
    print("Working")
""", "intent_loop")

        # 4. 类系统与 __to_prompt__
        self.assert_compile("""
class User:
    str name = "Alice"
    func __to_prompt__() -> str:
        return self.name

User u = User()
@~ 你好 $u ~
""", "class_system")

        # 5. 意图叠加与修饰符
        self.assert_compile("""
@! 严格鲁迅文风
@~ 描述夜晚 ~
""", "intent_modifier")

if __name__ == "__main__":
    unittest.main()
