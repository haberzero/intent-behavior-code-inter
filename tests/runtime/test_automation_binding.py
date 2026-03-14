import unittest
from core.foundation.registry import Registry
from core.runtime.bootstrap.builtin_initializer import initialize_builtin_classes
from core.runtime.objects.kernel import IbObject, IbClass
from core.runtime.objects.builtins import IbList
from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser
from core.compiler.semantic.passes.semantic_analyzer import SemanticAnalyzer
from core.compiler.serialization.serializer import FlatSerializer
from core.runtime.interpreter.interpreter import Interpreter
from core.runtime.loader.artifact_loader import ArtifactLoader
from core.runtime.interpreter.runtime_context import RuntimeContextImpl

class TestAutomationBinding(unittest.TestCase):
    """
    验证自动化绑定与执行 (Phase 3.2)。
    确保公理定义的方法能自动绑定到 Python 实现，且延迟执行逻辑正确。
    """

    def setUp(self):
        # 初始化运行时 Registry
        self.registry = Registry()
        initialize_builtin_classes(self.registry)
        
        # 编译器环境 (用于生成测试产物)
        from core.domain.factory import create_default_registry
        self.comp_registry = create_default_registry()
        self.analyzer = SemanticAnalyzer(registry=self.comp_registry)
        self.serializer = FlatSerializer()

    def test_axiom_method_binding(self):
        """验证 list.append 是否通过公理自动化绑定"""
        list_class = self.registry.get_class("list")
        self.assertIsNotNone(list_class)
        
        # 验证虚表中存在 append
        append_method = list_class.lookup_method("append")
        self.assertIsNotNone(append_method)
        
        # 创建实例并调用
        items = self.registry.box([])
        self.assertIsInstance(items, IbList)
        self.assertEqual(len(items.elements), 0)
        
        # 模拟消息传递调用 append
        val = self.registry.box(42)
        items.receive("append", [val])
        
        self.assertEqual(len(items.elements), 1)
        self.assertEqual(items.elements[0].to_native(), 42)

    def test_deferred_execution_wrapping(self):
        """验证 node_is_deferred 标记的节点在运行时被正确包裹为 IbBehavior"""
        # 编写包含行为描述行的代码
        code = '''
var x = @~ compute something ~
'''
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        module = parser.parse()
        
        # 编译器分析：行为描述行应该被标记为 deferred (如果它是表达式的话)
        result = self.analyzer.analyze(module)
        
        # 序列化并加载到解释器
        flat_data = self.serializer.serialize_result(result)
        
        # 找到行为描述行节点 UID
        behavior_node_uid = None
        for uid, node in flat_data["pools"]["nodes"].items():
            if node.get("_type") == "IbBehaviorExpr":
                behavior_node_uid = uid
                break
        self.assertIsNotNone(behavior_node_uid)
        
        # 验证编译器确实标记了延迟执行
        self.assertTrue(flat_data["side_tables"]["node_is_deferred"].get(behavior_node_uid, False))
        
        artifact = {
            "pools": flat_data["pools"],
            "entry_module": "main",
            "modules": {"main": {"root_node_uid": flat_data["root_node_uid"], "side_tables": flat_data["side_tables"]}}
        }
        
        loader = ArtifactLoader(self.registry)
        loaded = loader.load(artifact)
        
        # 创建解释器并执行
        from core.runtime.interpreter.interpreter import Interpreter
        from core.compiler.diagnostics.issue_tracker import IssueTracker
        
        issue_tracker = IssueTracker()
        # [NEW] 必须传入 artifact，因为 Interpreter 内部会调用 Loader
        interpreter = Interpreter(issue_tracker, registry=self.registry, artifact=artifact)
        
        interpreter.current_module_name = "main" # 必须设置模块名以查找侧表
        interpreter.node_pool = flat_data["pools"]["nodes"]
        interpreter.symbol_pool = flat_data["pools"]["symbols"]
        interpreter.type_pool = flat_data["pools"]["types"]
        interpreter.type_hydrator = loaded.type_hydrator
        
        # 注入 side tables
        interpreter._side_tables = flat_data["side_tables"]
        
        # 设置 context
        context = RuntimeContextImpl(registry=self.registry)
        interpreter.context = context
        
        # 执行赋值语句
        # module -> assign -> IbBehaviorExpr
        assign_uid = next(uid for uid, n in interpreter.node_pool.items() if n["_type"] == "IbAssign")
        res = interpreter.visit(assign_uid)
        
        # 验证变量 x 的值是一个 IbBehavior 对象
        x_val = context.get_variable("x")
        from core.runtime.objects.builtins import IbBehavior
        self.assertIsInstance(x_val, IbBehavior)
        self.assertEqual(x_val.node, behavior_node_uid)

if __name__ == "__main__":
    unittest.main()
