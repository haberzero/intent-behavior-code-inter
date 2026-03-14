import unittest
import os
import textwrap
from typing import Optional, Dict, Any
from contextlib import contextmanager
from core.engine import IBCIEngine
from core.domain.issue import CompilerError, InterpreterError
from core.domain.blueprint import CompilationArtifact

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

    def run_code(self, code: str, variables=None, silent: Optional[bool] = None):
        """运行代码字符串并捕获输出"""
        is_silent = silent if silent is not None else self.silent
        code = textwrap.dedent(code).strip() + "\n"
        self.outputs = []
        try:
            artifact = self.engine.compile_string(code, variables, silent=is_silent)
            return self.engine.execute(artifact, variables, output_callback=lambda m: self.outputs.append(m))
        except CompilerError as e:
            if not is_silent:
                self._print_diagnostics(e)
            raise e
        except InterpreterError as e:
            if not is_silent:
                print(f"\nINTERPRETER ERROR: {e}")
            raise e

    def _print_diagnostics(self, e: CompilerError):
        """格式化打印编译器错误"""
        from core.compiler.diagnostics.formatter import DiagnosticFormatter
        print("\n" + DiagnosticFormatter.format_all(e.diagnostics, source_manager=self.engine.scheduler.source_manager))

    def get_last_result(self, module_name: str = None):
        """快捷获取最近一次编译的单模块结果"""
        return self.engine.get_last_result(module_name)
