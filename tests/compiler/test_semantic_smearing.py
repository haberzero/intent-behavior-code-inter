import unittest
from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser
from core.compiler.semantic.passes.semantic_analyzer import SemanticAnalyzer
from core.domain.factory import create_default_registry
from core.domain import ast
from core.domain.types.descriptors import INT_DESCRIPTOR, TypeDescriptor

class TestSemanticSmearing(unittest.TestCase):
    """
    验证 SemanticAnalyzer 的意图涂抹 (Smearing) 和侧表纯净度。
    遵循 VERIFICATION_GUIDE.md 3.2 节。
    """

    def setUp(self):
        from core.engine import IBCIEngine
        self.engine = IBCIEngine(root_dir=".")
        self.registry = self.engine.registry.get_metadata_registry()

    def analyze_code(self, code: str):
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        self.engine.issue_tracker = parser.context.issue_tracker
        try:
            module = parser.parse()
            
            # [Fix] 使用 Engine 提供的分段语义分析标准接口
            self.analyzer = self.engine.resolve_semantics(module)
            
            return module
        except Exception as e:
            raise e

    def test_intent_smearing_side_table(self):
        """验证意图信息被正确“涂抹”到侧表中"""
        code = '@ "outer intent"\nintent "inner block":\n    @ "deep intent"\n    var a = 1\n'
        module = self.analyze_code(code)
        
        # 找到 'var a = 1' 节点
        # IbModule -> [IbIntentStmt] -> [IbAssign]
        intent_stmt = module.body[0]
        assign_stmt = intent_stmt.body[0]
        self.assertIsInstance(assign_stmt, ast.IbAssign)
        
        # 验证侧表记录
        self.assertIn(assign_stmt, self.analyzer.node_intents)
        intents = self.analyzer.node_intents[assign_stmt]
        
        # 应该只包含直接关联的 "deep intent"
        contents = [i.content for i in intents]
        self.assertEqual(len(contents), 1, f"Expected 1 intent, but got: {contents}")
        self.assertIn("deep intent", contents)

    def test_side_table_type_purity(self):
        """验证类型推导侧表存储的是对象引用，而非字符串"""
        code = 'var x = 100\n'
        module = self.analyze_code(code)
        
        # 找到 IbConstant(100) 节点
        # IbModule -> [IbAssign] -> targets, value
        assign = module.body[0]
        const_node = assign.value
        self.assertIsInstance(const_node, ast.IbConstant)
        
        # 验证侧表内容
        self.assertIn(const_node, self.analyzer.node_to_type)
        inferred_type = self.analyzer.node_to_type[const_node]
        
        # 核心断言：必须是对象标识
        self.assertIsInstance(inferred_type, TypeDescriptor)
        # 从注册表获取预期的描述符
        expected_int = self.registry.resolve("int")
        self.assertIs(inferred_type, expected_int, "侧表必须存储 INT_DESCRIPTOR 唯一原型")

    def test_dynamic_proxy_metadata(self):
        """验证 Any/var 类型的成员访问能正确产生虚拟符号"""
        code = 'var d: Any = {}\nvar val = d.some_random_field\n'
        module = self.analyze_code(code)
        
        # 找到 IbAttribute (d.some_random_field) 节点
        # IbModule -> [IbAssign, IbAssign]
        attr_assign = self.analyzer.symbol_table.get_global_scope().symbols['val'].def_node
        attr_node = attr_assign.value
        self.assertIsInstance(attr_node, ast.IbAttribute)
        
        # 验证生成的符号
        self.assertIn(attr_node, self.analyzer.node_to_symbol)
        sym = self.analyzer.node_to_symbol[attr_node]
        
        self.assertTrue(sym.metadata.get("is_dynamic_proxy"), "动态类型的成员访问应标记为 is_dynamic_proxy")

if __name__ == '__main__':
    unittest.main()
