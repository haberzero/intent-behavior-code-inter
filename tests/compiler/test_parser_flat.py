import unittest
from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser
from core.domain import ast

class TestParserFlattening(unittest.TestCase):
    """
    验证 Parser 的 AST 扁平化成果。
    遵循 VERIFICATION_GUIDE.md 3.1 节。
    """

    def parse_code(self, code: str) -> ast.IbModule:
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        try:
            return parser.parse()
        except Exception as e:
            if hasattr(parser.context.issue_tracker, "_diagnostics"):
                for d in parser.context.issue_tracker._diagnostics:
                    print(f"COMPILER ERROR: {d.message} at {d.location.line}:{d.location.column}")
            raise e

    def test_intent_shorthand_flattening(self):
        """验证 @ "intent" \n stmt 不再产生包装节点"""
        code = '@ "calculate something"\nvar a = 1'
        module = self.parse_code(code)
        
        # 验证主体结构
        self.assertEqual(len(module.body), 1)
        stmt = module.body[0]
        
        # 核心断言：它必须是 IbAssign 而不是 IbAnnotatedStmt (后者已被删除)
        self.assertIsInstance(stmt, ast.IbAssign, "意图简写后的节点应该是原始语句类型")
        
        # 验证意图是否被正确暂存在私有属性中
        self.assertTrue(hasattr(stmt, "_pending_intents"), "意图应该被暂存在节点属性中")
        intents = getattr(stmt, "_pending_intents")
        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0].content, "calculate something")

    def test_nested_intent_block(self):
        """验证 intent 块内部的普通语句不会被自动包装（它们通过 SemanticAnalyzer 处理堆栈）"""
        code = 'intent "main loop":\n    pass\n'
        module = self.parse_code(code)
        
        self.assertEqual(len(module.body), 1)
        intent_stmt = module.body[0]
        self.assertIsInstance(intent_stmt, ast.IbIntentStmt)
        
        # 验证内部语句是纯净的 IbPass
        inner_stmt = intent_stmt.body[0]
        self.assertIsInstance(inner_stmt, ast.IbPass)
        self.assertFalse(hasattr(inner_stmt, "_pending_intents"), "块内部语句在解析阶段不应持有私有属性意图")

if __name__ == '__main__':
    unittest.main()
