import unittest
import copy
from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser
from core.compiler.semantic.passes.semantic_analyzer import SemanticAnalyzer
from core.compiler.serialization.serializer import FlatSerializer
from core.runtime.loader.artifact_loader import ArtifactLoader
from core.domain.factory import create_default_registry
from core.foundation.registry import Registry
from core.domain.types import descriptors

class TestArtifactLoading(unittest.TestCase):
    """
    验证运行时产物加载与重水化 (Phase 3.1)。
    确保编译器产出的 UID 链路在经过序列化/反序列化后，能完美还原为运行时 Registry 中的对象。
    """

    def setUp(self):
        # 编译器环境
        self.comp_registry = create_default_registry()
        self.analyzer = SemanticAnalyzer(registry=self.comp_registry)
        self.serializer = FlatSerializer()

        # 运行时环境 (物理隔离)
        self.rt_foundation_registry = Registry()
        # 初始化并绑定 MetadataRegistry
        meta_reg = create_default_registry()
        token = self.rt_foundation_registry.get_kernel_token()
        self.rt_foundation_registry.register_metadata_registry(meta_reg, token)
        
        # [IES 2.0] 模拟状态机跳转到 HYDRATION 阶段，以允许加载器执行
        from core.runtime.enums import RegistrationState
        self.rt_foundation_registry.set_state_level(RegistrationState.STAGE_2_CORE_TYPES.value, token)
        self.rt_foundation_registry.set_state_level(RegistrationState.STAGE_3_PLUGIN_METADATA.value, token)
        self.rt_foundation_registry.set_state_level(RegistrationState.STAGE_4_PLUGIN_IMPL.value, token)
        self.rt_foundation_registry.set_state_level(RegistrationState.STAGE_5_HYDRATION.value, token)
        self._kernel_token = token
        
        self.loader = ArtifactLoader(self.rt_foundation_registry)

    def compile_and_load(self, code: str):
        # 1. 编译
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        self.analyzer.issue_tracker = parser.context.issue_tracker
        try:
            module = parser.parse()
            result = self.analyzer.analyze(module)
        except Exception as e:
            raise e
        
        # 2. 序列化
        flat_data = self.serializer.serialize_result(result)
        
        # 3. 模拟完整的项目结构 (Artifact)
        artifact = {
            "version": "2.0",
            "entry_module": "main",
            "pools": flat_data["pools"],
            "modules": {
                "main": {
                    "root_node_uid": flat_data["root_node_uid"],
                    "side_tables": flat_data["side_tables"]
                }
            }
        }
        
        # 4. 运行时加载
        return self.loader.load(artifact)

    def test_primitive_rehydration(self):
        """验证基础类型(int, str)的重水化标识一致性"""
        code = 'var x: int = 10\n'
        loaded = self.compile_and_load(code)
        
        # 找到符号 x
        x_sym_uid = None
        for uid, sym in loaded.symbol_pool.items():
            if sym["name"] == "x":
                x_sym_uid = uid
                break
        self.assertIsNotNone(x_sym_uid)
        
        # 通过 Hydrator 还原类型
        type_uid = loaded.symbol_pool[x_sym_uid]["type_uid"]
        hydrated_type = loaded.type_hydrator.hydrate(type_uid)
        
        # 验证 hydrated_type 是运行时 Registry 中的 int 实例
        rt_int = self.rt_foundation_registry.get_metadata_registry().resolve("int")
        self.assertIs(hydrated_type, rt_int)
        self.assertEqual(hydrated_type.name, "int")

    def test_nested_generic_rehydration(self):
        """验证嵌套泛型 (list[dict[str, int]]) 的递归重水化"""
        code = 'var x: list[dict[str, int]] = []\n'
        loaded = self.compile_and_load(code)
        
        # 1. 获取符号 x 的类型 UID
        x_sym_uid = next(uid for uid, s in loaded.symbol_pool.items() if s["name"] == "x")
        type_uid = loaded.symbol_pool[x_sym_uid]["type_uid"]
        
        # 2. 执行水化
        hydrated_type = loaded.type_hydrator.hydrate(type_uid)
        
        # 3. 验证结构
        self.assertIsInstance(hydrated_type, descriptors.ListMetadata)
        dict_type = hydrated_type.element_type
        self.assertIsInstance(dict_type, descriptors.DictMetadata)
        
        self.assertEqual(dict_type.key_type.name, "str")
        self.assertEqual(dict_type.value_type.name, "int")
        
        # 4. 验证 Registry 绑定
        self.assertIs(dict_type.key_type, self.rt_foundation_registry.get_metadata_registry().resolve("str"))
        self.assertIs(dict_type._registry, self.rt_foundation_registry.get_metadata_registry())

    def test_function_signature_rehydration(self):
        """验证函数签名的重水化"""
        code = '''
func add(int a, float b) -> float:
    return a + b
'''
        loaded = self.compile_and_load(code)
        
        # 找到函数符号
        add_sym_uid = next(uid for uid, s in loaded.symbol_pool.items() if s["name"] == "add")
        type_uid = loaded.symbol_pool[add_sym_uid]["type_uid"]
        
        # 水化
        hydrated_func = loaded.type_hydrator.hydrate(type_uid)
        
        self.assertIsInstance(hydrated_func, descriptors.FunctionMetadata)
        self.assertEqual(len(hydrated_func.param_types), 2)
        self.assertEqual(hydrated_func.param_types[0].name, "int")
        self.assertEqual(hydrated_func.param_types[1].name, "float")
        self.assertEqual(hydrated_func.return_type.name, "float")

    def test_class_metadata_rehydration(self):
        """验证类元数据的重水化与父类关联"""
        code = '''
class Animal:
    var name: str = ""

class Dog(Animal):
    func bark():
        pass
'''
        loaded = self.compile_and_load(code)
        
        # 找到 Dog 类型
        dog_type_uid = None
        for uid, t_data in loaded.type_pool.items():
            if t_data["name"] == "Dog" and t_data["kind"] == "ClassMetadata":
                dog_type_uid = uid
                break
        self.assertIsNotNone(dog_type_uid)
        
        # 水化
        hydrated_dog = loaded.type_hydrator.hydrate(dog_type_uid)
        
        self.assertIsInstance(hydrated_dog, descriptors.ClassMetadata)
        self.assertEqual(hydrated_dog.name, "Dog")
        self.assertEqual(hydrated_dog.parent_name, "Animal")

if __name__ == "__main__":
    unittest.main()
