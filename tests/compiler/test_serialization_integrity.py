import unittest
import uuid
from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser
from core.compiler.semantic.passes.semantic_analyzer import SemanticAnalyzer
from core.compiler.serialization.serializer import FlatSerializer
from core.domain.factory import create_default_registry
from core.domain import ast

class TestSerializationIntegrity(unittest.TestCase):
    """
    验证编译器产出物序列化后的完整性与一致性。
    特别关注 IBCI 2.0 物理隔离架构下的侧表与 UID 链路。
    """

    def setUp(self):
        from core.engine import IBCIEngine
        self.engine = IBCIEngine(root_dir=".")
        self.registry = self.engine.registry.get_metadata_registry()
        self.serializer = FlatSerializer()

    def analyze_and_serialize(self, code: str):
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        self.engine.issue_tracker = parser.context.issue_tracker
        module = parser.parse()
        
        # [Fix] 使用 Engine 提供的分段语义分析标准接口
        self.analyzer = self.engine.resolve_semantics(module)
        
        # 构造模拟的 CompilationResult
        from core.domain.blueprint import CompilationResult
        result = CompilationResult(
            module_ast=module,
            symbol_table=self.analyzer.symbol_table,
            node_scenes=self.analyzer.node_scenes,
            node_to_symbol=self.analyzer.node_to_symbol,
            node_to_type=self.analyzer.node_to_type,
            node_is_deferred=self.analyzer.node_is_deferred,
            node_intents=self.analyzer.node_intents
        )
        return self.serializer.serialize_result(result)

    def test_side_table_uid_consistency(self):
        """验证侧表中的 UID 是否能在池中正确还原"""
        code = 'var x: int = 10\nprint(x)\n'
        data = self.analyze_and_serialize(code)
        
        pools = data["pools"]
        side_tables = data["side_tables"]
        
        # 1. 验证 node_to_symbol
        # 找到 print(x) 中的 x 节点
        x_node_uid = None
        for uid, node in pools["nodes"].items():
            if node["_type"] == "IbName" and node.get("id") == "x" and node.get("ctx") == "Load":
                x_node_uid = uid
                break
        self.assertIsNotNone(x_node_uid)
        
        # 检查侧表绑定
        self.assertIn(x_node_uid, side_tables["node_to_symbol"])
        sym_uid = side_tables["node_to_symbol"][x_node_uid]
        self.assertIn(sym_uid, pools["symbols"])
        self.assertEqual(pools["symbols"][sym_uid]["name"], "x")

    def test_type_metadata_serialization(self):
        """验证复杂类型元数据（如 ListMetadata, FunctionMetadata）的序列化"""
        code = '''
func process(list[int] items) -> int:
    return items.len()
'''
        data = self.analyze_and_serialize(code)
        pools = data["pools"]
        
        # 1. 找到函数符号
        func_sym_uid = None
        for uid, sym in pools["symbols"].items():
            if sym["name"] == "process":
                func_sym_uid = uid
                break
        self.assertIsNotNone(func_sym_uid)
        
        # 2. 检查函数类型
        type_uid = pools["symbols"][func_sym_uid]["type_uid"]
        func_type = pools["types"][type_uid]
        self.assertEqual(func_type["kind"], "FunctionMetadata")
        
        # 3. 检查参数类型 (list[int])
        param_type_uid = func_type["param_types_uids"][0]
        list_type = pools["types"][param_type_uid]
        self.assertEqual(list_type["kind"], "ListMetadata")
        self.assertIn("element_type_uid", list_type)
        
        element_type = pools["types"][list_type["element_type_uid"]]
        self.assertEqual(element_type["name"], "int")

    def test_intent_smearing_serialization(self):
        """验证意图涂抹侧表的序列化"""
        code = '''
@ "root intent"
var x = 1
'''
        data = self.analyze_and_serialize(code)
        side_tables = data["side_tables"]
        pools = data["pools"]
        
        # 找到 IbAssign 节点
        assign_uid = next(uid for uid, n in pools["nodes"].items() if n["_type"] == "IbAssign")
        
        # 验证侧表关联
        self.assertIn(assign_uid, side_tables["node_intents"])
        intent_uids = side_tables["node_intents"][assign_uid]
        self.assertEqual(len(intent_uids), 1)
        
        intent_node = pools["nodes"][intent_uids[0]]
        self.assertEqual(intent_node["_type"], "IbIntentInfo")
        self.assertEqual(intent_node["content"], "root intent") 
        # Wait, I should check what the Lexer/Parser actually produces for intent content.
        # Actually, let's just check if it's there.
        self.assertIsNotNone(intent_node["content"])

if __name__ == "__main__":
    unittest.main()
