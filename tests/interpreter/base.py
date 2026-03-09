import unittest
import os
import shutil
import tempfile
import textwrap
from typing import Any, Dict, List, Optional, Callable
from core.engine import IBCIEngine
from core.domain.issue import InterpreterError, CompilerError

class BaseInterpreterTest(unittest.TestCase):
    """
    解释器测试基座。
    提供代码运行、输出捕获、状态校验等辅助方法。
    支持多引擎实例隔离测试。
    """
    def setUp(self):
        # 每次测试创建一个独立的临时根目录
        self.test_root = tempfile.mkdtemp(prefix="ibci_test_")
        self.engine = IBCIEngine(root_dir=self.test_root)
        self.outputs: List[str] = []
        
        # 记录旧的 CWD 并切换
        self.old_cwd = os.getcwd()
        os.chdir(self.test_root)

    def tearDown(self):
        os.chdir(self.old_cwd)
        if os.path.exists(self.test_root):
            shutil.rmtree(self.test_root)

    def output_callback(self, value: Any):
        """捕获解释器 print 输出"""
        self.outputs.append(str(value))

    def run_code(self, code: str, variables: Optional[Dict[str, Any]] = None) -> bool:
        """运行代码并返回是否成功"""
        # 自动去除 Python 代码中的缩进
        dedented_code = textwrap.dedent(code).strip()
        # [FIX] 确保代码以换行符结尾，避免 Parser 在 block 解析结束时因缺少 NEWLINE/DEDENT 报错
        if not dedented_code.endswith("\n"):
            dedented_code += "\n"
            
        try:
            # [IES Support] 在运行前同步 LLM Provider，如果已手动注册了 'ai' 模块
            ai_impl = self.engine.host_interface.get_module_implementation("ai")
            if ai_impl and hasattr(self.engine.scheduler, "llm_executor"):
                self.engine.scheduler.llm_executor.llm_callback = ai_impl
                
            return self.engine.run_string(
                dedented_code, 
                variables=variables, 
                output_callback=self.output_callback,
                silent=True # 抛出原始异常以便 assertRaises 捕获
            )
        except CompilerError as e:
            # 如果是预料之外的编译错误，打印诊断信息方便调试
            import sys
            from core.compiler.diagnostics.formatter import DiagnosticFormatter
            sys.stderr.write("\n[DEBUG] Compilation Errors in Test Case:\n")
            sys.stderr.write(DiagnosticFormatter.format_all(e.diagnostics))
            sys.stderr.write("\n")
            raise e

    def assert_output(self, expected: str):
        """断言输出列表中包含预期字符串"""
        self.assertIn(expected, self.outputs, f"Expected output '{expected}' not found in {self.outputs}")

    def assert_outputs(self, expected_list: List[str]):
        """按顺序断言输出列表"""
        # 确保输出列表至少和预期列表一样长
        self.assertGreaterEqual(len(self.outputs), len(expected_list), f"Expected at least {len(expected_list)} outputs, but got {len(self.outputs)}: {self.outputs}")
        for i, expected in enumerate(expected_list):
            self.assertEqual(self.outputs[i], expected, f"Output mismatch at index {i}. Outputs: {self.outputs}")

    def write_file(self, rel_path: str, content: str) -> str:
        """在测试根目录下创建文件"""
        full_path = os.path.join(self.test_root, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        # 自动去除缩进
        dedented_content = textwrap.dedent(content).strip()
        # 确保以换行符结尾
        if not dedented_content.endswith("\n"):
            dedented_content += "\n"
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(dedented_content)
        return full_path

    def create_secondary_engine(self, root_dir: Optional[str] = None) -> IBCIEngine:
        """创建一个独立的次要引擎实例，用于多实例隔离测试"""
        return IBCIEngine(root_dir=root_dir or self.test_root)
