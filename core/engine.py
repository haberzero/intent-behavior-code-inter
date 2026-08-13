import os
import importlib.util
import tempfile
import traceback
import copy
import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple, Union

# =============================================================================
# 架构边界说明：Engine = 组装者，不参与执行
# =============================================================================
# Engine 是 IBCI 运行环境的组装者（assembler）和入口点。
# 职责：创建 KernelRegistry、加载编译器和模块、注入 LLM Executor，
# 并将已组装的 Interpreter 交给调用方使用。
#
# Engine 本身不执行任何 IBCI 代码；执行发生在 Interpreter 内部。
# 多 Interpreter 并发（Layer 2）由
# DynamicHost（HostService）负责调度，而非 Engine。
# =============================================================================

from core.project_detector import ProjectDetector

from core.kernel.path import IbPath, PathContext, PathValidator
from core.kernel.config import IbciConfig
from core.runtime.path import InstallPaths
from core.kernel.registry import KernelRegistry
from core.compiler.scheduler import Scheduler
from core.runtime.interpreter.interpreter import Interpreter
from core.runtime.interpreter.runtime_context import RuntimeContextImpl
from core.runtime.objects.kernel import IbObject
from core.runtime.factory import RuntimeObjectFactory
from core.runtime.module_system.discovery import ModuleDiscoveryService
from core.runtime.module_system.loader import ModuleLoader
from core.kernel.host_interface import HostInterface
from core.runtime.bootstrap.primitive_initializer import initialize_primitive_classes
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.compiler.diagnostics.formatter import DiagnosticFormatter
from core.compiler.serialization.serializer import FlatSerializer
from core.compiler.semantic.passes.contract_validator import ContractValidator
from core.kernel.blueprint import CompilationArtifact
from core.kernel.issue import CompilerError
from core.kernel.issue import InterpreterError
from core.kernel.symbols import VariableSymbol, SymbolKind
from core.kernel.spec import INT_SPEC, STR_SPEC, FLOAT_SPEC, BOOL_SPEC, ANY_SPEC, TypeDef, MethodMemberSpec, TypeRef, TypeKind, ParamDescriptor
from core.runtime.interfaces import IInterpreterFactory, ServiceContext, IKernelOrchestrator
from core.runtime.interfaces import IExecutionContext
from core.runtime.host.isolation_policy import IsolationPolicy
from core.runtime.rt_scheduler import RuntimeSchedulerImpl
from core.runtime.serialization.immutable_artifact import ImmutableArtifact
from core.runtime.capability_registry import CapabilityRegistry
from core.runtime.observability.events import EventBus
from core.runtime.observability.diagnostics import kernel_diagnostic
from core.base.diagnostics.codes import KDIAG_RUNTIME_COLLECT_SKIP
from core.extension.auto_discovery import AutoDiscoveryService


from core.base.enums import RegistrationState, Provenance, Visibility

# collect() 时跳过的 IBCI 类型名集合（函数/行为/可调用实例等不可序列化为原生 Python 值）
_COLLECT_SKIP_TYPES: frozenset = frozenset({
    "fn", "lambda", "snapshot", "behavior", "fn_callable", "callable", "void",
})


@dataclass(frozen=True)
class EngineTestSnapshot:
    """引擎可观测状态快照（测试内省用，只读，替代私有字段穿透）。

    字段均为引擎生命周期事实的只读投影：
    - ``explicit_root``    —— 构造期显式 root（canonicalize 后；未提供为 None）
    - ``cwd``              —— 构造期 CWD
    - ``entry_file``       —— 当前 entry 锚点（run/compile_string 确立后非 None）
    - ``entry_dir``        —— PathContext.entry_dir 原生字符串（未确立为 None）
    - ``project_root``     —— PathContext.project_root 原生字符串（未确立为 None）
    - ``plugin_search_paths`` —— 当前插件搜索路径（root 确立后有效）
    - ``install_path``     —— kernel-native 模块目录
    - ``root_initialized`` —— root-dependent 初始化是否完成
    - ``spawned_handles``  —— 在途隔离 spawn 任务句柄（锁内快照）
    """

    explicit_root: Optional[str] = None
    cwd: str = ""
    entry_file: Optional[str] = None
    entry_dir: Optional[str] = None
    project_root: Optional[str] = None
    plugin_search_paths: List[str] = field(default_factory=list)
    install_path: str = ""
    root_initialized: bool = False
    spawned_handles: List[str] = field(default_factory=list)


