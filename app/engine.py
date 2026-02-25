import os
import importlib.util
from typing import Optional, Dict, Any

from utils.scheduler import Scheduler
from utils.interpreter.interpreter import Interpreter
from utils.diagnostics.issue_tracker import IssueTracker
from utils.interpreter.modules.stdlib import register_stdlib
from utils.host_interface import HostInterface
from utils.semantic.types import ModuleType
from app.services.stdlib_provider import get_stdlib_metadata
from typedef.diagnostic_types import CompilerError

class IBCIEngine:
    """
    IBC-Inter 标准化引擎，整合了调度、编译和执行流程。
    """
    def __init__(self, root_dir: Optional[str] = None, auto_sniff: bool = True):
        self.root_dir = os.path.abspath(root_dir or os.getcwd())
        self.issue_tracker = IssueTracker()
        
        # 初始化统一的宿主接口，并加载标准库元数据
        self.host_interface = get_stdlib_metadata()
        
        self.scheduler = Scheduler(self.root_dir, host_interface=self.host_interface)
        self.interpreter: Optional[Interpreter] = None

        # 自动嗅探本地插件
        if auto_sniff:
            self._sniff_plugins()

    def _sniff_plugins(self):
        """
        自动探测项目目录下的 plugins/ 文件夹并加载插件。
        协议：
        1. 寻找 root_dir/plugins/*.py
        2. 如果模块有 setup(engine) 函数，调用它完成深度注册
        3. 否则，将模块整体注册为同名插件
        """
        plugins_dir = os.path.join(self.root_dir, "plugins")
        if not os.path.isdir(plugins_dir):
            return

        for filename in os.listdir(plugins_dir):
            if not filename.endswith(".py") or filename == "__init__.py":
                continue
            
            plugin_path = os.path.join(plugins_dir, filename)
            module_name = os.path.splitext(filename)[0]

            try:
                spec = importlib.util.spec_from_file_location(module_name, plugin_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)

                # 优先寻找 setup(engine) 钩子
                if hasattr(mod, "setup") and callable(mod.setup):
                    mod.setup(self)
                else:
                    # 默认自动注册整个模块
                    self.register_plugin(module_name, mod)
            except Exception as e:
                print(f"Warning: Failed to auto-sniff plugin {filename}: {e}")

    def _prepare_interpreter(self, output_callback=None):
        """初始化解释器并注册标准库实现"""
        self.interpreter = Interpreter(
            self.issue_tracker, 
            scheduler=self.scheduler, 
            output_callback=output_callback,
            host_interface=self.host_interface
        )
        # 注册运行时实现（覆盖 metadata 中的 None 值）
        register_stdlib(self.interpreter.service_context)

    def register_plugin(self, name: str, implementation: Any, type_metadata: Optional[ModuleType] = None):
        """
        供第三方开发者注册自定义 Python 插件模块。
        
        Args:
            name: 插件名称，在 .ibci 中通过 'import <name>' 使用
            implementation: 插件的 Python 实现对象
            type_metadata: 可选的静态类型定义。如果不提供，将通过反射自动推断成员。
        """
        self.host_interface.register_module(name, implementation, type_metadata)
        # 重新同步调度器的预定义符号（如果有变动）
        self.scheduler.host_interface = self.host_interface

    def run(self, entry_file: str, variables: Optional[Dict[str, Any]] = None, output_callback=None) -> bool:
        """
        运行一个 IBCI 项目或文件。
        
        Args:
            entry_file: 入口文件路径（绝对或相对 root_dir）
            variables: 注入的全局变量（如 API 配置）
            output_callback: 自定义输出回调
            
        Returns:
            bool: 执行是否成功
        """
        abs_entry = os.path.abspath(entry_file)
        if not os.path.exists(abs_entry):
            print(f"Error: Entry file not found: {abs_entry}")
            return False

        try:
            # 0. 预置符号到调度器（用于静态检查）
            if variables:
                self.scheduler.predefined_symbols.update(variables)

            # 1. 静态编译与依赖解析
            ast_cache = self.scheduler.compile_project(abs_entry)
            entry_ast = ast_cache.get(abs_entry)
            
            if not entry_ast:
                print(f"Error: Failed to get AST for {abs_entry}")
                return False

            # 2. 准备执行环境
            self._prepare_interpreter(output_callback)
            
            # 3. 注入外部变量
            if variables:
                for name, val in variables.items():
                    self.interpreter.context.define_variable(name, val)

            # 4. 执行
            self.interpreter.interpret(entry_ast)
            return True

        except CompilerError:
            print("\n--- Compilation Errors ---")
            for diag in self.scheduler.issue_tracker.diagnostics:
                print(f"[{diag.severity.name}] {diag.code}: {diag.message} (Line {diag.location.line if diag.location else '?'})")
            return False
        except Exception as e:
            print(f"\nRuntime Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def check(self, entry_file: str) -> bool:
        """
        仅对项目进行静态检查（编译和语义分析）。
        """
        abs_entry = os.path.abspath(entry_file)
        try:
            self.scheduler.compile_project(abs_entry)
            print(f"Check successful: {entry_file}")
            return True
        except CompilerError:
            print(f"Check failed: {entry_file}")
            return False
