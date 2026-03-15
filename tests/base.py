import unittest
import os
import textwrap
from typing import Optional, Dict, Any, List, Callable
from contextlib import contextmanager
from core.engine import IBCIEngine
from core.domain.issue import CompilerError, InterpreterError
from core.domain.blueprint import CompilationArtifact
from core.domain.types import ModuleMetadata

class MockAI:
    """通用的 AI 服务 Mock (IES 2.0 Standard)"""
    def __init__(self):
        self.last_sys = ""
        self.last_user = ""
        self.response = "42"
        self.calls = []
        self._decision_map = {
            "1": "1", "true": "1", "yes": "1", "ok": "1",
            "0": "0", "false": "0", "no": "0", "fail": "0"
        }

    def setup(self, capabilities):
        # 核心：将自己注册为内核的 LLM Provider
        capabilities.llm_provider = self

    def set_config(self, url, key, model):
        pass

    def get_decision_map(self):
        return self._decision_map

    def __call__(self, sys, user, scene="general"):
        self.last_sys = sys
        self.last_user = user
        self.calls.append({"sys": sys, "user": user, "scene": scene})
        return self.response

    def get_return_type_prompt(self, type_name):
        return f"Return type should be {type_name}"

    def set_retry_hint(self, hint):
        pass
    
    def get_last_call_info(self):
        return {"sys": self.last_sys, "user": self.last_user, "response": self.response}

    def get_vtable(self):
        return {
            "set_config": self.set_config,
            "set_retry_hint": lambda x: None,
            "set_retry": lambda x: None,
            "set_timeout": lambda x: None,
            "set_general_prompt": lambda x: None,
            "set_branch_prompt": lambda x: None,
            "set_loop_prompt": lambda x: None,
            "set_return_type_prompt": lambda x, y: None,
            "get_return_type_prompt": lambda x: "",
            "set_decision_map": lambda x: None,
            "get_decision_map": self.get_decision_map,
            "get_last_call_info": self.get_last_call_info,
            "get_scene_prompt": lambda x: "",
            "set_scene_config": lambda x, y: None,
            "set_global_intent": lambda x: None,
            "clear_global_intents": lambda: None,
            "remove_global_intent": lambda x: None,
            "get_global_intents": lambda: [],
            "get_current_intent_stack": lambda: [],
            "mask": lambda x: None,
        }

class MockHostService:
    """通用的宿主服务 Mock (IES 2.0 Standard)"""
    def __init__(self):
        self.saved_states = {}
        self.calls = []

    def setup(self, capabilities):
        pass

    def save_state(self, path: str, data: Any):
        self.saved_states[path] = data
        self.calls.append(("save_state", path, data))

    def load_state(self, path: str) -> Any:
        self.calls.append(("load_state", path))
        return self.saved_states.get(path)

    def run_isolated(self, path: str, policy: Dict[str, Any]) -> bool:
        self.calls.append(("run_isolated", path, policy))
        return True

    def get_source(self) -> str:
        self.calls.append(("get_source",))
        return "mock source"

    def get_vtable(self):
        return {
            "save_state": self.save_state,
            "load_state": self.load_state,
            "run_isolated": self.run_isolated,
            "get_source": self.get_source
        }
