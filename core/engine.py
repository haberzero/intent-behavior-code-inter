import os
import importlib.util
from typing import Optional, Dict, Any

from core.compiler.scheduler import Scheduler
from core.runtime.interpreter.interpreter import Interpreter
from core.compiler.support.issue_adapter import wrap_tracker
from core.runtime.module_system.discovery import ModuleDiscoveryService
from core.runtime.module_system.loader import ModuleLoader
from core.support.host_interface import HostInterface
from core.foundation.types import ModuleMetadata
from core.domain.diagnostics import CompilerError
from core.domain.exceptions import InterpreterError
from core.support.diagnostics.core_debugger import CoreDebugger, CoreModule, DebugLevel

class IBCIEngine:
    """
    IBC-Inter 标准化引擎，整合了调度、编译和执行流程。
    """
    def __init__(self, root_dir: Optional[str] = None, auto_sniff: bool = True, core_debug_config: Optional[Dict[str, str]] = None):
        from core.foundation.builtins import initialize_builtin_classes
        initialize_builtin_classes()
        
        self.root_dir = os.path.abspath(root_dir or os.getcwd())
        from core.support.diagnostics.issue_tracker import IssueTracker
        self.issue_tracker = wrap_tracker(IssueTracker())
        self.debugger = CoreDebugger()
        
        # 0. 配置内核调试器
        if core_debug_config:
            self.debugger.configure(core_debug_config)
            self.debugger.trace(CoreModule.GENERAL, DebugLevel.BASIC, f"Core Debugger initialized with config: {core_debug_config}")
            
        # [NEW] 同步输出回调到调试器，确保内核追踪能被捕获
        self.debugger.output_callback = None # 默认

        # 1. 初始化模块发现服务 (内置路径 + 插件路径)
        builtin_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ibc_modules")
        plugins_path = os.path.join(self.root_dir, "plugins")
        
        self.discovery_service = ModuleDiscoveryService([builtin_path, plugins_path])
        self.module_loader = ModuleLoader([builtin_path, plugins_path])
        
        # 2. 加载元数据以支持静态分析
        self.host_interface = self.discovery_service.discover_all()
        
        self.scheduler = Scheduler(self.root_dir, host_interface=self.host_interface, debugger=self.debugger)
        
        self.interpreter: Optional[Interpreter] = None

    def _prepare_interpreter(self, artifact: Optional[Any] = None, output_callback=None):
        """初始化解释器并动态加载模块实现"""
        self.interpreter = Interpreter(
            self.issue_tracker, 
            artifact=artifact, 
            output_callback=output_callback,
            host_interface=self.host_interface,
            debugger=self.debugger,
            root_dir=self.root_dir
        )
        # 统一由 ModuleLoader 驱动实现层的加载与注入
        self.module_loader.load_and_register_all(self.interpreter.service_context)

    def register_plugin(self, name: str, implementation: Any, type_metadata: Optional[ModuleMetadata] = None):
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
        abs_entry = os.path.abspath(entry_file)
        # 同步调试器输出回调
        if output_callback:
            self.debugger.output_callback = output_callback
        
        if not os.path.exists(abs_entry):
            if not silent:
                print(f"Error: Entry file not found: {abs_entry}")
            return False

        try:
            # 1. 静态编译阶段
            artifact = self.compile(abs_entry, variables)
            
            # 2. 执行阶段 (可选)
            if prepare_interpreter:
                return self.execute(artifact, variables, output_callback)
            
            return True

        except CompilerError as e:
            if not silent:
                print("\n--- Compilation Errors ---")
                for diag in self.scheduler.issue_tracker.diagnostics:
                    print(f"[{diag.severity.name}] {diag.code}: {diag.message} (Line {diag.location.line if diag.location else '?'})")
            else:
                raise e
            return False
        except Exception as e:
            if not silent:
                print(f"\nRuntime Error: {str(e)}")
                import traceback
                traceback.print_exc()
            else:
                raise e
            return False

    def compile(self, entry_file: str, variables: Optional[Dict[str, Any]] = None) -> Any:
        """
        [NEW] 核心解耦：仅执行静态编译和语义分析，返回 CompilationArtifact。
        """
        abs_entry = os.path.abspath(entry_file)
        
        # 0. 预置符号到调度器
        if variables:
            from core.domain.symbols import STATIC_INT, STATIC_STR, STATIC_FLOAT, STATIC_BOOL, STATIC_ANY, VariableSymbol, SymbolKind
            static_vars = {}
            for name, val in variables.items():
                stype = STATIC_ANY
                if isinstance(val, bool): stype = STATIC_BOOL
                elif isinstance(val, int): stype = STATIC_INT
                elif isinstance(val, float): stype = STATIC_FLOAT
                elif isinstance(val, str): stype = STATIC_STR
                
                static_vars[name] = VariableSymbol(name=name, kind=SymbolKind.VARIABLE, var_type=stype)
            
            self.scheduler.predefined_symbols.update(static_vars)

        # 1. 调用调度器进行项目级编译
        self.debugger.trace(CoreModule.GENERAL, DebugLevel.BASIC, f"Compiling project: {abs_entry}")
        return self.scheduler.compile_project(abs_entry)

    def execute(self, artifact: Any, variables: Optional[Dict[str, Any]] = None, output_callback=None) -> bool:
        """执行编译后的蓝图"""
        self._prepare_interpreter(artifact, output_callback)
        
        # 1. 注入初始变量
        if variables:
            for name, val in variables.items():
                self.interpreter.context.define_variable(name, val)
        
        # 2. 从入口模块开始执行
        try:
            entry_module = self.interpreter.artifact_dict.get("entry_module")
            if not entry_module:
                return True
                
            module_data = self.interpreter.artifact_dict.get("modules", {}).get(entry_module)
            if not module_data:
                return True
                
            self.interpreter.execute_module(module_data["root_node_uid"], module_name=entry_module)
            return True
        except Exception as e:
            # 运行时异常已由解释器内部报告
            if not isinstance(e, InterpreterError):
                print(f"Internal engine error: {e}")
                import traceback
                traceback.print_exc()
            else:
                print(f"Runtime error: {e}")
            return False

    def get_variable(self, name: str) -> Any:
        """获取解释器上下文中的变量"""
        if self.interpreter and self.interpreter.context:
            val = self.interpreter.context.get_variable(name)
            # 自动进行 to_native 转换，以便外部调用者（如测试用例）直接使用 Python 原生值
            if hasattr(val, 'to_native'):
                return val.to_native()
            return val
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
