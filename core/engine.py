import os
import importlib.util
from typing import Optional, Dict, Any

from core.scheduler import Scheduler
from core.runtime.interpreter.interpreter import Interpreter
from core.support.diagnostics.issue_tracker import IssueTracker
from core.runtime.module_system.discovery import ModuleDiscoveryService
from core.runtime.module_system.loader import ModuleLoader
from core.support.host_interface import HostInterface
from core.compiler.semantic.types import ModuleType
from core.types.diagnostic_types import CompilerError
from core.support.diagnostics.core_debugger import CoreDebugger, CoreModule, DebugLevel

class IBCIEngine:
    """
    IBC-Inter 标准化引擎，整合了调度、编译和执行流程。
    """
    def __init__(self, root_dir: Optional[str] = None, auto_sniff: bool = True, core_debug_config: Optional[Dict[str, str]] = None):
        self.root_dir = os.path.abspath(root_dir or os.getcwd())
        self.issue_tracker = IssueTracker()
        self.debugger = CoreDebugger()
        
        # 0. 配置内核调试器
        if core_debug_config:
            self.debugger.configure(core_debug_config)
            self.debugger.trace(CoreModule.GENERAL, DebugLevel.BASIC, f"Core Debugger initialized with config: {core_debug_config}")
        
        # 1. 初始化模块发现服务 (内置路径 + 插件路径)
        builtin_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ibc_modules")
        plugins_path = os.path.join(self.root_dir, "plugins")
        
        self.discovery_service = ModuleDiscoveryService([builtin_path, plugins_path])
        self.module_loader = ModuleLoader([builtin_path, plugins_path])
        
        # 2. 加载元数据以支持静态分析
        self.host_interface = self.discovery_service.discover_all()
        
        self.scheduler = Scheduler(self.root_dir, host_interface=self.host_interface, debugger=self.debugger)
        self.interpreter: Optional[Interpreter] = None

    def _prepare_interpreter(self, output_callback=None):
        """初始化解释器并动态加载模块实现"""
        self.interpreter = Interpreter(
            self.issue_tracker, 
            scheduler=self.scheduler, 
            output_callback=output_callback,
            host_interface=self.host_interface,
            debugger=self.debugger
        )
        # 统一由 ModuleLoader 驱动实现层的加载与注入
        self.module_loader.load_and_register_all(self.interpreter.service_context)

    def register_plugin(self, name: str, implementation: Any, type_metadata: Optional[ModuleType] = None):
        """
        手动注册插件（兼容旧模式，但建议使用 plugins/ 目录下的双文件协议）。
        """
        self.host_interface.register_module(name, implementation, type_metadata)
        self.scheduler.host_interface = self.host_interface

    def run_string(self, code: str, variables: Optional[Dict[str, Any]] = None, output_callback=None, silent: bool = False, prepare_interpreter: bool = True) -> bool:
        """
        运行一段 IBCI 代码字符串。
        """
        import tempfile
        # Use system temp directory but explicitly allow this file in scheduler
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ibci', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_path = f.name
        
        try:
            # Register this specific temp file as allowed even if outside root
            self.scheduler.allow_file(temp_path)
            return self.run(temp_path, variables, output_callback, silent=silent, prepare_interpreter=prepare_interpreter)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def run(self, entry_file: str, variables: Optional[Dict[str, Any]] = None, output_callback=None, silent: bool = False, prepare_interpreter: bool = True) -> bool:
        """
        运行一个 IBCI 项目或文件。
        
        Args:
            entry_file: 入口文件路径（绝对或相对 root_dir）
            variables: 注入的全局变量（如 API 配置）
            output_callback: 自定义输出回调
            silent: 如果为 True，则不向 stdout 打印编译或运行时错误，而是直接由调用者处理异常。
            prepare_interpreter: 是否重新初始化解释器。如果为 False，则使用当前已有的解释器。
            
        Returns:
            bool: 执行是否成功
        """
        abs_entry = os.path.abspath(entry_file)
        if not os.path.exists(abs_entry):
            if not silent:
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
                if not silent:
                    print(f"Error: Failed to get AST for {abs_entry}")
                return False

            # 2. 准备执行环境
            if prepare_interpreter or not self.interpreter:
                self._prepare_interpreter(output_callback)
            
            # 3. 注入外部变量
            if variables:
                for name, val in variables.items():
                    self.interpreter.context.define_variable(name, val)

            # 4. 执行
            self.interpreter.interpret(entry_ast)
            return True

        except CompilerError as e:
            if not silent:
                print("\n--- Compilation Errors ---")
                for diag in self.scheduler.issue_tracker.diagnostics:
                    print(f"[{diag.severity.name}] {diag.code}: {diag.message} (Line {diag.location.line if diag.location else '?'})")
            else:
                # 在静默模式下，让调用者自己决定如何处理异常
                raise e
            return False
        except Exception as e:
            if not silent:
                print(f"\nRuntime Error: {str(e)}")
                import traceback
                traceback.print_exc()
            else:
                # 在静默模式下，让调用者自己决定如何处理异常
                raise e
            return False

    def get_variable(self, name: str) -> Any:
        """获取解释器上下文中的变量"""
        if self.interpreter and self.interpreter.context:
            return self.interpreter.context.get_variable(name)
        raise RuntimeError("Interpreter not initialized")

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
