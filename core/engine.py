import os
import importlib.util
import tempfile
import traceback
from typing import Optional, Dict, Any

from core.foundation.registry import Registry
from core.compiler.scheduler import Scheduler
from core.runtime.interpreter.interpreter import Interpreter, ServiceContextImpl
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
from core.runtime.interfaces import IInterpreterFactory


from core.foundation.registry import Registry, RegistrationState

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
        
        # [IES 2.0 Transition] STAGE 3: 发现并加载元数据
        self.registry.set_state(RegistrationState.STAGE_3_PLUGIN_METADATA, self._kernel_token)
        
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
            factory=self # 注入自己作为工厂
        )
        # 加载插件
        self.module_loader.load_and_register_all(sub_interpreter.service_context)
        return sub_interpreter

    def _prepare_interpreter(self, artifact: Optional[Any] = None, output_callback=None):
        """初始化解释器并动态加载模块实现"""
        # [IES 2.0 Transition] STAGE 4: 加载插件实现层
        self.registry.set_state(RegistrationState.STAGE_4_PLUGIN_IMPL, self._kernel_token)
        
        # 1. 预先初始化 ServiceContext 需要的部分组件（如 InterOp）以供插件加载
        # 这里我们需要先创建一个简易的 ServiceContext，或者重构 ModuleLoader 使其不强依赖 Interpreter 实例
        # 考虑到 load_and_register_all 需要 ServiceContext，我们先创建一个空的解释器外壳或者提前准备好 context
        
        # [IES 2.0] 创建一个临时 context 用于插件初始化
        # 插件在初始化阶段可能需要 registry 和 host_interface
        interop = InterOpImpl(host_interface=self.host_interface)
        
        # [IES 2.0] 创建统一的 RuntimeContext 以供插件和解释器共享
        runtime_context = RuntimeContextImpl(registry=self.registry)
        
        # [IES 2.0] 初始化运行时对象工厂
        object_factory = RuntimeObjectFactory(registry=self.registry)
        
        service_context = ServiceContextImpl(
            self.issue_tracker,
            runtime_context,
            LLMExecutorImpl(),
            ModuleManagerImpl(interop, artifact=artifact, root_dir=self.root_dir, object_factory=object_factory),
            interop,
            PermissionManagerImpl(self.root_dir),
            None, # interpreter
            self.registry,
            object_factory,
            source_provider=self.scheduler.source_manager,
            compiler=self.scheduler,
            debugger=self.debugger
        )
        
        # 统一由 ModuleLoader 驱动实现层的加载与注入
        self.module_loader.load_and_register_all(service_context)
        
        # [IES 2.0 Transition] STAGE 5: 执行用户产物重水合
        self.registry.set_state(RegistrationState.STAGE_5_HYDRATION, self._kernel_token)

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
            factory=self, # 注入自己作为工厂
            interop=interop,
            runtime_context=runtime_context # 传入共享的 context
        )
        
        # [IES 2.0 Transition] STAGE 6: 准备就绪
        self.registry.set_state(RegistrationState.STAGE_6_READY, self._kernel_token)
        # 封印类注册表
        self.registry.seal_classes(self._kernel_token)

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
        """执行编译后的蓝图"""
        # 1. 序列化蓝图为字典池 (这是解释器要求的格式)
        serializer = FlatSerializer()
        artifact_dict = serializer.serialize_artifact(artifact)
        
        self._prepare_interpreter(artifact_dict, output_callback)
        
        # 1. 注入初始变量
        if variables:
            for name, val in variables.items():
                self.interpreter.context.define_variable(name, val)
        
        # 2. 启动执行
        return self.interpreter.run()

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