class IBCIEngine(IInterpreterFactory, IKernelOrchestrator):
    """
    IBC-Inter 标准化引擎，整合了调度、编译和执行流程。
    """
    def __init__(self, root_dir: Optional[str] = None, auto_sniff: bool = True, inherited_plugin_paths: Optional[List[str]] = None, inherited_global_plugin: Optional[List[str]] = None):
        """
        参数:
            root_dir: **可选**。项目根目录（沙箱边界）。
                引擎级默认——未提供时，project_root 在 run()/compile() 时
                确立为 entry_file 所在目录（entry_dir）。run_string 无真实 entry，须显式提供。
                提供时经 canonicalize_for_security 规范化。
            auto_sniff: 是否自动嗅探项目插件路径（plugin 发现优先级见 resolve_plugin_search_paths）。

        多阶段启动：__init__ 仅做 root-independent 设置（KernelRegistry/CWD/install 路径等）；
        root-dependent 设置（plugin 发现路径、Scheduler）延迟到 ``_ensure_root_initialized``，
        在 run/compile/check 时经 ``_establish_project_root`` 确立 project_root 后触发。
        """
        # --- root-independent ---
        self.registry = KernelRegistry()
        self._kernel_token = initialize_primitive_classes(self.registry)

        # 注入引擎级共享事件总线（runtime 观测设施由组装层创建注入；
        # 所有 interpreter/子引擎/线程任务共享，计算隔离、观测全局）。
        self.registry.set_event_bus(EventBus())

        # project_root：显式（可选）。未提供时在 run/compile 经 _establish_project_root 确立。
        self._explicit_root: Optional[str] = (
            PathValidator.canonicalize_for_security(root_dir).to_native() if root_dir else None
        )
        # CWD：单独保存（无上界校验）；子脚本可获取。使用待权限系统。
        self._cwd: str = os.getcwd()

        # PathContext（entry_dir + project_root 锚点容器）：run/compile 时确立。
        self._path_ctx: Optional[PathContext] = None
        self._entry_file: Optional[str] = None

        self.issue_tracker = IssueTracker()
        # 执行输出回调（run() 时记录，spawn 子解释器时透传）
        self._output_callback: Optional[Any] = None
        # 测试钩子（服务上下文创建后注入；生产为 None）
        self._test_hooks: Optional[Any] = None

        # 初始化能力注册中心
        self.capability_registry = CapabilityRegistry()

        # 内核原生模块目录（恒在，单独存储，不配置不隔离）
        self._install_path: str = InstallPaths.modules_dir().to_native()

        # 运行时对象工厂
        self.object_factory = RuntimeObjectFactory(self.registry)

        # host_interface 与引擎共享 MetadataRegistry，确保构造期预注册的
        # kernel-native 模块元数据对编译器可见。
        self.host_interface = HostInterface(external_registry=self.registry.get_metadata_registry())
        # 注入诊断发射器（kernel 层不依赖 runtime；经注入的 kernel_diagnostic
        # 发射覆盖站点的警告+事件双投影）。
        self.host_interface.set_diagnostic_emitter(kernel_diagnostic)
        # 预注册 ai/ihost/idbg/isys 为 kernel-native 模块
        from core.runtime.bootstrap.kernel_native_modules import register_kernel_native_modules
        register_kernel_native_modules(self.host_interface)

        # 注册 file 为 kernel-native 模块。
        from core.runtime.modules.file_impl import FileLib
        _FILE_MODULE_SPEC = TypeDef(
            name="file",
            kind=TypeKind.MODULE.value,
            provenance=Provenance.KERNEL_NATIVE,
            visibility=Visibility.IMPORT_GATED,
            # `import file` also gates the disk-backed types into scope.
            exported_types=["file_handle", "audio", "image", "video"],
            members={
                "open": MethodMemberSpec(
                    name="open", kind="method", type_ref=TypeRef.of("file_handle"),
                    param_types=[TypeRef.of("str")], return_type=TypeRef.of("file_handle"),
                ),
                "read": MethodMemberSpec(
                    name="read", kind="method", type_ref=TypeRef.of("str"),
                    param_types=[TypeRef.of("any")], return_type=TypeRef.of("str"),
                ),
                "read_bytes": MethodMemberSpec(
                    name="read_bytes", kind="method", type_ref=TypeRef.generic("list", TypeRef.of("int")),
                    param_types=[TypeRef.of("any")], return_type=TypeRef.generic("list", TypeRef.of("int")),
                ),
                "write": MethodMemberSpec(
                    name="write", kind="method", type_ref=TypeRef.of("file_handle"), mutating=True,
                    param_types=[TypeRef.of("any"), TypeRef.of("any"), TypeRef.of("str")],
                    return_type=TypeRef.of("file_handle"),
                    param_descriptors=[
                        ParamDescriptor(name="target", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any")),
                        ParamDescriptor(name="data", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("any")),
                        ParamDescriptor(name="overwrite_flag", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str"), has_default=True, default_value="new"),
                    ],
                ),
                "exists": MethodMemberSpec(
                    name="exists", kind="method", type_ref=TypeRef.of("bool"),
                    param_types=[TypeRef.of("str")], return_type=TypeRef.of("bool"),
                ),
                "remove": MethodMemberSpec(
                    name="remove", kind="method", type_ref=TypeRef.of("void"), mutating=True,
                    param_types=[TypeRef.of("any")], return_type=TypeRef.of("void"),
                ),
            },
        )
        self.host_interface.register_module("file", FileLib(), metadata=_FILE_MODULE_SPEC)
        self.host_interface.reserve_kernel_native_name("file")

        self._plugins_discovered = False

        # 运行时调度器
        self.rt_scheduler = RuntimeSchedulerImpl(None)  # ServiceContext 尚未就绪，后续注入
        self.interpreter: Optional[Interpreter] = None

        # 多 Interpreter 并发任务表（handle → (thread, sub_engine, exc_holder)）
        self._spawned_tasks: Dict[str, Tuple[threading.Thread, 'IBCIEngine', list, Optional[float], list]] = {}
        self._spawned_tasks_lock = threading.Lock()

        # --- root-dependent（延迟）：在 _ensure_root_initialized 中确立 ---
        self.auto_sniff = auto_sniff
        self.root_dir: Optional[str] = None
        self._plugin_search_paths: List[str] = []
        # 继承的父 plugin search_paths（隔离子引擎透传）。
        # 分两路透传以保持优先级：inherited_global_plugin（保持在优先级 2，不被普通 plugin 覆盖）；
        # inherited_plugin_paths（作为兜底来源，优先级 6）。
        self._inherited_plugin_paths: List[str] = list(inherited_plugin_paths) if inherited_plugin_paths else []
        self._inherited_global_plugin: List[str] = list(inherited_global_plugin) if inherited_global_plugin else []
        self._global_plugin_paths: List[str] = []  # 自身解析出的 global_plugin（含继承），传给子引擎
        self.scheduler = None  # type: ignore[assignment]
        self.discovery_service = None  # type: ignore[assignment]
        self.module_loader = None  # type: ignore[assignment]
        self._root_initialized = False

    # ------------------------------------------------------------------
    # 多阶段启动：project_root 确立 + root-dependent 延迟初始化
    # ------------------------------------------------------------------

    def _establish_project_root(self, entry_file: Optional[str]) -> str:
        """确立 project_root：= 显式 OR entry_dir。

        - 显式 root_dir 已提供（构造期）→ 用它。
        - 否则有 entry_file → project_root = entry_file 所在目录（canonicalize）。
        - 否则（run_string 无 entry 且无显式 root）→ 报错。
        """
        if self._explicit_root is not None:
            return self._explicit_root
        if entry_file is None:
            raise InterpreterError(
                "project_root 未确立：run_string/compile_string 无真实 entry_file，"
                "须在构造期显式提供 root_dir。",
                None,
            )
        # 先 canonicalize entry_file（解 symlink），再取 parent，确保 project_root
        # 与 run()/compile() 中 canonicalize 后的 _entry_file 同源（沙箱边界一致）。
        entry_ib = PathValidator.canonicalize_for_security(entry_file)
        parent = entry_ib.parent
        entry_dir = parent.to_native() if parent is not None else ""
        return entry_dir if entry_dir else entry_ib.to_native()

    def _ensure_root_initialized(self, project_root: str) -> None:
        """root-dependent 延迟初始化（多阶段启动）：plugin 发现路径 + Scheduler。

        幂等：engine 单次执行，project_root 一旦确立不再变。
        plugin 发现优先级见 ``resolve_plugin_search_paths``。
        """
        if self._root_initialized:
            return
        self.root_dir = project_root
        self._plugin_search_paths = self.resolve_plugin_search_paths(project_root)
        self.discovery_service = ModuleDiscoveryService(self._plugin_search_paths)
        self.module_loader = ModuleLoader(self._plugin_search_paths, capability_registry=self.capability_registry)
        self.scheduler = Scheduler(
            project_root, host_interface=self.host_interface,
            issue_tracker=self.issue_tracker,
            registry=self.registry.get_metadata_registry(),
        )
        self._root_initialized = True

    def resolve_plugin_search_paths(self, project_root: str) -> List[str]:
        """plugin 发现优先级（高 → 低，先命中者胜）：

        1. **kernel-native**（install 路径，恒在，最高优先级，不可覆盖）
        2. **global_plugin**（ibci.json 的 global_plugin 字段；全局 ibci.json 查找本轮预留）
        3. **plugin_paths**（ibci.json 显式）；配置后嗅探**不触发**（explicit > implicit）
        4. **嗅探 project_root**（ProjectDetector，仅 plugin_paths 未配置时）
        5. 全局 config（**预留，本轮不实现**）
        6. **继承的父 plugin_paths**（隔离子引擎透传；附加于自身之后，作为兜底来源）

        继承的 **global_plugin** 单独透传，并入优先级 2（与自身 global_plugin 合并），
        而非混入兜底的 inherited_plugin_paths（优先级 6）——保持
        "global_plugin 不被普通优先级覆盖" 在隔离子引擎中也成立。

        plugin_path 只读特权：可在 project_root 之外（模块加载为 loader 级特权操作，
        越界读取；脚本写入仍由 proj_root 沙箱约束——file.* 走 PermissionManager）。
        """
        config = IbciConfig.load(project_root)
        own_global_plugin = IbciConfig.global_plugin(config, project_root)
        explicit_plugin_paths = IbciConfig.plugin_paths(config, project_root)

        # global_plugin = 自身 + 继承（去重保序，保持在优先级 2）
        global_plugin_merged: List[str] = []
        for g in own_global_plugin + self._inherited_global_plugin:
            if g not in global_plugin_merged:
                global_plugin_merged.append(g)
        self._global_plugin_paths = global_plugin_merged  # 供子引擎继承

        ordered: List[str] = [self._install_path]              # 1. 内核原生（install）最高
        ordered.extend(global_plugin_merged)                 # 2. global_plugin（自身+继承）
        if explicit_plugin_paths:
            ordered.extend(explicit_plugin_paths)            # 3. 显式 plugin_paths（嗅探不触发）
        elif self.auto_sniff:
            ordered.extend(ProjectDetector.get_plugin_paths(project_root))  # 4. 嗅探兜底
        # 5. 全局 config：预留
        ordered.extend(self._inherited_plugin_paths)         # 6. 继承的普通 plugin_paths（兜底）

        # 去重保序
        seen = set()
        result = []
        for p in ordered:
            if p not in seen:
                seen.add(p)
                result.append(p)
        return result

    def spawn_interpreter(self, artifact: Any, registry: Any, host_interface: Any, root_dir: str, parent_context: Any, entry_file: str = None, entry_dir: str = None, project_root: str = None) -> Interpreter:
        """[IInterpreterFactory] 实现工厂方法产生子解释器"""
        instance_id = self.rt_scheduler.spawn(
            artifact=artifact,
            registry=registry,
            host_interface=host_interface,
            root_dir=root_dir,
            factory=self,
            object_factory=self.object_factory,
            plugin_loader=self._load_plugins,
            kernel_token=self._kernel_token,
            issue_tracker=self.issue_tracker,
            output_callback=self._output_callback,
            input_callback=None,
            entry_file=entry_file,
            entry_dir=entry_dir,
            project_root=project_root,
            capability_registry=self.capability_registry
        )
        return self.rt_scheduler.instances[instance_id]

    def _prepare_interpreter(self, artifact: Optional[Any] = None, output_callback=None):
        """初始化解释器并动态加载模块实现"""
        # entry_dir 从 PathContext（锚点容器）读取——保证其始终有意义：
        # run → entry_file.parent；run_string → project_root。
        _ctx_entry_dir = self._path_ctx.entry_dir.to_native() if self._path_ctx else None
        _ctx_project_root = self._path_ctx.project_root.to_native() if self._path_ctx else None
        self.interpreter = self.spawn_interpreter(
            artifact=artifact,
            registry=self.registry,
            host_interface=self.host_interface,
            root_dir=self.root_dir,
            parent_context=None,
            entry_file=self._entry_file,
            entry_dir=_ctx_entry_dir,
            project_root=_ctx_project_root
        )
        
        # Post-construction wiring: inject orchestrator and output_callback into ServiceContext.
        # scheduler / capability_registry / host_service 已由 rt_scheduler.spawn 通过
        # 公开 setter 注入（set_scheduler / set_capability_registry / set_host_service）。
        # Engine 此处仅注入 orchestrator（Engine 自身）和 output_callback。
        service_context = self.interpreter.service_context
        service_context.set_orchestrator(self)
        if output_callback is not None:
            service_context.output_callback = output_callback
        if self._test_hooks is not None:
            service_context.test_hooks = self._test_hooks

        # 延迟水化调度器（给 rt_scheduler 注入 service_context 引用，方向与上述 setter 相反）
        self.rt_scheduler.hydrate(service_context)

        # 设定主实例 ID
        self.rt_scheduler._main_instance_id = self.interpreter.instance_id
        
        # STAGE 7: 深度契约校验与就绪
        # 强制检查状态流转，确保 STAGE 6 (预评估) 已完成
        if self.registry.state_level < RegistrationState.STAGE_6_PRE_EVAL.value:
             self.registry.set_state_level(RegistrationState.STAGE_6_PRE_EVAL.value, self._kernel_token)

        validator = ContractValidator(self.registry.get_metadata_registry(), self.issue_tracker)
        validator.validate_all()
        
        # 如果校验过程中发现了严重契约冲突，则阻止系统进入 READY 状态
        if self.issue_tracker.has_errors():
             raise InterpreterError("System readiness failed: Global Contract Violation detected in STAGE 7.", None)

        self.registry.set_state_level(RegistrationState.STAGE_7_READY.value, self._kernel_token)
        # 封印类注册表
        self.registry.seal_classes(self._kernel_token)

        # 将 LLM 执行器注入 KernelRegistry，使 IbBehavior.call() 可通过公理体系自主执行
        llm_executor = self.interpreter.service_context.llm_executor
        if llm_executor is not None:
            self.registry.register_llm_executor(llm_executor, self._kernel_token)

        # 将宿主服务、调用栈内省器、状态读取器注入 KernelRegistry
        # 供核心层插件（ibci_ihost、ibci_idbg）通过稳定钩子接口访问，替代直接持有 ServiceContext
        host_service = self.interpreter.service_context.host_service
        if host_service is not None:
            self.registry.register_host_service(host_service, self._kernel_token)

        stack_inspector = self.interpreter.execution_context.stack_inspector
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

        self.registry.set_state_level(RegistrationState.STAGE_4_PLUGIN_IMPL.value, self._kernel_token)

        # plugin 发现走统一解析的 search_paths（install/global_plugin/plugin_paths/嗅探）。
        discovery = AutoDiscoveryService(self._plugin_search_paths)

        axiom_registry = self.registry.get_metadata_registry().get_axiom_registry()
        if axiom_registry:
            for spec in discovery.discover_plugins().values():
                if spec.has_axioms():
                    for axiom in spec.axioms.values():
                        axiom_registry.register(axiom)

        self.module_loader.load_and_register_all(service_context, execution_context)

        self.registry.set_state_level(RegistrationState.STAGE_5_HYDRATION.value, self._kernel_token)

    def register_native_module(self, name: str, implementation: Any, type_metadata: Optional[Any] = None):
        """
         显式注册一个原生 Python 模块实现及其元数据。

         可能在 run() 前调用（如 main.py load_external_plugins），
         此时需构造期已提供 explicit root，否则报错（无 entry_file 可确立 project_root）。
        """
        if not self._root_initialized:
            if self._explicit_root is None:
                raise InterpreterError(
                    "register_native_module 需在构造期显式提供 root_dir（或在 run/compile 之后调用）。",
                    None,
                )
            self._ensure_root_initialized(self._explicit_root)
        self.host_interface.register_module(name, implementation, type_metadata)
        self.scheduler.host_interface = self.host_interface

    def _ensure_plugins_discovered(self) -> None:
        """
        确保插件元数据已加载到 host_interface（懒加载，只在首次编译/检查时触发）。

        显式引入原则：discover_all() 不在 Engine.__init__() 中无条件调用，
        而是延迟到首次编译时才执行。这确保：
        1. 仅创建 Engine 实例而不编译时，不触发任何插件发现。
        2. Scheduler 在编译开始前获得完整的 host_interface（含所有插件元数据）。
        3. 插件符号仍须通过 import 语句显式引入才能在代码中使用（Prelude 过滤保证）。
        """
        if not self._plugins_discovered:
            # 传入已有的 host_interface，保留构造期预注册的 kernel-native 模块
            self.host_interface = self.discovery_service.discover_all(self.registry, host=self.host_interface)
            self.scheduler.host_interface = self.host_interface
            self._plugins_discovered = True

    def compile_string(self, code: str, variables: Optional[Dict[str, Any]] = None, silent: bool = False) -> CompilationArtifact:
        """
         编译一段 IBCI 代码字符串，返回蓝图。

         run_string 无真实 entry_file → 合成 entry
         ``<project_root>/__string_exec__.ibci``（entry_dir = project_root，语义自洽，非 tempdir）。
         project_root 须显式提供（无 entry_file 可默认）；tempfile 仅作编译器源码载体。
        """
        # project_root 必须显式（run_string 无真实 entry 可默认 entry_dir）
        project_root = self._establish_project_root(None)
        self._ensure_root_initialized(project_root)
        # 合成 entry：anchor 语义，非源码文件
        synthetic_entry = (IbPath.from_native(project_root) / "__string_exec__.ibci").to_native()

        # tempfile 仅作编译器源码载体（源码位置），entry_file 用合成路径（anchor）
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ibci', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_path = f.name

        try:
            self.scheduler.allow_file(temp_path)
            self._entry_file = synthetic_entry
            self._path_ctx = PathContext.from_native(
                entry_dir=project_root, project_root=project_root
            )
            # 入口模块名显式锚定（稳定身份）：源码经 tempfile 载体、路径派生名
            # 非确定，传合成锚点名（__string_exec__）使入口模块身份稳定可复现。
            return self.compile(temp_path, variables, silent=silent,
                                entry_module_name="__string_exec__")
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
        # 多阶段启动：先确立 project_root + root-dependent 初始化
        project_root = self._establish_project_root(entry_file)
        self._ensure_root_initialized(project_root)
        # entry 锚点：经 canonicalize_for_security 规范化（解 symlink、绝对化相对路径，
        # 与 check()/project_root 同源）。原仅 resolve_dot_segments（词法），
        # 对相对 entry 会产出相对 entry_dir，破坏运行时路径解析。
        _entry_ib = PathValidator.canonicalize_for_security(entry_file)
        self._entry_file = _entry_ib.to_native()
        _entry_parent = _entry_ib.parent
        _entry_dir = _entry_parent.to_native() if _entry_parent is not None else ""
        self._path_ctx = PathContext.from_native(
            entry_dir=_entry_dir, project_root=project_root
        )
        abs_entry = self._entry_file

        if output_callback:
            self._output_callback = output_callback

        if not os.path.exists(abs_entry):
            # 统一错误语义：入口缺失与编译错误一样显式抛出（fail-fast），
            # 不再静默返回 False（调用方无法区分"运行成功"与"文件缺失"）。
            raise FileNotFoundError(f"Entry file not found: {abs_entry}")

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

    def compile(self, entry_file: str, variables: Optional[Dict[str, Any]] = None, silent: bool = False,
                entry_module_name: Optional[str] = None) -> Any:
        """
         核心解耦：仅执行静态编译和语义分析，返回 CompilationArtifact。

         多阶段启动：确立 project_root（= 显式 OR entry_dir）+ root-dependent 初始化。
         锚点（_entry_file / _path_ctx）由语义调用方（run / compile_string）确立。

         ``entry_module_name``：可选入口模块名覆盖（compile_string 场景——源码经
         tempfile 载体、路径派生名非确定，传稳定锚点名使入口模块身份可复现）。
        """
        # 确立 project_root + root-dependent 初始化（幂等）
        project_root = self._establish_project_root(entry_file)
        self._ensure_root_initialized(project_root)
        # 懒加载插件元数据（显式引入原则）
        self._ensure_plugins_discovered()

        # entry_file 直接用作编译输入（源码位置）；canonicalize（解 symlink、绝对化）。
        abs_entry = PathValidator.canonicalize_for_security(entry_file).to_native()
        
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
        
        return self.scheduler.compile_project(abs_entry, entry_module_name=entry_module_name)

    def execute(self, artifact: CompilationArtifact, variables: Optional[Dict[str, Any]] = None, output_callback=None) -> bool:
        """
         调度入口。执行编译产物。
         注意：如果引擎已经处于 READY 状态，调用此方法将抛出状态冲突错误。建议每个执行流创建新的引擎实例。

         execute() 依赖 root-dependent 初始化（Scheduler/Permission/module_loader），
         故要求先经 run/compile/compile_string/check 触发 _ensure_root_initialized。
         直接 execute() 未经编译 → 明确报错。
        """
        if not self._root_initialized:
            raise InterpreterError(
                "execute() 要求先经 run/compile/compile_string/check 触发 project_root 初始化"
                "（root-dependent 设置延迟到首次编译/运行）。",
                None,
            )
        serializer = FlatSerializer(registry=self.scheduler.registry)
        artifact_dict = serializer.serialize_artifact(artifact)

        # 包装为 ImmutableArtifact，防止解释器修改 artifact
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
            if not isinstance(val, IbObject):
                val = self.interpreter.registry.box(val)
            if self.interpreter.runtime_context:
                self.interpreter.runtime_context.define_variable(name, val)

    def get_variable(self, name: str) -> Any:
        """[Engine API] 从当前解释器环境获取变量"""
        if self.interpreter and self.interpreter.runtime_context:
            val = self.interpreter.runtime_context.get_variable(name)
            return val
        return None

    def get_llm_call_trace(self) -> List[Any]:
        """[Engine API] 获取最近 LLM 调用追踪（调试观测）。

        每条含 ``sys_prompt``/``user_prompt``/``response``/意图列表——定位
        "LLM 未服从 vs 内核未注入"时直接查看实际发出的 prompt 与返回。
        无 LLM executor（未运行）返回空列表。
        """
        executor = self.registry.get_llm_executor() if self.registry else None
        if executor is None:
            return []
        return executor.get_call_trace()

    def test_snapshot(self) -> EngineTestSnapshot:
        """引擎可观测状态快照（测试内省；替代对私有字段的穿透访问）。

        ``spawned_handles`` 为锁内快照，避免与并发 spawn 竞态。
        """
        with self._spawned_tasks_lock:
            handles = list(self._spawned_tasks.keys())
        entry_dir = self._path_ctx.entry_dir.to_native() if self._path_ctx else None
        project_root = self._path_ctx.project_root.to_native() if self._path_ctx else None
        return EngineTestSnapshot(
            explicit_root=self._explicit_root,
            cwd=self._cwd,
            entry_file=self._entry_file,
            entry_dir=entry_dir,
            project_root=project_root,
            plugin_search_paths=list(self._plugin_search_paths),
            install_path=self._install_path,
            root_initialized=self._root_initialized,
            spawned_handles=handles,
        )

    def reset_test_state(self) -> None:
        """重置引擎级测试可观测状态（清空在途隔离 spawn 任务表）。

        供测试复用引擎实例时的隔离清理：子线程为 daemon，清表不中断其执行，
        仅移除句柄追踪（收集语义为"已消费"）。生产流程不使用。
        """
        with self._spawned_tasks_lock:
            self._spawned_tasks.clear()

    @property
    def test_hooks(self) -> Optional[Any]:
        """测试钩子（TestHooks 协议实例；解释器就绪后注入服务上下文）。"""
        return self._test_hooks

    @test_hooks.setter
    def test_hooks(self, hooks: Optional[Any]) -> None:
        self._test_hooks = hooks
        if self.interpreter is not None and self.interpreter.service_context is not None:
            self.interpreter.service_context.test_hooks = hooks
    def check(self, entry_file: str, silent: bool = False) -> bool:
        """
        仅对项目进行静态检查（编译和语义分析）。

        多阶段启动：确立 project_root + root-dependent 初始化。
        entry 规范化统一走 canonicalize_for_security（与 run/compile 同源，解 symlink）。
        """
        # 确立 project_root + root-dependent 初始化
        project_root = self._establish_project_root(entry_file)
        self._ensure_root_initialized(project_root)
        # 懒加载插件元数据（显式引入原则）
        self._ensure_plugins_discovered()

        abs_entry = PathValidator.canonicalize_for_security(entry_file).to_native()
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

    def _validate_and_derive_isolated(self, entry_path: str) -> Tuple[str, str]:
        """隔离反转：解析子 entry + 校验其在父 project_root 内。

        现阶段语义（负责人确认）：子脚本不得超出父 project_root。
        - 派生：``PathContext.derive_isolated``（子 project_root = 子 entry_dir，纯路径策略）。
        - 策略校验（本方法）：子 entry 必须在父 ``self.root_dir`` 内，否则报错。
        - 未来：policy 可放开特定外部 zone。
        """
        # 确保父 project_root 已确立：隔离调用可能在 parent 未 run 时发生（engine 层 API 直调）。
        if not self._root_initialized:
            self._ensure_root_initialized(self._establish_project_root(None))
        abs_path, sub_root_dir = PathContext.derive_isolated(entry_path)
        # 校验：子 entry（canonicalize 后）必须在父 project_root 内
        child_canonical = PathValidator.canonicalize_for_security(abs_path)
        parent_root = IbPath.from_native(self.root_dir)
        if not PathValidator.is_within(parent_root, child_canonical):
            raise InterpreterError(
                f"隔离执行拒绝：子入口 {abs_path} 不在父 project_root {self.root_dir} 内"
                f"（现阶段子脚本不得超出父 proj_root）。",
                None,
            )
        return abs_path, sub_root_dir

    def _resolve_inherited_plugin_paths(self, policy: Union[Dict[str, Any], IsolationPolicy]) -> List[str]:
        """根据 IsolationPolicy.inherit_plugins 解析子引擎应继承的插件搜索路径。

        True  = 全部继承（默认）
        False = 不继承
        """
        policy_obj = IsolationPolicy.from_dict(policy) if isinstance(policy, dict) else policy

        if policy_obj.inherit_plugins:
            return self._plugin_search_paths
        return []

    def request_spawn_isolated(self, entry_path: str, policy: Dict[str, Any], silent: bool = True) -> str:
        """
        [IKernelOrchestrator] 非阻塞版本的隔离执行系统调用。
        在后台线程中启动全新的 Engine 实例；立即返回 handle 字符串。
        调用方随后通过 request_collect(handle) 阻塞等待结果。

        ``silent``：子引擎是否抑制输出。``spawn_isolated``（后台任务）默认 True；
        ``run_isolated``（阻塞式运行）传 False 以保留子脚本输出。
        """
        # 派生 + 隔离反转校验。
        abs_path, sub_root_dir = self._validate_and_derive_isolated(entry_path)

        policy_obj = IsolationPolicy.from_dict(policy) if isinstance(policy, dict) else policy

        sub_engine = IBCIEngine(
            root_dir=sub_root_dir,
            auto_sniff=self.auto_sniff,
            inherited_plugin_paths=self._resolve_inherited_plugin_paths(policy_obj),
            inherited_global_plugin=self._global_plugin_paths,   # global_plugin 单独透传保持优先级
        )

        # exc_holder[0] 捕获子线程中抛出的异常，以便 collect 时重新抛出
        exc_holder: list = [None]
        # R2：子任务完成的唤醒回调表（HostAwaitable.register_wake 注册的 event）
        wake_callbacks: list = []

        def _run_child():
            try:
                sub_engine.run(abs_path, silent=silent)
            except Exception as e:
                exc_holder[0] = e
            finally:
                # 子线程完成 → 触发全部唤醒回调（调度器即时唤醒，无轮询延迟）
                with self._spawned_tasks_lock:
                    callbacks, _cb_ref = wake_callbacks, []
                    wake_callbacks[:] = []
                for ev in callbacks:
                    ev.set()

        thread = threading.Thread(target=_run_child, daemon=True, name=f"ibci-spawn-{abs_path}")
        thread.start()

        handle = f"spawn_{uuid.uuid4().hex[:16]}"
        with self._spawned_tasks_lock:
            self._spawned_tasks[handle] = (thread, sub_engine, exc_holder, policy_obj.collect_timeout, wake_callbacks)

        return handle

    def register_spawn_wake(self, handle: str, event) -> bool:
        """[IKernelOrchestrator] 为 spawn handle 注册完成通知（R2）。

        子线程完成时设置 ``event``（调度器即时唤醒）。返回 False 表示 handle
        已不存在/已完成（调用方退回首轮询）。
        """
        with self._spawned_tasks_lock:
            task = self._spawned_tasks.get(handle)
            if task is None:
                return False
            thread, _sub, _exc, _to, wake_callbacks = task
            if not thread.is_alive():
                # 已完成：立即唤醒（竞态下注册晚于完成）
                event.set()
                return True
            wake_callbacks.append(event)
            return True

    def is_spawn_done(self, handle: str) -> bool:
        """[IKernelOrchestrator] 非破坏性检查 spawn handle 的子线程是否已执行完成。

        供 ``HostAwaitable.is_done`` 轮询；不消费 handle（不 pop），与
        ``request_collect`` 的消费语义互补。handle 不存在/已消费视为已完成。
        """
        with self._spawned_tasks_lock:
            task = self._spawned_tasks.get(handle)
        if task is None:
            return True
        return not task[0].is_alive()

    def request_collect(self, handle: str) -> Dict[str, Any]:
        """
        [IKernelOrchestrator] 阻塞等待 spawn handle 对应的子执行完成。
        线程 join 后提取子环境的全局变量（排除内置符号和不可序列化值），
        以 Python dict 形式返回，由 HostService 层装箱为 IbDict 传回 IBCI。

        collect_timeout（spawn 时由 IsolationPolicy 传入）：
            None = 无界等待（默认，阻塞至子执行完成）；
            正数 = 墙钟等待上限（秒），超时抛 RuntimeError。Python 无法强杀
                   线程，超时后子线程作为 daemon 孤儿继续运行直至自身结束
                   或进程退出，调用方不应假设子任务已停止。
        """
        with self._spawned_tasks_lock:
            task = self._spawned_tasks.pop(handle, None)
        if task is None:
            raise RuntimeError(f"Unknown spawn handle: {handle!r}. "
                               "The handle may have already been collected or never spawned.")

        thread, sub_engine, exc_holder, collect_timeout, _wake_callbacks = task
        thread.join(timeout=collect_timeout)  # None = 无界阻塞；正数 = 墙钟上限
        if thread.is_alive():
            # 超时：handle 已消费，子线程作为 daemon 孤儿继续运行。
            raise RuntimeError(
                f"collect({handle!r}) timed out after {collect_timeout}s; "
                "the isolated child thread is still running as a daemon orphan "
                "and could not be joined."
            )

        # 子线程异常透传至父环境
        if exc_holder[0] is not None:
            raise RuntimeError(
                f"Isolated execution ({handle!r}) raised an exception: {exc_holder[0]}"
            ) from exc_holder[0]

        # 从子引擎全局作用域提取用户变量（原生 Python 值）
        # 排除内置/不可序列化对象（函数、行为、插件模块等）
        result: Dict[str, Any] = {}

        if sub_engine.interpreter and sub_engine.interpreter.runtime_context:
            all_syms = sub_engine.interpreter.runtime_context.global_scope.get_all_symbols()
            for name, sym in all_syms.items():
                if sym.is_intrinsic:
                    continue
                val = sym.value
                if val is None:
                    continue
                # 非 IbObject 占位符（未执行的 LLMFuture 等）不属于可收集变量：
                # 结构化判别前置，替代宽 except 吞错（try 只保留 to_native 转换）。
                if not isinstance(val, IbObject):
                    continue
                type_name = val.ib_class.name
                if type_name in _COLLECT_SKIP_TYPES:
                    continue
                try:
                    result[name] = val.to_native()
                except Exception as e:
                    # 跳过无法转为原生值的对象（未执行的延迟值、循环引用等）
                    kernel_diagnostic(
                        code=KDIAG_RUNTIME_COLLECT_SKIP,
                        detail={"handle": handle, "name": name, "error": repr(e)},
                        message=(
                            f"collect({handle!r}) skipped non-convertible "
                            f"variable '{name}': {e!r}"
                        ),
                    )

        return result
