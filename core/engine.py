import os
import importlib.util
import tempfile
import traceback
from typing import Optional, Dict, Any

from core.foundation.registry import Registry
from core.compiler.scheduler import Scheduler
from core.runtime.interpreter.interpreter import Interpreter
from core.runtime.interpreter.service_context import ServiceContextImpl
from core.runtime.interpreter.runtime_context import RuntimeContextImpl
from core.runtime.interpreter.module_manager import ModuleManagerImpl
from core.runtime.interpreter.interop import InterOpImpl
from core.runtime.interpreter.llm_executor import LLMExecutorImpl
from core.runtime.interpreter.permissions import PermissionManager as PermissionManagerImpl
from core.runtime.interpreter.factory import RuntimeObjectFactory
from core.runtime.module_system.discovery import ModuleDiscoveryService
from core.runtime.module_system.loader import ModuleLoader
from core.foundation.host_interface import HostInterface
from core.runtime.bootstrap.builtin_initializer import initialize_builtin_classes
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.compiler.diagnostics.formatter import DiagnosticFormatter
from core.compiler.serialization.serializer import FlatSerializer
from core.compiler.semantic.passes.semantic_analyzer import SemanticAnalyzer
from core.domain.types import ModuleMetadata
from core.domain.blueprint import CompilationArtifact
from core.domain.issue import CompilerError
from core.domain.issue import InterpreterError, LexerError, ParserError, SemanticError
from core.domain.symbols import VariableSymbol, SymbolKind
from core.domain.types.descriptors import (
    INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR, 
    BOOL_DESCRIPTOR, ANY_DESCRIPTOR
)
from core.foundation.diagnostics.core_debugger import CoreDebugger, CoreModule, DebugLevel
from core.runtime.interfaces import IInterpreterFactory, ServiceContext
from core.foundation.interfaces import IExecutionContext


from core.runtime.enums import RegistrationState