class IBCTestEngine(IBCIEngine):
    """
    专为测试设计的引擎子类。
    在保持生产环境逻辑的同时，提供内部状态观察能力。
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_artifact: Optional[CompilationArtifact] = None

    def compile_string(self, code: str, variables: Optional[Dict[str, Any]] = None, silent: bool = False) -> CompilationArtifact:
        self.last_artifact = super().compile_string(code, variables, silent=silent)
        return self.last_artifact

    def get_last_result(self, module_name: str = None):
        """获取最近一次编译的单模块结果 (CompilationResult)"""
        if not self.last_artifact:
            return None
        name = module_name or self.last_artifact.entry_module
        return self.last_artifact.get_module(name)

class BaseIBCTest(unittest.TestCase):
    """
    IBCI 单元测试基类。
    提供标准化的 Engine 接口调用和夹具 (Fixture) 加载能力。
    """
    def setUp(self):
        # 初始化专为测试定制的引擎
        self.engine = IBCTestEngine(root_dir=os.getcwd())
        self.outputs = []
        self.silent = False
        self.mock_ai: Optional[MockAI] = None
        self.mock_host: Optional[MockHostService] = None

    def setup_mock_ai(self):
        """快捷设置 Mock AI 服务"""
        self.mock_ai = MockAI()
        # 注册插件，以便编译器能识别 'ai' 模块
        self.engine.register_plugin("ai", self.mock_ai, type_metadata=ModuleMetadata(name="ai"))
        return self.mock_ai

    def setup_mock_host(self):
        """快捷设置 Mock 宿主服务"""
        self.mock_host = MockHostService()
        self.engine.register_plugin("host", self.mock_host, type_metadata=ModuleMetadata(name="host"))
        return self.mock_host

    @contextmanager
    def silent_mode(self):
        """静默模式上下文管理器"""
        old_silent = self.silent
        self.silent = True
        try:
            yield
        finally:
            self.silent = old_silent

    def fixture_path(self, name: str) -> str:
        """获取夹具文件的绝对路径"""
        # 默认夹具目录在 tests/fixtures
        path = os.path.join(os.getcwd(), "tests", "fixtures", name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Fixture not found: {path}")
        return path

    def write_file(self, rel_path: str, content: str) -> str:
        """在测试根目录下创建文件"""
        full_path = os.path.join(self.engine.root_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        # 自动去除缩进
        dedented_content = textwrap.dedent(content).strip()
        # 确保以换行符结尾
        if not dedented_content.endswith("\n"):
            dedented_content += "\n"
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(dedented_content)
        return full_path

    def compile_code(self, code: str, variables=None, silent: Optional[bool] = None):
        """编译代码字符串并返回蓝图"""
        is_silent = silent if silent is not None else self.silent
        code = textwrap.dedent(code).strip() + "\n"
        try:
            return self.engine.compile_string(code, variables, silent=is_silent)
        except CompilerError as e:
            if not is_silent:
                self._print_diagnostics(e)
            raise e

    def run_code(self, code: str, variables=None, silent: Optional[bool] = None, pre_run_hook: Optional[Callable[[IBCIEngine], None]] = None):
        """
        运行代码字符串并捕获输出。
        [IES 2.0] 标准化全链路测试工具。
        """
        is_silent = silent if silent is not None else self.silent
        code = textwrap.dedent(code).strip() + "\n"
        self.outputs = []
        
        # 1. 重置引擎实例以确保生命周期清洁
        old_root = self.engine.root_dir
        self.engine = IBCTestEngine(root_dir=old_root)
        
        # 2. 恢复 Mock 环境
        if self.mock_ai:
            self.engine.register_plugin("ai", self.mock_ai, type_metadata=ModuleMetadata(name="ai"))
        if self.mock_host:
            self.engine.register_plugin("host", self.mock_host, type_metadata=ModuleMetadata(name="host"))

        try:
            # 3. 静态编译阶段
            artifact = self.engine.compile_string(code, variables, silent=is_silent)
            
            # 4. 执行准备阶段
            from core.compiler.serialization.serializer import FlatSerializer
            serializer = FlatSerializer()
            artifact_dict = serializer.serialize_artifact(artifact)
            
            # 内部触发 _prepare_interpreter 但不立即运行
            self.engine._prepare_interpreter(artifact_dict, output_callback=lambda m: self.outputs.append(m))
            
            # 5. 执行钩子 (允许测试用例在运行前注入拦截器)
            if pre_run_hook:
                pre_run_hook(self.engine)
                
            # 6. 注入初始变量
            if variables:
                for name, val in variables.items():
                    if not hasattr(val, 'ib_class'):
                        val = self.engine.interpreter.registry.box(val)
                    self.engine.interpreter.runtime_context.define_variable(name, val)
            
            # 7. 启动执行
            return self.engine.interpreter.run()
            
        except CompilerError as e:
            if not is_silent:
                self._print_diagnostics(e)
            raise e
        except InterpreterError as e:
            if not is_silent:
                print(f"\nINTERPRETER ERROR: {e}")
            raise e

    @contextmanager
    def capture_llm(self):
        """捕获 LLM 调用的上下文管理器"""
        captured = []
        def mock_llm_call(sys_prompt, user_prompt, node_uid, **kwargs):
            captured.append({"sys": sys_prompt, "user": user_prompt, "node": node_uid})
            return "42" # 默认 Mock 返回值
            
        def hook(engine):
            engine.interpreter.service_context.llm_executor._call_llm = mock_llm_call
            
        yield captured, hook

    def assert_output(self, expected: str):
        """断言输出列表中包含预期字符串"""
        self.assertIn(expected, self.outputs, f"Expected output '{expected}' not found in {self.outputs}")

    def assert_outputs(self, expected_list: List[str]):
        """按顺序断言输出列表"""
        # 确保输出列表至少和预期列表一样长
        self.assertGreaterEqual(len(self.outputs), len(expected_list), f"Expected at least {len(expected_list)} outputs, but got {len(self.outputs)}: {self.outputs}")
        for i, expected in enumerate(expected_list):
            self.assertEqual(self.outputs[i], expected, f"Output mismatch at index {i}. Outputs: {self.outputs}")

    def _print_diagnostics(self, e: CompilerError):
        """格式化打印编译器错误"""
        from core.compiler.diagnostics.formatter import DiagnosticFormatter
        print("\n" + DiagnosticFormatter.format_all(e.diagnostics, source_manager=self.engine.scheduler.source_manager))

    def get_last_result(self, module_name: str = None):
        """快捷获取最近一次编译的单模块结果"""
        return self.engine.get_last_result(module_name)
