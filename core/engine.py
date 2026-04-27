import os
import importlib.util
import tempfile
import traceback
import copy
from typing import Optional, Dict, Any, List

# =============================================================================
# 架构边界说明：Engine = 组装者，不参与执行
# =============================================================================
# Engine 是 IBCI 运行环境的组装者（assembler）和入口点。
# 职责：创建 KernelRegistry、加载编译器和模块、注入 LLM Executor，
# 并将已组装的 Interpreter 交给调用方使用。
#
# Engine 本身不执行任何 IBCI 代码；执行发生在 Interpreter 内部。
# 多 Interpreter 并发（Layer 2，PENDING_TASKS_VM.md Step 11）由
# DynamicHost（HostService）负责调度，而非 Engine。
# =============================================================================

from core.project_detector import ProjectDetector

from core.kernel.registry import KernelRegistry
from core.compiler.scheduler import Scheduler
from core.runtime.interpreter.interpreter import Interpreter
from core.runtime.interpreter.runtime_context import RuntimeContextImpl
from core.runtime.factory import RuntimeObjectFactory
from core.runtime.module_system.discovery import ModuleDiscoveryService
from core.runtime.module_system.loader import ModuleLoader
from core.runtime.host.host_interface import HostInterface
from core.runtime.bootstrap.builtin_initializer import initialize_builtin_classes
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.compiler.diagnostics.formatter import DiagnosticFormatter
from core.compiler.serialization.serializer import FlatSerializer
from core.compiler.semantic.passes.semantic_analyzer import SemanticAnalyzer
from core.compiler.semantic.passes.contract_validator import ContractValidator
from core.kernel.blueprint import CompilationArtifact
from core.kernel.issue import CompilerError
from core.kernel.issue import InterpreterError
from core.kernel.symbols import VariableSymbol, SymbolKind
from core.kernel.spec import INT_SPEC, STR_SPEC, FLOAT_SPEC, BOOL_SPEC, ANY_SPEC
from core.base.diagnostics.debugger import CoreDebugger, CoreModule, DebugLevel
from core.runtime.interfaces import IInterpreterFactory, ServiceContext, IKernelOrchestrator
from core.runtime.interfaces import IExecutionContext
from core.runtime.rt_scheduler import RuntimeSchedulerImpl
from core.runtime.serialization.immutable_artifact import ImmutableArtifact
from core.runtime.capability_registry import CapabilityRegistry
from core.runtime.interfaces import IsolationLevel


from core.base.enums import RegistrationState