class IBCIEngine(IInterpreterFactory):
    """
    IBC-Inter 标准化引擎，整合了调度、编译和执行流程。
    """
    def __init__(self, root_dir: Optional[str] = None, auto_sniff: bool = True, core_debug_config: Optional[Dict[str, str]] = None):
        self.registry = Registry()
        # STAGE 1 & 2 handled inside initialize_builtin_classes
        self._kernel_token = initialize_builtin_classes(self.registry)
        
        self.root_dir = os.path.abspath(root_dir or os.getcwd())
        self.issue_tracker = IssueTracker()
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
        self.host_interface = self.discovery_service.discover_all(self.registry)
        
        # [Strict Registry] Scheduler/SemanticAnalyzer require MetadataRegistry, not the container Registry
        self.scheduler = Scheduler(self.root_dir, host_interface=self.host_interface, debugger=self.debugger, issue_tracker=self.issue_tracker, registry=self.registry.get_metadata_registry())
        
        self.interpreter: Optional[Interpreter] = None

    def spawn_interpreter(self, artifact: Any, registry: Any, host_interface: Any, root_dir: str, parent_context: Any) -> Interpreter:
        """[IInterpreterFactory] 实现工厂方法产生子解释器"""
        # [IES 2.0] 彻底透传副作用回调
        sub_interpreter = Interpreter(
            issue_tracker=self.issue_tracker,
            artifact=artifact, 
            registry=registry,
            host_interface=host_interface,
            output_callback=self.interpreter.output_callback if self.interpreter else None,
            input_callback=getattr(self.interpreter, 'input_callback', None) if self.interpreter else None,
            source_provider=self.scheduler.source_manager,
            compiler=self.scheduler,
            root_dir=root_dir,
            factory=self, # 注入自己作为工厂
            plugin_loader=self._load_plugins # 注入生命周期钩子
        )
        # 加载插件已由 plugin_loader 完成
        return sub_interpreter

    def _prepare_interpreter(self, artifact: Optional[Any] = None, output_callback=None):
        """初始化解释器并动态加载模块实现"""
        # [IES 2.0] 彻底消除后期注入，构造期完成依赖图谱闭合
        self.interpreter = Interpreter(
            self.issue_tracker, 
            output_callback=output_callback,
            artifact=artifact, 
            host_interface=self.host_interface,
            debugger=self.debugger,
            root_dir=self.root_dir,
            registry=self.registry,
            source_provider=self.scheduler.source_manager,
            compiler=self.scheduler,
            factory=self,
            plugin_loader=self._load_plugins # 注入生命周期钩子
        )
        
        # [IES 2.0 Transition] STAGE 6: 准备就绪
        self.registry.set_state_level(RegistrationState.STAGE_6_READY.value, self._kernel_token)
        # 封印类注册表
        self.registry.seal_classes(self._kernel_token)

    def _load_plugins(self, service_context: ServiceContext, execution_context: IExecutionContext, intrinsic_manager: Any):
        """[IES 2.0] 驱动插件加载生命周期 (STAGE 4 -> STAGE 5)"""
        # 1. 进入插件加载阶段
        self.registry.set_state_level(RegistrationState.STAGE_4_PLUGIN_IMPL.value, self._kernel_token)
        
        # 2. 统一由 ModuleLoader 驱动实现层的加载与注入
        self.module_loader.load_and_register_all(service_context, execution_context)
        
        # 3. 插件加载完成，进入水合阶段
        self.registry.set_state_level(RegistrationState.STAGE_5_HYDRATION.value, self._kernel_token)

    def register_plugin(self, name: str, implementation: Any, type_metadata: Optional[ModuleMetadata] = None):
        """
        手动注册插件（兼容旧模式，但建议使用 plugins/ 目录下的双文件协议）。
        """
        self.host_interface.register_module(name, implementation, type_metadata)
        self.scheduler.host_interface = self.host_interface

    def compile_string(self, code: str, variables: Optional[Dict[str, Any]] = None, silent: bool = False) -> CompilationArtifact:
        """
        [NEW] 编译一段 IBCI 代码字符串，返回蓝图。
        """
        # Use system temp directory but explicitly allow this file in scheduler
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ibci', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_path = f.name
        
        try:
            self.scheduler.allow_file(temp_path)
            return self.compile(temp_path, variables, silent=silent)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def run_string(self, code: str, variables: Optional[Dict[str, Any]] = None, output_callback=None, silent: bool = False, prepare_interpreter: bool = True) -> bool:
        """
        运行一段 IBCI 代码字符串。
        """
        try:
            artifact = self.compile_string(code, variables, silent=silent)
            if prepare_interpreter:
                return self.execute(artifact, variables, output_callback)
            return True
        except CompilerError as e:
            if not silent:
                print("\n--- Compilation Errors ---")
                print(DiagnosticFormatter.format_all(e.diagnostics, source_manager=self.scheduler.source_manager))
            raise e # 统一向上抛出，由调用者决定是否处理

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
            artifact = self.compile(abs_entry, variables, silent=silent)
            
            # 2. 执行阶段 (可选)
            if prepare_interpreter:
                return self.execute(artifact, variables, output_callback)
            
            return True

        except CompilerError as e:
            if not silent:
                print("\n--- Compilation Errors ---")
                print(DiagnosticFormatter.format_all(e.diagnostics, source_manager=self.scheduler.source_manager))
                
                # Use tracker counts if available
                tracker = self.scheduler.issue_tracker
                print(f"\nCompilation failed: {tracker.error_count} errors, {tracker.warning_count} warnings.")
            raise e
        except Exception as e:
            if not silent:
                print(f"\nRuntime Error: {str(e)}")
            raise e

    def compile(self, entry_file: str, variables: Optional[Dict[str, Any]] = None, silent: bool = False) -> Any:
        """
        [NEW] 核心解耦：仅执行静态编译和语义分析，返回 CompilationArtifact。
        """
        abs_entry = os.path.abspath(entry_file)
        
        # 同步静默状态到调试器
        self.debugger.silent = silent
        
        # 0. 预置符号到调度器
        if variables:
            static_vars = {}
            for name, val in variables.items():
                stype = ANY_DESCRIPTOR
                if isinstance(val, bool): stype = BOOL_DESCRIPTOR
                elif isinstance(val, int): stype = INT_DESCRIPTOR
                elif isinstance(val, float): stype = FLOAT_DESCRIPTOR
                elif isinstance(val, str): stype = STR_DESCRIPTOR
                
                static_vars[name] = VariableSymbol(name=name, kind=SymbolKind.VARIABLE, descriptor=stype)
            
            self.scheduler.predefined_symbols.update(static_vars)

        # 1. 调用调度器进行项目级编译
        self.debugger.trace(CoreModule.GENERAL, DebugLevel.BASIC, f"Compiling project: {abs_entry}")
        
        return self.scheduler.compile_project(abs_entry)

    def execute(self, artifact: CompilationArtifact, variables: Optional[Dict[str, Any]] = None, output_callback=None) -> bool:
        """
        [IES 2.0] 调度入口。执行编译产物。
        注意：如果引擎已经处于 READY 状态，调用此方法将抛出状态冲突错误。建议每个执行流创建新的引擎实例。
        """
        serializer = FlatSerializer()
        artifact_dict = serializer.serialize_artifact(artifact)
        
        # 强制重置或重新准备解释器
        # 理由：Registry 封印后，无法再次加载不同的 Artifact
        if self.registry.is_sealed:
             raise PermissionError("Engine: Cannot execute new artifact on a sealed registry. Create a new Engine instance.")

        if not self.interpreter:
            self._prepare_interpreter(artifact_dict, output_callback=output_callback)
        
        # 1. 注入初始变量
        if variables:
            for name, val in variables.items():
                self.interpreter.runtime_context.define_variable(name, val)
        
        # 2. 启动执行
        return self.interpreter.run()

    def set_variable(self, name: str, val: Any):
        """[Engine API] 向当前解释器环境注入变量"""
        if self.interpreter:
            if not hasattr(val, 'ib_class'):
                val = self.interpreter.registry.box(val)
            if self.interpreter.runtime_context:
                self.interpreter.runtime_context.define_variable(name, val)

    def get_variable(self, name: str) -> Any:
        """[Engine API] 从当前解释器环境获取变量"""
        if self.interpreter and self.interpreter.runtime_context:
            val = self.interpreter.runtime_context.get_variable(name)
            return val
        return None

    def check(self, entry_file: str) -> bool:
        """
        仅对项目进行静态检查（编译和语义分析）。
        """
        abs_entry = os.path.abspath(entry_file)
        try:
            self.scheduler.compile_project(abs_entry)
            print(f"Check successful: {entry_file}")
            return True
        except CompilerError as e:
            print("\n--- Compilation Errors ---")
            print(DiagnosticFormatter.format_all(e.diagnostics, source_manager=self.scheduler.source_manager))
            print(f"Check failed: {entry_file}")
            return False

    def resolve_semantics(self, module: Any, raise_on_error: bool = True, analyzer: Optional[Any] = None):
        """
        [NEW] 暴露分段语义分析接口，允许观察中间产物。
        按顺序运行 Pass 1 (Collector), Pass 2 (Resolver), Pass 3 (Analyzer)。
        """
        if analyzer is None:
            # 构造分析器
            analyzer = SemanticAnalyzer(
                issue_tracker=self.issue_tracker, 
                registry=self.registry.get_metadata_registry(),
                debugger=self.debugger,
                host_interface=self.host_interface
            )
        
        # 内部执行完整的 3-Pass 分析流
        analyzer.analyze(module, raise_on_error=raise_on_error)
        
        return analyzer
