import unittest
import os
from tests.compiler.base import BaseCompilerTest
from core.compiler.serialization.serializer import FlatSerializer
from core.domain import ast as ast

class TestSerialization(BaseCompilerTest):
    """
    验证编译器产出物（CompilationResult/Artifact）的序列化完整性。
    特别关注 Phase 1/2 重构后的侧表和包装节点。
    """

    def test_basic_serialization_structure(self):
        """验证序列化产物的基本池结构和侧表是否存在"""
        # 使用 standard/basics.ibci 作为测试源
        artifact = self.assert_compile_success("standard/basics.ibci")
        result = self.get_main_result(artifact)
        
        # 执行序列化 (通过 Serializer 而非 Result 对象)
        serializer = FlatSerializer()
        data = serializer.serialize_result(result)
        
        # 1. 检查根节点引用
        self.assertIn("root_node_uid", data)
        self.assertIn("root_scope_uid", data)
        
        # 2. 检查池结构
        pools = data.get("pools", {})
        self.assertIn("nodes", pools)
        self.assertIn("symbols", pools)
        self.assertIn("scopes", pools)
        self.assertIn("types", pools)
        
        # 3. 检查侧表 [NEW in Phase 2.5]
        side_tables = data.get("side_tables", {})
        self.assertIn("node_scenes", side_tables)
        self.assertIn("node_to_symbol", side_tables)
        self.assertIn("node_to_type", side_tables)

    def test_llm_except_serialization(self):
        """验证 LLM Fallback (llmexcept) 是否被正确序列化"""
        source = """
x = 1
llmexcept:
    print("fallback")
"""
        with open("test_llm.ibci", "w", encoding="utf-8") as f:
            f.write(source)
            
        artifact = self.engine.compile(os.path.abspath("test_llm.ibci"))
        result = self.get_main_result(artifact)
        data = FlatSerializer().serialize_result(result)
        nodes = data["pools"]["nodes"]
        
        # 查找带有 llm_fallback 的赋值节点
        assign_nodes = [n for n in nodes.values() if n["_type"] == "IbAssign" and n.get("llm_fallback")]
        self.assertTrue(len(assign_nodes) >= 1, "Should contain assignment node with fallback in pool")
        
        node = assign_nodes[0]
        self.assertIn("llm_fallback", node)
        
        # 验证引用的回退节点也在池中
        self.assertIn(node["llm_fallback"][0], nodes)

    def test_node_intents_side_table(self):
        """验证 Phase 2 意图涂抹逻辑产生的 node_intents 侧表是否被正确序列化"""
        source = """
@ 计算总和
func add(int a, int b) -> int:
    return a + b
"""
        with open("test_intent.ibci", "w", encoding="utf-8") as f:
            f.write(source)
            
        artifact = self.engine.compile(os.path.abspath("test_intent.ibci"))
        result = self.get_main_result(artifact)
        data = FlatSerializer().serialize_result(result)
        
        node_intents = data["side_tables"]["node_intents"]
        nodes = data["pools"]["nodes"]
        
        # 1. 找到函数定义节点
        func_uids = [uid for uid, n in nodes.items() if n["_type"] == "IbFunctionDef" and n.get("name") == "add"]
        self.assertTrue(len(func_uids) >= 1)
        func_uid = func_uids[0]
        
        # 2. 验证侧表中有关联意图
        self.assertIn(func_uid, node_intents)
        intent_uids = node_intents[func_uid]
        self.assertEqual(len(intent_uids), 1)
        
        # 3. 验证意图内容
        intent_node = nodes[intent_uids[0]]
        self.assertEqual(intent_node["_type"], "IbIntentInfo")
        self.assertEqual(intent_node["content"], "计算总和")

    def test_side_table_content_integrity(self):
        """验证侧表中的场景信息 (Scene) 是否被正确记录并序列化"""
        source = """
if True:
    x = 1
while False:
    y = 2
"""
        with open("test_scene.ibci", "w", encoding="utf-8") as f:
            f.write(source)
            
        artifact = self.engine.compile(os.path.abspath("test_scene.ibci"))
        result = self.get_main_result(artifact)
        data = FlatSerializer().serialize_result(result)
        
        node_scenes = data["side_tables"]["node_scenes"]
        nodes = data["pools"]["nodes"]
        
        # 验证 If 分支内的语句是否被标记为 BRANCH 场景
        # 验证 While 循环内的语句是否被标记为 LOOP 场景
        # 注意：由于 side_tables 存储的是 UID -> SceneName
        
        found_branch = False
        found_loop = False
        
        for uid, scene_name in node_scenes.items():
            if scene_name == "BRANCH":
                found_branch = True
            if scene_name == "LOOP":
                found_loop = True
                
        self.assertTrue(found_branch, "Should have at least one node in BRANCH scene")
        self.assertTrue(found_loop, "Should have at least one node in LOOP scene")

    def test_type_annotation_serialization(self):
        """验证 Phase 3 的 TypeAnnotatedExpr (类型标注) 是否被正确序列化"""
        source = """
var x: int = 1
"""
        with open("test_type.ibci", "w", encoding="utf-8") as f:
            f.write(source)
            
        artifact = self.engine.compile(os.path.abspath("test_type.ibci"))
        result = self.get_main_result(artifact)
        data = FlatSerializer().serialize_result(result)
        nodes = data["pools"]["nodes"]
        
        # 查找 TypeAnnotatedExpr 类型的节点
        type_nodes = [n for n in nodes.values() if n["_type"] == "IbTypeAnnotatedExpr"]
        self.assertTrue(len(type_nodes) >= 1, "Should contain TypeAnnotatedExpr node in pool")
        
        node = type_nodes[0]
        self.assertIn("target", node)
        self.assertIn("annotation", node)
        
        # 验证引用的节点也在池中
        self.assertIn(node["target"], nodes)
        self.assertIn(node["annotation"], nodes)
        
        # 验证目标节点是 Name 类型
        target_node = nodes[node["target"]]
        self.assertEqual(target_node["_type"], "IbName")
        self.assertEqual(target_node["id"], "x")

    def test_filtered_expr_serialization(self):
        """验证 Phase 4 的 FilteredExpr (过滤条件) 是否被正确序列化"""
        source = """
func is_ready() -> bool:
    return True

while True if is_ready():
    pass
"""
        with open("test_filter.ibci", "w", encoding="utf-8") as f:
            f.write(source)
            
        artifact = self.engine.compile(os.path.abspath("test_filter.ibci"))
        result = self.get_main_result(artifact)
        data = FlatSerializer().serialize_result(result)
        nodes = data["pools"]["nodes"]
        
        # 查找 FilteredExpr 类型的节点
        filter_nodes = [n for n in nodes.values() if n["_type"] == "IbFilteredExpr"]
        self.assertTrue(len(filter_nodes) >= 1, "Should contain FilteredExpr node in pool")
        
        node = filter_nodes[0]
        self.assertIn("expr", node)
        self.assertIn("filter", node)
        
        # 验证引用的节点也在池中
        self.assertIn(node["expr"], nodes)
        self.assertIn(node["filter"], nodes)
        
        # 验证 expr 节点是 Constant(True)
        expr_node = nodes[node["expr"]]
        self.assertEqual(expr_node["_type"], "IbConstant")
        self.assertEqual(expr_node["value"], True)

    def test_complex_nested_wrappers_serialization(self):
        """[复合验证] 验证意图 + 过滤 + 类型 + 回退逻辑的多重嵌套序列化"""
        source = """
func is_active() -> bool:
    return True

@ 核心处理逻辑
while True if is_active():
    var result: int = 42
llmexcept:
    print("fallback")
"""
        with open("test_complex.ibci", "w", encoding="utf-8") as f:
            f.write(source)
            
        artifact = self.engine.compile(os.path.abspath("test_complex.ibci"))
        result = self.get_main_result(artifact)
        data = FlatSerializer().serialize_result(result)
        nodes = data["pools"]["nodes"]
        node_intents = data["side_tables"]["node_intents"]
        
        # 层级 1: While (不再被包装，且持有 llm_fallback)
        while_nodes = [uid for uid, n in nodes.items() if n["_type"] == "IbWhile" and n.get("llm_fallback")]
        self.assertTrue(len(while_nodes) >= 1)
        while_uid = while_nodes[0]
        while_node = nodes[while_uid]
        
        # 验证侧表关联的意图
        self.assertIn(while_uid, node_intents)
        intent_uid = node_intents[while_uid][0]
        self.assertEqual(nodes[intent_uid]["content"], "核心处理逻辑")
        
        # 层级 2: FilteredExpr (过滤条件)
        filter_uid = while_node["test"]
        filter_node = nodes[filter_uid]
        self.assertEqual(filter_node["_type"], "IbFilteredExpr")
        
        # 层级 5: Assign (循环体内的赋值)
        assign_uid = while_node["body"][0]
        assign_node = nodes[assign_uid]
        self.assertEqual(assign_node["_type"], "IbAssign")
        
        # 层级 6: TypeAnnotatedExpr (类型标注)
        type_annotated_uid = assign_node["targets"][0]
        type_annotated_node = nodes[type_annotated_uid]
        self.assertEqual(type_annotated_node["_type"], "IbTypeAnnotatedExpr")
        
        # 验证叶子节点
        target_name_uid = type_annotated_node["target"]
        self.assertEqual(nodes[target_name_uid]["id"], "result")

    def test_node_to_symbol_side_table(self):
        """[Phase 5 验证] 验证符号绑定关系是否被正确侧表化"""
        source = """
var score: int = 100
print(score)
"""
        with open("test_sym_table.ibci", "w", encoding="utf-8") as f:
            f.write(source)
            
        artifact = self.engine.compile(os.path.abspath("test_sym_table.ibci"))
        data = FlatSerializer().serialize_result(self.get_main_result(artifact))
        
        node_to_symbol = data["side_tables"]["node_to_symbol"]
        nodes = data["pools"]["nodes"]
        symbols = data["pools"]["symbols"]
        
        # 1. 找到 print(score) 中的 score (Name 节点)
        call_nodes = [n for n in nodes.values() if n["_type"] == "IbCall"]
        self.assertTrue(len(call_nodes) >= 1)
        
        arg_uid = call_nodes[0]["args"][0]
        arg_node = nodes[arg_uid]
        self.assertEqual(arg_node["_type"], "IbName")
        self.assertEqual(arg_node["id"], "score")
        
        # 2. 验证该节点在侧表中有关联符号
        self.assertIn(arg_uid, node_to_symbol, "Name node 'score' should have a symbol binding in side table")
        
        sym_uid = node_to_symbol[arg_uid]
        self.assertIn(sym_uid, symbols, "Symbol UID should exist in symbols pool")
        self.assertEqual(symbols[sym_uid]["name"], "score")

    def test_scope_shadowing_side_table(self):
        """[Phase 5 进阶] 验证作用域遮蔽(Shadowing)场景下的侧表绑定准确性"""
        source = """
var x: int = 1
func outer():
    var x: str = "shadow"
    print(x)
print(x)
"""
        with open("test_shadow.ibci", "w", encoding="utf-8") as f:
            f.write(source)
            
        artifact = self.engine.compile(os.path.abspath("test_shadow.ibci"))
        data = FlatSerializer().serialize_result(self.get_main_result(artifact))
        
        node_to_symbol = data["side_tables"]["node_to_symbol"]
        nodes = data["pools"]["nodes"]
        symbols = data["pools"]["symbols"]
        
        # 1. 找到所有的 Name 节点，其 ID 为 'x'
        x_nodes = [uid for uid, n in nodes.items() if n["_type"] == "IbName" and n.get("id") == "x"]
        # 排除掉赋值目标节点 (ctx='Store')，只看引用节点 (ctx='Load')
        x_refs = [uid for uid in x_nodes if nodes[uid].get("ctx") == "Load"]
        self.assertEqual(len(x_refs), 2, "Should have two references to 'x'")
        
        # 2. 验证第一个引用 (函数内部的 x) 绑定到局部变量符号 (类型为 str)
        # 我们根据行号区分引用
        inner_ref_uid = next(uid for uid in x_refs if nodes[uid]["lineno"] == 5)
        outer_ref_uid = next(uid for uid in x_refs if nodes[uid]["lineno"] == 6)
        
        inner_sym_uid = node_to_symbol[inner_ref_uid]
        outer_sym_uid = node_to_symbol[outer_ref_uid]
        
        self.assertNotEqual(inner_sym_uid, outer_sym_uid, "Shadowed variables must map to different Symbol UIDs")
        
        # 3. 验证符号池中的具体类型
        inner_sym = symbols[inner_sym_uid]
        outer_sym = symbols[outer_sym_uid]
        
        # 通过 type_info 字段验证（在序列化后的 symbols 池中）
        # 注意：这里我们通过符号池引用的类型池 UID 来验证
        self.assertEqual(data["pools"]["types"][inner_sym["type_uid"]]["name"], "str")
        self.assertEqual(data["pools"]["types"][outer_sym["type_uid"]]["name"], "int")

    def test_type_inference_side_table(self):
        """[Phase 5 进阶] 验证表达式类型推导结果是否被正确侧表化"""
        source = "var result = 1 + 2.5" # int + float -> float
        with open("test_type_inf.ibci", "w", encoding="utf-8") as f:
            f.write(source)
            
        artifact = self.engine.compile(os.path.abspath("test_type_inf.ibci"))
        data = FlatSerializer().serialize_result(self.get_main_result(artifact))
        
        node_to_type = data["side_tables"]["node_to_type"]
        nodes = data["pools"]["nodes"]
        
        # 找到 BinOp 节点 (1 + 2.5)
        binop_nodes = [uid for uid, n in nodes.items() if n["_type"] == "IbBinOp"]
        self.assertTrue(len(binop_nodes) >= 1)
        
        binop_uid = binop_nodes[0]
        self.assertIn(binop_uid, node_to_type, "Expression node should have inferred type in side table")
        type_uid = node_to_type[binop_uid]
        self.assertEqual(data["pools"]["types"][type_uid]["name"], "float")

    def test_cross_module_symbol_binding(self):
        """[Phase 5 进阶] 验证跨模块引用时的侧表绑定"""
        # 准备被引用模块
        lib_source = "var shared_val: int = 99"
        with open("lib.ibci", "w", encoding="utf-8") as f:
            f.write(lib_source)
            
        # 准备主模块
        main_source = "import lib\nprint(lib.shared_val)"
        with open("main.ibci", "w", encoding="utf-8") as f:
            f.write(main_source)
            
        artifact = self.engine.compile(os.path.abspath("main.ibci"))
        
        # 获取主模块数据
        main_res = artifact.get_module("main")
        serializer = FlatSerializer()
        data = serializer.serialize_result(main_res)
        node_to_symbol = data["side_tables"]["node_to_symbol"]
        
        # 查找访问 lib.shared_val 的 IbAttribute 节点
        nodes = data["pools"]["nodes"]
        attr_uid = [uid for uid, n in nodes.items() if n["_type"] == "IbAttribute" and n.get("attr") == "shared_val"][0]
        
        # 验证该属性访问节点是否在侧表中绑定了符号
        self.assertIn(attr_uid, node_to_symbol, "Cross-module attribute access should be in side table")
        sym_uid = node_to_symbol[attr_uid]
        
        # 检查该符号是否在 lib 模块的符号池中
        lib_res = artifact.get_module("lib")
        # 注意：必须使用同一个序列化器实例以保持 UID 一致性
        lib_symbols = serializer.serialize_result(lib_res)["pools"]["symbols"]
        self.assertIn(sym_uid, lib_symbols, "Symbol UID must exist in the defining module's symbol pool")
        self.assertEqual(lib_symbols[sym_uid]["name"], "shared_val")

    def test_dict_type_inference_serialization(self):
        """[Phase 5 验证] 验证 DictType 的推导与池化序列化"""
        source = 'var config = {"id": 101, "name": "test"}'
        with open("test_dict.ibci", "w", encoding="utf-8") as f:
            f.write(source)
            
        artifact = self.engine.compile(os.path.abspath("test_dict.ibci"))
        data = FlatSerializer().serialize_result(self.get_main_result(artifact))
        
        node_to_type = data["side_tables"]["node_to_type"]
        nodes = data["pools"]["nodes"]
        types = data["pools"]["types"]
        
        # 1. 找到 Dict 节点
        dict_nodes = [uid for uid, n in nodes.items() if n["_type"] == "IbDict"]
        self.assertTrue(len(dict_nodes) >= 1)
        dict_uid = dict_nodes[0]
        
        # 2. 验证推导类型名
        type_uid = node_to_type[dict_uid]
        self.assertEqual(data["pools"]["types"][type_uid]["name"], "dict")
        
        # 3. 验证符号池中的 DictType 细节
        # 找到 config 变量符号
        symbols = data["pools"]["symbols"]
        config_sym = next(s for s in symbols.values() if s["name"] == "config")
        dict_type_uid = config_sym["type_uid"]
        dict_type = types[dict_type_uid]
        
        self.assertEqual(dict_type["name"], "dict")
        # 验证键值类型 (str, int)
        self.assertEqual(types[dict_type["key_type_uid"]]["name"], "str")
        self.assertEqual(types[dict_type["value_type_uid"]]["name"], "int")

if __name__ == "__main__":
    unittest.main()
