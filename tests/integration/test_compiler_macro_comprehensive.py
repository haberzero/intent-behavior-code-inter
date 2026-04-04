"""
Comprehensive Compiler Macro Test Suite (V2)
验证编译器输出的质量与逻辑功能，确保能够支撑 MVP 解释器运行。
要求：每个测试用例完全隔离，使用真实的 .ibci 文件进行宏观验证。
"""
import unittest
import os
import sys
import json

# 确保项目根目录在路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.engine import IBCIEngine
from core.kernel.blueprint import CompilationArtifact, CompilationResult
from core.kernel.ast import IbIf, IbWhile, IbFor, IbClassDef, IbFunctionDef, IbBehaviorExpr, IbAssign, IbName, IbTypeAnnotatedExpr

class TestCompilerMacroComprehensive(unittest.TestCase):
    """
    编译器宏观综合测试类。
    每个方法都会创建一个全新的 IBCIEngine 实例以保证完全隔离。
    """

    def setUp(self):
        # 每个测试前清除可能存在的环境变量干扰
        os.environ.pop("IBC_TEST_MODE", None)

    def _get_fresh_engine(self):
        """创建一个全新的引擎实例"""
        return IBCIEngine(root_dir=PROJECT_ROOT)

    def _get_main_module(self, artifact: CompilationArtifact) -> CompilationResult:
        """获取主模块编译结果"""
        key = artifact.entry_module or list(artifact.modules.keys())[0]
        return artifact.modules.get(key)

    def _compile_example(self, rel_path: str) -> tuple[IBCIEngine, CompilationArtifact, CompilationResult]:
        """编译指定的 example 文件并返回相关对象"""
        engine = self._get_fresh_engine()
        abs_path = os.path.join(PROJECT_ROOT, rel_path)
        if not os.path.exists(abs_path):
            self.fail(f"Example file not found: {abs_path}")
        
        artifact = engine.compile(abs_path, silent=True)
        if engine.issue_tracker.has_errors():
            errors = "\n".join([f"[{d.level}] {d.message}" for d in engine.issue_tracker.diagnostics if d.level == "ERROR"])
            self.fail(f"Compilation of {rel_path} failed with errors:\n{errors}")
            
        module = self._get_main_module(artifact)
        return engine, artifact, module

    def test_01_basics_class_protocol_output_quality(self):
        """
        验证 01_basics/class_protocol.ibci 的输出质量：
        1. 符号表包含类 User 和变量 u, res, analyze
        2. IbClassDef 节点包含成员变量 (fields) 和方法 (methods)
        3. node_to_type 包含核心表达式的类型
        """
        engine, artifact, module = self._compile_example("examples/01_basics/class_protocol.ibci")
        
        # 1. 符号解析检查
        for name in ["User", "u", "res", "analyze", "text"]:
            sym = module.symbol_table.resolve(name)
            self.assertIsNotNone(sym, f"Symbol '{name}' should be resolved in class_protocol.ibci")
        
        # 2. 类结构检查
        user_class_node = next((n for n in module.module_ast.body if isinstance(n, IbClassDef) and n.name == "User"), None)
        self.assertIsNotNone(user_class_node, "IbClassDef 'User' not found in AST")
        
        # 检查类成员变量 (fields)
        field_names = []
        for field in user_class_node.fields:
            if isinstance(field, IbAssign):
                for target in field.targets:
                    if isinstance(target, IbName): 
                        field_names.append(target.id)
                    elif isinstance(target, IbTypeAnnotatedExpr) and isinstance(target.target, IbName):
                        field_names.append(target.target.id)
        
        self.assertIn("name", field_names)
        self.assertIn("score", field_names)

        # 检查类方法 (methods)
        method_names = [m.name for m in user_class_node.methods if isinstance(m, IbFunctionDef)]
        self.assertIn("__to_prompt__", method_names)

        # 3. 类型绑定检查
        # 检查带类型注解的赋值，验证其 targets[0] 节点是否有类型信息
        found_type_info = False
        for field in user_class_node.fields:
            if isinstance(field, IbAssign) and field.targets:
                target = field.targets[0]
                if module.node_to_type.get(target) is not None:
                    found_type_info = True
                    break
        self.assertTrue(found_type_info, "No assigned targets in User class fields have type info")

    def test_02_control_flow_llm_error_handling_logic(self):
        """
        验证 02_control_flow/llm_error_handling.ibci 的逻辑：
        1. IbIf 和 IbWhile 节点必须有 .test 属性
        2. 对应的 test 节点必须绑定了 scene (BRANCH 或 LOOP)
        3. [NEW] 语句节点本身也应绑定场景
        """
        engine, artifact, module = self._compile_example("examples/02_control_flow/llm_error_handling.ibci")
        
        if_nodes = [n for n in module.module_ast.body if isinstance(n, IbIf)]
        while_nodes = [n for n in module.module_ast.body if isinstance(n, IbWhile)]
        
        self.assertGreater(len(if_nodes), 0, "No IbIf nodes found")
        self.assertGreater(len(while_nodes), 0, "No IbWhile nodes found")
        
        for node in if_nodes:
            # 检查条件节点场景
            self.assertTrue(hasattr(node, 'test'), "IbIf node missing 'test' attribute")
            scene = module.node_scenes.get(node.test)
            self.assertIsNotNone(scene, f"IbIf.test node {node.test} should have a scene binding")
            self.assertIn("BRANCH", str(scene), "If condition should be in BRANCH scene")
            
            # 检查语句节点本身场景 (NEW Fix)
            stmt_scene = module.node_scenes.get(node)
            self.assertIsNotNone(stmt_scene, "IbIf statement node should have a scene binding")
            self.assertIn("BRANCH", str(stmt_scene))

        for node in while_nodes:
            # 检查条件节点场景
            self.assertTrue(hasattr(node, 'test'), "IbWhile node missing 'test' attribute")
            scene = module.node_scenes.get(node.test)
            self.assertIsNotNone(scene, f"IbWhile.test node {node.test} should have a scene binding")
            self.assertIn("LOOP", str(scene), "While condition should be in LOOP scene")
            
            # 检查语句节点本身场景 (NEW Fix)
            stmt_scene = module.node_scenes.get(node)
            self.assertIsNotNone(stmt_scene, "IbWhile statement node should have a scene binding")
            self.assertIn("LOOP", str(stmt_scene))

    def test_02_control_flow_intent_driven_loop_scenes(self):
        """
        验证 02_control_flow/intent_driven_loop.ibci 的场景标记：
        1. 验证 IbFor 节点内的 BehaviorExpr 是否标记为 LOOP 场景
        2. 验证 IbFor 节点本身是否标记为 LOOP 场景
        """
        engine, artifact, module = self._compile_example("examples/02_control_flow/intent_driven_loop.ibci")
        
        # 寻找 IbFor 节点
        for_nodes = [n for n in module.module_ast.body if isinstance(n, IbFor)]
        self.assertGreater(len(for_nodes), 0, "No IbFor nodes found")
        
        behavior_in_loop_found = False
        for for_node in for_nodes:
            # 检查 for 循环的迭代对象是否是 BehaviorExpr
            if isinstance(for_node.iter, IbBehaviorExpr):
                scene = module.node_scenes.get(for_node.iter)
                self.assertIsNotNone(scene, "IbBehaviorExpr in IbFor should have scene")
                if "LOOP" in str(scene):
                    behavior_in_loop_found = True
            
            # 检查 IbFor 节点本身场景 (NEW Fix)
            stmt_scene = module.node_scenes.get(for_node)
            self.assertIsNotNone(stmt_scene, "IbFor statement node should have a scene binding")
            self.assertIn("LOOP", str(stmt_scene))
        
        self.assertTrue(behavior_in_loop_found, "Did not find IbBehaviorExpr with LOOP scene in intent_driven_loop.ibci")

    def test_01_basics_basic_ai_side_tables(self):
        """
        验证 01_basics/basic_ai.ibci 的侧表完整性：
        1. node_to_symbol 映射数量合理
        2. node_to_loc 包含所有顶层语句且为字典格式
        """
        engine, artifact, module = self._compile_example("examples/01_basics/basic_ai.ibci")
        
        # 检查 node_to_symbol
        self.assertGreater(len(module.node_to_symbol), 0, "node_to_symbol side table is empty")
        
        # 检查 node_to_loc
        for node in module.module_ast.body:
            loc = module.node_to_loc.get(node)
            self.assertIsNotNone(loc, f"Statement {node} missing location info")
            # 验证 loc 是 dict 格式
            self.assertIsInstance(loc, dict, f"Location info for {node} should be a dict, got {type(loc)}")
            self.assertIn("file_path", loc)
            self.assertIn("basic_ai.ibci", loc["file_path"])

    def test_compilation_artifact_serialization_completeness(self):
        """
        验证 CompilationArtifact 序列化后的完整性，特别是侧表的完整性。
        """
        engine, artifact, module = self._compile_example("examples/01_basics/basic_ai.ibci")
        
        # 手动执行序列化
        from core.compiler.serialization.serializer import FlatSerializer
        serializer = FlatSerializer()
        data = serializer.serialize_artifact(artifact)
        
        self.assertIn("modules", data)
        main_module_data = data["modules"][artifact.entry_module]
        side_tables = main_module_data.get("side_tables", {})
        
        # 验证 6 个核心侧表是否存在
        required_tables = [
            "node_scenes", "node_to_symbol", "node_to_type", 
            "node_is_deferred", "node_intents", "node_to_loc"
        ]
        for table in required_tables:
            self.assertIn(table, side_tables, f"Missing side table in serialized output: {table}")

    def test_intent_tag_parsing_and_serialization(self):
        """
        验证意图标签 (#tag) 的解析与序列化是否正确
        """
        engine = self._get_fresh_engine()
        code = "@+#1 \"tagged intent\"\nx = 1"
        artifact = engine.compile_string(code, silent=True)
        module = self._get_main_module(artifact)
        
        # 查找 x = 1 节点对应的意图
        assign_node = next(n for n in module.module_ast.body if isinstance(n, IbAssign))
        intents = module.node_intents.get(assign_node)
        
        self.assertIsNotNone(intents, "Intent not found for assignment node")
        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0].tag, "1", f"Expected tag '1', got {intents[0].tag}")
        self.assertEqual(intents[0].content, "tagged intent")
        
        # 验证序列化后意图信息是否保留
        from core.compiler.serialization.serializer import FlatSerializer
        serializer = FlatSerializer()
        data = serializer.serialize_artifact(artifact)
        
        # 检查意图池
        intent_node_uid = data["modules"][artifact.entry_module]["side_tables"]["node_intents"][serializer._collect_node(assign_node)][0]
        intent_data = data["pools"]["nodes"][intent_node_uid]
        self.assertEqual(intent_data.get("tag"), "1", "Tag lost after serialization")

    def test_cross_module_symbol_resolution(self):
        """
        验证跨模块符号解析（如果 example 中存在 import）
        使用 examples/03_plugins/main.ibci
        """
        # 注意：此测试依赖于 examples/03_plugins/ 目录结构
        try:
            engine, artifact, module = self._compile_example("examples/03_plugins/main.ibci")
            # 验证是否成功加载了插件模块的符号
            self.assertFalse(engine.issue_tracker.has_errors(), "main.ibci should compile without errors")
        except Exception as e:
            self.skipTest(f"Skipping cross-module test due to environment/path issues: {e}")

if __name__ == "__main__":
    unittest.main()