class IBCIEngine(IInterpreterFactory, IKernelOrchestrator):
    """
    IBC-Inter 标准化引擎，整合了调度、编译和执行流程。
    """
    def __init__(self, root_dir: Optional[str] = None, auto_sniff: bool = True, core_debug_config: Optional[Dict[str, str]] = None):
        self.registry = KernelRegistry()
        # STAGE 1 & 2 handled inside initialize_builtin_classes
        self._kernel_token = initialize_builtin_classes(self.registry)

        self.root_dir = os.path.abspath(root_dir or os.getcwd())
        self.issue_tracker = IssueTracker()
        self.debugger = CoreDebugger()

        # 0. 配置内核调试器
        if core_debug_config:
            self.debugger.configure(core_debug_config)
            self.debugger.trace(CoreModule.GENERAL, DebugLevel.BASIC, f"Core Debugger initialized with config: {core_debug_config}")

        # 同步输出回调到调试器，确保内核追踪能被捕获
        self.debugger.output_callback = None # 默认

        # 初始化能力注册中心
        self.capability_registry = CapabilityRegistry()

        # 1. 初始化模块发现服务 (内置路径 + 动态插件路径)
        builtin_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ibci_modules")

        # 自动检测项目插件路径
        project_plugin_paths = ProjectDetector.get_plugin_paths(self.root_dir)

        # 合并插件路径
        all_plugin_paths = project_plugin_paths.copy()
        if auto_sniff and project_plugin_paths:
            # 如果找到项目插件路径，使用它们
            search_paths = [builtin_path] + all_plugin_paths
        elif auto_sniff:
            # 如果未找到项目插件路径，使用默认的 root_dir/plugins
            default_plugins = os.path.join(self.root_dir, "plugins")
            if os.path.isdir(default_plugins):
                search_paths = [builtin_path, default_plugins]
            else:
                search_paths = [builtin_path]
        else:
            # 不自动嗅探
            search_paths = [builtin_path]

        self.discovery_service = ModuleDiscoveryService(search_paths)
        self.module_loader = ModuleLoader(search_paths, capability_registry=self.capability_registry)
        
        # 初始化并配置运行时对象工厂
        self.object_factory = RuntimeObjectFactory(self.registry)

        # 2. 延迟插件发现（Phase 2 显式引入原则）：
        #    在首次编译/静态检查时才调用 discover_all()，而非在 Engine 初始化时无条件加载。
        #    这确保插件元数据只在真正需要（编译）时才注入 MetadataRegistry，
        #    使"必须 import ai 才能使用"的语义清晰度在 Engine 生命周期内保持一致。
        #    调用入口：_ensure_plugins_discovered()，由 compile() 和 check() 在开始前触发。
        self.host_interface = HostInterface()  # 空接口，将在首次编译前填充
        self._plugins_discovered = False

        # [Strict Registry] Scheduler/SemanticAnalyzer require MetadataRegistry, not the container Registry
        self.scheduler = Scheduler(self.root_dir, host_interface=self.host_interface, debugger=self.debugger, issue_tracker=self.issue_tracker, registry=self.registry.get_metadata_registry())
        
        # 初始化运行时调度器
        self.rt_scheduler = RuntimeSchedulerImpl(None) # 此时 ServiceContext 尚未就绪，将在后续注入
        
        self.interpreter: Optional[Interpreter] = None

    def spawn_interpreter(self, artifact: Any, registry: Any, host_interface: Any, root_dir: str, parent_context: Any, isolated: bool = False, entry_file: str = None, entry_dir: str = None) -> Interpreter:
        """[IInterpreterFactory] 实现工厂方法产生子解释器"""
        instance_id = self.rt_scheduler.spawn(
            artifact=artifact,
            isolation=IsolationLevel.SCOPE if isolated else IsolationLevel.NONE,
            registry=registry,
            host_interface=host_interface,
            root_dir=root_dir,
            factory=self,
            object_factory=self.object_factory,
            plugin_loader=self._load_plugins,
            kernel_token=self._kernel_token,
            issue_tracker=self.issue_tracker,
            output_callback=self.debugger.output_callback,
            input_callback=None,
            entry_file=entry_file,
            entry_dir=entry_dir
        )
        return self.rt_scheduler.instances[instance_id]

    def _prepare_interpreter(self, artifact: Optional[Any] = None, output_callback=None):
        """初始化解释器并动态加载模块实现"""
        self.interpreter = self.spawn_interpreter(
            artifact=artifact,
            registry=self.registry,
            host_interface=self.host_interface,
            root_dir=self.root_dir,
            parent_context=None,
            isolated=False,
            entry_file=getattr(self, '_entry_file', None),
            entry_dir=getattr(self, '_entry_dir', None)
        )
        
        # Post-construction wiring: inject orchestrator and output_callback into ServiceContext.
        # This is intentional deferred injection — Engine is the orchestrator, but it can only
        # inject itself after the interpreter is fully constructed.
        if hasattr(self.interpreter, 'service_context'):
            self.interpreter.service_context.set_orchestrator(self)
            if output_callback is not None:
                self.interpreter.service_context.output_callback = output_callback
        
        # 统一装配调度器与能力注册中心
        service_context = self.interpreter.service_context
        self.rt_scheduler.hydrate(service_context)
        
        # 设定主实例 ID
        self.rt_scheduler._main_instance_id = self.interpreter.instance_id
        
        if hasattr(service_context, '_scheduler'):
            setattr(service_context, '_scheduler', self.rt_scheduler)
        if hasattr(service_context, '_capability_registry'):
            setattr(service_context, '_capability_registry', self.capability_registry)
        
        # STAGE 7: 深度契约校验与就绪
        # 强制检查状态流转，确保 STAGE 6 (预评估) 已完成
        if self.registry.state_level < RegistrationState.STAGE_6_PRE_EVAL.value:
             self.registry.set_state_level(RegistrationState.STAGE_6_PRE_EVAL.value, self._kernel_token)

        validator = ContractValidator(self.registry.get_metadata_registry(), self.issue_tracker, self.debugger)
        validator.validate_all()
        
        # 如果校验过程中发现了严重契约冲突，则阻止系统进入 READY 状态
        if self.issue_tracker.has_errors():
             raise InterpreterError("System readiness failed: Global Contract Violation detected in STAGE 7.", None)

        self.registry.set_state_level(RegistrationState.STAGE_7_READY.value, self._kernel_token)
        # 封印类注册表
        self.registry.seal_classes(self._kernel_token)

        # 将 LLM 执行器注入 KernelRegistry，使 IbBehavior.call() 可通过公理体系自主执行
        llm_executor = getattr(self.interpreter.service_context, 'llm_executor', None)
        if llm_executor is not None:
            self.registry.register_llm_executor(llm_executor, self._kernel_token)

        # 将宿主服务、调用栈内省器、状态读取器注入 KernelRegistry
        # 供核心层插件（ibci_ihost、ibci_idbg）通过稳定钩子接口访问，替代直接持有 ServiceContext
        host_service = getattr(self.interpreter.service_context, 'host_service', None)
        if host_service is not None:
            self.registry.register_host_service(host_service, self._kernel_token)

        stack_inspector = getattr(self.interpreter._execution_context, 'stack_inspector', None)
        if stack_inspector is not None:
            self.registry.register_stack_inspector(stack_inspector, self._kernel_token)

        state_reader = self.interpreter.runtime_context
        if state_reader is not None:
            self.registry.register_state_reader(state_reader, self._kernel_token)

    def _load_plugins(self, service_context: ServiceContext, execution_context: IExecutionContext, intrinsic_manager: Any):
        """ 驱动插件加载生命周期 (STAGE 4 -> STAGE 5)

         在插件实现加载前，先加载插件公理（如果提供了 __ibcext_axiom__）。
        这确保自定义公理能在封印前注册到 AxiomRegistry。
        """
        from core.extension.auto_discovery import AutoDiscoveryService

        self.registry.set_state_level(RegistrationState.STAGE_4_PLUGIN_IMPL.value, self._kernel_token)

        builtin_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ibci_modules")
        plugins_path = os.path.join(self.root_dir, "plugins")
        discovery = AutoDiscoveryService([builtin_path, plugins_path])

        axiom_registry = self.registry.get_metadata_registry().get_axiom_registry()
        if axiom_registry:
            for spec in discovery.discover_plugins().values():
                if spec.has_axioms():
                    for name, axiom in spec.axioms.items():
                        try:
                            axiom_registry.register(axiom)
                        except Exception as e:
                            pass

        self.module_loader.load_and_register_all(service_context, execution_context)

        self.registry.set_state_level(RegistrationState.STAGE_5_HYDRATION.value, self._kernel_token)

    def register_native_module(self, name: str, implementation: Any, type_metadata: Optional[Any] = None):
        """
         显式注册一个原生 Python 模块实现及其元数据。
        """
        self.host_interface.register_module(name, implementation, type_metadata)
        self.scheduler.host_interface = self.host_interface

    def _ensure_plugins_discovered(self) -> None:
        """
        确保插件元数据已加载到 host_interface（懒加载，只在首次编译/检查时触发）。

        Phase 2 显式引入原则：discover_all() 不在 Engine.__init__() 中无条件调用，
        而是延迟到首次编译时才执行。这确保：
        1. 仅创建 Engine 实例而不编译时，不触发任何插件发现。
        2. Scheduler 在编译开始前获得完整的 host_interface（含所有插件元数据）。
        3. 插件符号仍须通过 import 语句显式引入才能在代码中使用（Phase 1 的 Prelude 过滤保证）。
        """
        if not self._plugins_discovered:
            self.host_interface = self.discovery_service.discover_all(self.registry)
            self.scheduler.host_interface = self.host_interface
            self._plugins_discovered = True

    def compile_string(self, code: str, variables: Optional[Dict[str, Any]] = None, silent: bool = False) -> CompilationArtifact:
        """
         编译一段 IBCI 代码字符串，返回蓝图。
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
                tracker = self.scheduler.issue_tracker
                print(f"\nCompilation failed: {tracker.error_count} errors, {tracker.warning_count} warnings.")
            raise e
        except Exception as e:
            if not silent:
                print(f"\nRuntime Error: {str(e)}")
            raise e

    def run(self, entry_file: str, variables: Optional[Dict[str, Any]] = None, output_callback=None, silent: bool = False, prepare_interpreter: bool = True) -> bool:
        self._entry_file = os.path.abspath(entry_file)
        self._entry_dir = os.path.dirname(self._entry_file)
        abs_entry = self._entry_file

        if output_callback:
            self.debugger.output_callback = output_callback

        if not os.path.exists(abs_entry):
            if not silent:
                print(f"Error: Entry file not found: {abs_entry}")
            return False

        try:
            artifact = self.compile(abs_entry, variables, silent=silent)

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
         核心解耦：仅执行静态编译和语义分析，返回 CompilationArtifact。
        """
        # 懒加载插件元数据（Phase 2 显式引入原则）
        self._ensure_plugins_discovered()

        if not hasattr(self, '_entry_file'):
            self._entry_file = os.path.abspath(entry_file)
            self._entry_dir = os.path.dirname(self._entry_file)
        abs_entry = self._entry_file
        
        # 同步静默状态到调试器
        self.debugger.silent = silent
        
        # 0. 预置符号到调度器
        if variables:
            static_vars = {}
            for name, val in variables.items():
                stype = ANY_SPEC
                if isinstance(val, bool): stype = BOOL_SPEC
                elif isinstance(val, int): stype = INT_SPEC
                elif isinstance(val, float): stype = FLOAT_SPEC
                elif isinstance(val, str): stype = STR_SPEC
                
                static_vars[name] = VariableSymbol(name=name, kind=SymbolKind.VARIABLE, spec=stype)
            
            self.scheduler.predefined_symbols.update(static_vars)

        # 1. 调用调度器进行项目级编译
        self.debugger.trace(CoreModule.GENERAL, DebugLevel.BASIC, f"Compiling project: {abs_entry}")
        
        return self.scheduler.compile_project(abs_entry)

    def execute(self, artifact: CompilationArtifact, variables: Optional[Dict[str, Any]] = None, output_callback=None) -> bool:
        """
         调度入口。执行编译产物。
        注意：如果引擎已经处于 READY 状态，调用此方法将抛出状态冲突错误。建议每个执行流创建新的引擎实例。
        """
        serializer = FlatSerializer()
        artifact_dict = serializer.serialize_artifact(artifact)

        # [P2-D] 包装为 ImmutableArtifact，防止解释器修改 artifact
        immutable_artifact = ImmutableArtifact(artifact_dict)

        # 强制重置或重新准备解释器
        # 理由：Registry 封印后，无法再次加载不同的 Artifact
        if self.registry.is_sealed:
             raise PermissionError("Engine: Cannot execute new artifact on a sealed registry. Create a new Engine instance.")

        if not self.interpreter:
            self._prepare_interpreter(immutable_artifact, output_callback=output_callback)
        
        # 委派执行权给运行时调度器
        # 目前调度器内部仍然通过 Engine 的准备机制来启动解释器
        # 但从宏观视角看，Engine 已经不再直接驱动 Interpreter
        return self.rt_scheduler.execute(immutable_artifact, variables=variables, output_callback=output_callback)

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

    def check(self, entry_file: str, silent: bool = False) -> bool:
        """
        仅对项目进行静态检查（编译和语义分析）。
        """
        # 懒加载插件元数据（Phase 2 显式引入原则）
        self._ensure_plugins_discovered()

        abs_entry = os.path.abspath(entry_file)
        try:
            self.scheduler.compile_project(abs_entry)
            if not silent:
                print(f"Check successful: {entry_file}")
            return True
        except CompilerError as e:
            if not silent:
                print("\n--- Compilation Errors ---")
                print(DiagnosticFormatter.format_all(e.diagnostics, source_manager=self.scheduler.source_manager))
                print(f"Check failed: {entry_file}")
            return False

    def resolve_semantics(self, module: Any, raise_on_error: bool = True, analyzer: Optional[Any] = None):
        """
         暴露分段语义分析接口，允许观察中间产物。
        按顺序运行 Pass 1 (Collector), Pass 2 (Resolver), Pass 3 (Analyzer)。
        """
        if analyzer is None:
            # 构造分析器
            analyzer = SemanticAnalyzer(
                issue_tracker=self.issue_tracker, 
                registry=self.registry.get_metadata_registry(),
                debugger=self.debugger
            )
        
        # 内部执行完整的 3-Pass 分析流
        analyzer.analyze(module, raise_on_error=raise_on_error)
        
        return analyzer

    def request_isolated_run(self, entry_path: str, policy: Dict[str, Any], initial_vars: Optional[Dict[str, Any]] = None) -> bool:
        """
        [IKernelOrchestrator] 处理来自运行时的隔离执行系统调用。
        核心逻辑：启动一个全新的 Engine 实例，实现编译与运行的完全隔离。
        """
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Handling kernel system call: request_isolated_run -> {entry_path}")
        
        # 1. 决定子项目的 target_proj_root (永远等于入口文件所在目录)
        abs_path = os.path.abspath(entry_path)
        sub_root_dir = os.path.dirname(abs_path)
        
        # 2. 实例化全新的 Engine
        # 这将触发全新的插件发现 (基于 sub_root_dir/plugins) 和注册表水合
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Bootstrapping new Engine instance for sub-project root: {sub_root_dir}")
        sub_engine = IBCIEngine(
            root_dir=sub_root_dir,
            auto_sniff=True,
            core_debug_config=self.debugger.config # 继承调试配置
        )
        
        # 3. 运行子项目
        # 将 policy 中的 inherit_variables 提取的初始状态作为 CLI vars 注入子项目
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Running isolated artifact...")
        success = sub_engine.run(abs_path, variables=initial_vars)
        
        return success
