import unittest
import os
import shutil
from typing import Any
from core.engine import IBCIEngine
from core.domain.issue import CompilerError
from core.domain.dependencies import CircularDependencyError

class BaseCompilerTest(unittest.TestCase):
    """
    Compiler 测试基座，负责加载 Fixture 文件并执行编译。
    """
    def setUp(self):
        self.fixtures_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures", "compiler"))
        # 每次测试创建一个临时目录模拟工作区，避免文件污染
        self.test_root = os.path.abspath("temp_test_root")
        if os.path.exists(self.test_root):
            shutil.rmtree(self.test_root)
        os.makedirs(self.test_root)
        
        # 将工作目录切换到测试根目录，模拟真实运行环境
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)
        
        self.engine = IBCIEngine(root_dir=self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if os.path.exists(self.test_root):
            shutil.rmtree(self.test_root)

    def get_fixture_path(self, relative_path: str) -> str:
        return os.path.join(self.fixtures_dir, relative_path)

    def copy_fixture_to_root(self, relative_path: str):
        """将 Fixture 目录下的文件/文件夹拷贝到测试根目录"""
        src = self.get_fixture_path(relative_path)
        # 如果 src 是一个 ibci 文件，则拷贝到根目录
        # 如果是一个目录，则拷贝整个内容到根目录
        dst_name = os.path.basename(relative_path)
        dst = os.path.join(self.test_root, dst_name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        return dst

    def get_fixture_content(self, relative_path: str) -> str:
        """读取 Fixture 文件内容为字符串"""
        full_path = self.get_fixture_path(relative_path)
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    def assert_compile_success(self, main_file_rel_path: str) -> Any:
        """断言编译成功并返回 CompilationArtifact"""
        if os.path.isabs(main_file_rel_path):
            full_path = main_file_rel_path
        else:
            full_path = self.copy_fixture_to_root(main_file_rel_path)
        try:
            artifact = self.engine.compile(full_path)
            self.assertIsNotNone(artifact, f"Expected compilation success for {main_file_rel_path}")
            return artifact
        except (CompilerError, CircularDependencyError) as e:
            self.fail(f"Expected compilation success for {main_file_rel_path}, but got {type(e).__name__}: {e}")

    def get_main_result(self, artifact: Any) -> Any:
        """从 Artifact 中获取主模块的编译结果"""
        return artifact.get_module(artifact.entry_module)

    def assert_compile_fail(self, main_file_rel_path: str):
        """断言编译失败"""
        if os.path.isabs(main_file_rel_path):
            full_path = main_file_rel_path
        else:
            full_path = self.copy_fixture_to_root(main_file_rel_path)
        try:
            success = self.engine.run(full_path, prepare_interpreter=False)
            self.assertFalse(success, f"Expected compilation failure (False) for {main_file_rel_path}")
        except (CompilerError, CircularDependencyError):
            # 捕获预期的异常也算失败成功
            pass
        except Exception as e:
            self.fail(f"Unexpected exception during compilation failure test: {type(e).__name__}: {e}")
