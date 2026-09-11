import os
import sys
import json
import shutil
import subprocess
import importlib.util
import tempfile
import traceback
import copy
import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple, Callable

import re as _re
from pathlib import Path

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

from core.kernel.path import IbPath, PathContext, PathValidator
from core.runtime.path import InstallPaths
from core.kernel.registry import KernelRegistry
from core.compiler.scheduler import Scheduler
from core.runtime.interpreter.interpreter import Interpreter
from core.runtime.objects.kernel import IbObject
from core.runtime.factory import RuntimeObjectFactory
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
from core.kernel.spec import INT_SPEC, STR_SPEC, FLOAT_SPEC, BOOL_SPEC, ANY_SPEC
from core.runtime.interfaces import IInterpreterFactory, ServiceContext, IKernelOrchestrator
from core.runtime.interfaces import IExecutionContext
from core.runtime.host.isolation_policy import IsolationPolicy
from core.runtime.rt_scheduler import RuntimeSchedulerImpl
from core.runtime.serialization.immutable_artifact import ImmutableArtifact
from core.runtime.capability_registry import CapabilityRegistry
from core.runtime.observability.events import EventBus
from core.runtime.observability.diagnostics import kernel_diagnostic
from core.base.diagnostics.codes import KDIAG_RUNTIME_COLLECT_SKIP, HOST_ISOLATE_LLM_INHERIT_FAILED


from core.base.enums import RegistrationState

# collect() 时跳过的 IBCI 类型名集合（函数/行为/可调用实例等不可序列化为原生 Python 值）
# 变量导出跳过类型清单的单一权威源在 main.py `_extract_engine_variables`
# （子进程 CLI 端执行变量提取；父进程 request_collect 从 JSON 读取结果）。


@dataclass(frozen=True)
class EngineTestSnapshot:
    """引擎可观测状态快照（测试内省用，只读，替代私有字段穿透）。

    字段均为引擎生命周期事实的只读投影：
    - ``explicit_root``    —— 构造期显式 root（canonicalize 后；未提供为 None）
    - ``cwd``              —— 构造期 CWD
    - ``entry_file``       —— 当前 entry 锚点（run/compile_string 确立后非 None）
    - ``entry_dir``        —— PathContext.entry_dir 原生字符串（未确立为 None）
    - ``project_root``     —— PathContext.project_root 原生字符串（未确立为 None）
    - ``install_path``     —— 内核原生模块目录
    - ``root_initialized`` —— root-dependent 初始化是否完成
    - ``spawned_handles``  —— 在途隔离 spawn 任务句柄（锁内快照）
    """

    explicit_root: Optional[str] = None
    cwd: str = ""
    entry_file: Optional[str] = None
    entry_dir: Optional[str] = None
    project_root: Optional[str] = None
    install_path: str = ""
    root_initialized: bool = False
    spawned_handles: List[str] = field(default_factory=list)


# Rust 运行时环境错误类名 → 诊断码映射（与 Python 运行时同一契约面：
# core.runtime.objects.kernel.functions 异常类型→码映射的数据面投影）。
_RUST_ERROR_CODES = {
    "ZeroDivisionError": "RUN_DIVISION_BY_ZERO",
    "IndexError": "RUN_INDEX_ERROR",
    "KeyError": "RUN_INDEX_ERROR",
    "AttributeError": "RUN_ATTRIBUTE_ERROR",
    "TypeError": "RUN_TYPE_MISMATCH",
}


class IBCIEngine(IInterpreterFactory, IKernelOrchestrator):
    """
    IBC-Inter 标准化引擎，整合了调度、编译和执行流程。
    """
    def __init__(self, root_dir: Optional[str] = None):
        """
        参数:
            root_dir: **可选**。项目根目录（沙箱边界）。
                引擎级默认——未提供时，project_root 在 run()/compile() 时
                确立为 entry_file 所在目录（entry_dir）。run_string 无真实 entry，须显式提供。
                提供时经 canonicalize_for_security 规范化。

        多阶段启动：__init__ 仅做 root-independent 设置（KernelRegistry/CWD/install 路径等）；
        root-dependent 设置（Scheduler）延迟到 ``_ensure_root_initialized``，
        在 run/compile/check 时经 ``_establish_project_root`` 确立 project_root 后触发。

        用户侧扩展唯一边 = 宿主绑定 bind；不再有插件搜索路径/嗅探/继承透传
        （_spec.py 磁盘发现通道已废弃，内置模块全部构造期预注册）。
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
        # 预注册宿主侧构造期内置模块（内核原生 5 + net + file）
        from core.runtime.bootstrap.builtin_modules import register_builtin_modules
        register_builtin_modules(self.host_interface)
        # 工具契约自举（bind 声明契约源：math/json/time/schema——契约单一权威源
        # = contracts/<module>.ibci，经既有注册/绑定通道）
        from core.runtime.bootstrap.kernel_contracts import load_tool_contracts
        load_tool_contracts(self.host_interface)

        # 运行时调度器
        self.rt_scheduler = RuntimeSchedulerImpl(None)  # ServiceContext 尚未就绪，后续注入
        self.interpreter: Optional[Interpreter] = None

        # 多 Interpreter 并发任务表（handle → (thread, sub_engine, exc_holder)）
        self._spawned_tasks: Dict[str, Tuple[threading.Thread, 'IBCIEngine', list, Optional[float], list]] = {}
        self._spawned_tasks_lock = threading.Lock()

        # --- root-dependent（延迟）：在 _ensure_root_initialized 中确立 ---
        self.root_dir: Optional[str] = None
        self.scheduler = None  # type: ignore[assignment]
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
        """root-dependent 延迟初始化（多阶段启动）：Scheduler + module_loader。

        幂等：engine 单次执行，project_root 一旦确立不再变。
        内置模块已构造期预注册；loader 仅负责已注册模块的契约绑定与 setup
        （无磁盘插件发现/搜索路径）。
        """
        if self._root_initialized:
            return
        self.root_dir = project_root
        self.module_loader = ModuleLoader(capability_registry=self.capability_registry)
        self.scheduler = Scheduler(
            project_root, host_interface=self.host_interface,
            issue_tracker=self.issue_tracker,
            registry=self.registry.get_metadata_registry(),
        )
        self._root_initialized = True

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
        """驱动模块加载生命周期 (STAGE 4 -> STAGE 5)。

        无插件公理加载（__ibcext_axiom__ 死协议已废弃）；内置模块经
        module_loader 契约绑定与 setup（构造期已注册实现）。
        """

        self.registry.set_state_level(RegistrationState.STAGE_4_PLUGIN_IMPL.value, self._kernel_token)

        self.module_loader.load_and_register_all(service_context, execution_context)

        self.registry.set_state_level(RegistrationState.STAGE_5_HYDRATION.value, self._kernel_token)

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

        # 持久 artifact 缓存：键 = sha256(源码 + entry_module_name + kernel_version
        # + project_root)；命中 → 跳过 5 阶段编译管线，直接加载缓存产物。默认关闭
        # （IBCI_ARTIFACT_CACHE=1 启用），零侵入既有行为。
        from core.compiler.artifact_cache import (
            compute_cache_key, load_cached_artifact, save_artifact,
        )
        cache_key = compute_cache_key(code, "__string_exec__", project_root)
        cached = load_cached_artifact(project_root, cache_key)
        if cached is not None:
            return cached

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
            artifact = self.compile(temp_path, variables, silent=silent,
                                    entry_module_name="__string_exec__")
            # 持久 artifact 缓存：保存产物（失败不抛穿编译流程）
            save_artifact(project_root, cache_key, artifact)
            return artifact
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def run_string(self, code: str, variables: Optional[Dict[str, Any]] = None, output_callback=None, silent: bool = False, prepare_interpreter: bool = True, journal_writer=None, budget_guard=None, deterministic_guard=None, on_ready=None) -> bool:
        """
        运行一段 IBCI 代码字符串。

        ``on_ready``：解释器与插件就绪后、执行开始前触发的钩子
        （Callable[[IBCIEngine], None]，接收本引擎）——供子环境场景在
        执行前应用继承配置等；None = 无钩子（零侵入）。
        """
        try:
            artifact = self.compile_string(code, variables, silent=silent)
            if prepare_interpreter:
                return self.execute(artifact, variables, output_callback, journal_writer=journal_writer, budget_guard=budget_guard, deterministic_guard=deterministic_guard, on_ready=on_ready)
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

    def run(self, entry_file: str, variables: Optional[Dict[str, Any]] = None, output_callback=None, silent: bool = False, prepare_interpreter: bool = True, journal_writer=None, budget_guard=None, deterministic_guard=None, on_ready=None) -> bool:
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
                return self.execute(artifact, variables, output_callback, journal_writer=journal_writer, budget_guard=budget_guard, deterministic_guard=deterministic_guard, on_ready=on_ready)

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

    def execute(self, artifact: CompilationArtifact, variables: Optional[Dict[str, Any]] = None, output_callback=None, journal_writer=None, budget_guard=None, deterministic_guard=None, on_ready=None) -> bool:
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

        # ⑦ 切换门面分区路由：数据面源（节点类型全集 ⊆ Rust 反序列化器处理
        # 全集）→ Rust 内核执行（执行真相 = Rust）；LLM/宿主面源 → Python
        # 运行时（LLM 语义宿主）。单一内核归属纪律：每源按节点类型路由至
        # 唯一内核（无对比/无静默回退——双内核协议）。
        from core.runtime.kernels import artifact_is_rust_executable

        if artifact_is_rust_executable(artifact_dict):
            # 输出面同构（VM print 契约：callback 优先，无 callback =
            # stdout 渲染点——子进程 CLI[main.py run] silent 面同语义）
            return self._execute_rust(
                artifact_dict,
                variables=variables,
                output_callback=output_callback or self._output_callback,
                on_ready=on_ready,
            )

        # LLM journal 挂载（run 级审计侧信道；None = 不挂载，行为与无 journal 完全一致）
        if journal_writer is not None:
            self.interpreter.service_context.set_llm_journal(journal_writer)
        # LLM 预算守卫挂载（api_config budget 节驱动；None = 无预算，零侵入）
        if budget_guard is not None:
            self.interpreter.service_context.set_budget_guard(budget_guard)
        # 确定性执行守卫挂载（--deterministic 零 LLM 不变量；None = 未启用，零侵入）
        if deterministic_guard is not None:
            self.interpreter.service_context.set_deterministic_guard(deterministic_guard)
        # on_ready 钩子（解释器 + 插件就绪后、执行开始前；None = 无钩子，零侵入）
        if on_ready is not None:
            on_ready(self)

        # 委派执行权给运行时调度器
        # 目前调度器内部仍然通过 Engine 的准备机制来启动解释器
        # 但从宏观视角看，Engine 已经不再直接驱动 Interpreter
        return self.rt_scheduler.execute(immutable_artifact, variables=variables, output_callback=output_callback)

    def _bind_container_specialization(self, value, declared_type):
        """⑦ 镜像容器特化绑定（leaf._bind_container_specialization 同构
        registry 面）：声明为内置容器特化的容器值 → ib_class 重绑水化特化
        类 + type_ref 结构化；嵌套容器元素经 spec.element_type 递归绑定
        （VM 嵌套字面量各层独立绑定的镜像等价面）。非容器/非特化声明 =
        原样返回（保守）。"""
        if not isinstance(value, (list, dict)) or declared_type is None:
            return value
        spec_name = (
            getattr(declared_type, "qualified_name", None)
            or getattr(declared_type, "name", None)
        ) or ""
        container_kind = "list" if isinstance(value, list) else "dict"
        if spec_name.split("[", 1)[0].strip() != container_kind:
            return value
        registry = self.interpreter.registry
        spec_reg = registry.get_metadata_registry()
        if spec_reg is None:
            return value
        if "[" not in spec_name or spec_reg.resolve(spec_name) is None:
            return value
        specialized_cls = registry.get_class(spec_name)
        if specialized_cls is None:
            return value
        try:
            from core.runtime.objects.kernel import IbClass as _IbClass

            if not isinstance(specialized_cls, _IbClass):
                return value
            boxed = (
                value if hasattr(value, "ib_class") else registry.box(value)
            )
            if getattr(boxed, "ib_class", None) is None:
                return value
            boxed.ib_class = specialized_cls
            from core.kernel.spec.type_ref import TypeRef as _TypeRef

            boxed.type_ref = _TypeRef.from_spec(declared_type)
            # 嵌套元素递归（spec 元素类型 ref → 解析 → 绑定）
            elem_ref = getattr(declared_type, "element_type", None)
            if elem_ref is not None:
                elem_spec = spec_reg.resolve_typeref(elem_ref)
                if elem_spec is not None:
                    elements = getattr(boxed, "elements", None)
                    if elements is not None and isinstance(elements, list):
                        # 仅容器元素递归（标量元素装箱形态保持——解箱/
                        # 回箱循环会破坏元素装箱身份）
                        for i, elt in enumerate(list(elements)):
                            elt_base = (
                                getattr(
                                    getattr(elt, "ib_class", None), "name", ""
                                )
                                or ""
                            ).split("[", 1)[0]
                            if isinstance(elt, (list, dict)) or elt_base in (
                                "list",
                                "dict",
                            ):
                                native = (
                                    elt
                                    if isinstance(elt, (list, dict))
                                    else self._maybe_unbox(elt)
                                )
                                bound = self._bind_container_specialization(
                                    native, elem_spec
                                )
                                if bound is not None and bound is not elt:
                                    elements[i] = bound
            return boxed
        except Exception:
            return value

    @staticmethod
    def _maybe_unbox(v):
        """容器元素解箱（绑定面以原生值为操作面——box 幂等[已装箱原样
        返回]，unbox 统一递归绑定的元素操作面）。"""
        if hasattr(v, "to_native"):
            try:
                return v.to_native()
            except Exception:
                return v
        return v

    def _execute_rust(
        self,
        artifact_dict: dict,
        variables: Optional[Dict[str, Any]],
        output_callback: Optional[Callable[[str], None]],
        on_ready: Optional[Callable[["IBCIEngine"], None]],
    ) -> bool:
        """⑦ 切换门：数据面源执行（Rust 内核——执行真相唯一）+ 最终状态
        镜像（Python runtime_context = 状态/符号 API 容器——符号面来自
        编译产物，define_variable 绑定 Rust 导出的执行后值）。

        数据面源无 LLM 面 → journal/budget/deterministic 守卫无触发面
        （零 LLM 不变量平凡成立）；on_ready 钩子按契约执行（解释器就绪后、
        执行开始前）。初始变量经 Rust 状态面注入（run_artifact_state）；
        未捕获异常 = RuntimeError（Rust 内核边界——执行错误显式传播）。
        """
        import json as _json
        import warnings

        from core.runtime.kernels import load_kernel

        kernel = load_kernel()
        if on_ready is not None:
            on_ready(self)
        artifact_json = _json.dumps(artifact_dict, ensure_ascii=False)
        try:
            # 持久会话执行（host 桥接面：顶层环境保活——函数值宿主
            # .call 经会话调用，闭包/计数器状态跨调用存活）
            _handle, lines, state = kernel.open_session(
                artifact_json, variables if variables else None
            )
        except RuntimeError as e:
            # 环境限制异常边界转换（Rust 递归深度守卫 → Python
            # RecursionError 根因原样传播 + KDIAG 警告不门控投影——
            # Python VM 契约同面：深递归触底 = RecursionError 本身）
            if "RecursionError" in str(e):
                # 环境限制异常边界（VM 同面：KDIAG_RUNTIME_ENV_LIMIT 事件
                # 投影 + 警告不门控 + 根因原样传播）
                import core.runtime.observability.diagnostics as _diag

                _exc = RecursionError(str(e))
                _rc = None
                if (
                    self.interpreter is not None
                    and self.interpreter.execution_context is not None
                ):
                    _rc = self.interpreter.execution_context.runtime_context
                _diag.kernel_diagnostic(
                    "KDIAG_RUNTIME_ENV_LIMIT",
                    {"exc_type": "RecursionError", "message": str(e)},
                    message="环境限制异常 RecursionError: 非语义错误，保留根因传播",
                    rc=_rc,
                )
                warnings.warn(
                    "环境限制异常 RecursionError（Rust 内核递归深度超限）",
                    UserWarning,
                )
                raise _exc from e
            # 运行时环境错误边界映射（Rust 异常类名 → 诊断码——与 Python
            # 运行时同一契约面：functions.py 异常类型→码映射；数据面源
            # 执行错误 = 显式诊断码，非静默）
            m = _re.search(r"uncaught exception: (\w+)", str(e))
            if m and m.group(1) in _RUST_ERROR_CODES:
                detail = str(e).split(m.group(1) + ":", 1)[-1].strip()
                # 错误现场位置（Rust 表达式 pos @line:col 后缀——engine 边界
                # 构造诊断位置；file_path = 模块源文件[合成 entry 同形]）
                location = None
                pos_m = _re.search(r"@([0-9]+):([0-9]+)$", detail)
                if pos_m:
                    from core.base.source_atomic import Location

                    detail = detail[: pos_m.start()].strip()
                    file_path = Path(self.root_dir) / (
                        f"{artifact_dict['entry_module']}.ibci"
                    )
                    location = Location(
                        file_path=str(file_path),
                        line=int(pos_m.group(1)),
                        column=int(pos_m.group(2)),
                    )
                message = m.group(1) if not detail else f"{m.group(1)}: {detail}"
                raise InterpreterError(
                    message, location=location, error_code=_RUST_ERROR_CODES[m.group(1)]
                ) from e
            raise
        # 输出投递（VM 同面：有 callback → callback；无 = stdout 渲染点）
        if output_callback is not None:
            for line in lines:
                output_callback(line)
        else:
            for line in lines:
                print(line)
        # 最终状态镜像：执行真相 = Rust；Python 运行时上下文 = 状态容器
        # （get_variable/runtime_context 契约面——数据面源执行后可读）。
        # declared_type = prepare 期符号声明类型（artifact 符号池经 prepare
        # 加载）——运行时内省契约（declared_type 泛型身份保留）；可调用声明
        # 跳过运行时类型检查（VM 同面：值 = 函数对象时直放行——镜像值 =
        # 显示形态串，检查面不适用）。
        if self.interpreter is not None and self.interpreter.runtime_context is not None:
            # 顶层符号 UID 面（artifact 符号池：scope 级 VARIABLE 符号——
            # 声明类型经 execution_context.resolve_type_from_symbol 解析，
            # 与 Python VM 赋值路径同一权威源）
            mod = artifact_dict["modules"][artifact_dict["entry_module"]]
            sym_uid_by_name = {}
            for s in mod["pools"]["symbols"].values():
                uid = s.get("uid") or ""
                if (
                    s.get("kind") == "VARIABLE"
                    and ":" in uid
                    and "/" not in uid.rsplit(":", 1)[0]
                ):
                    sym_uid_by_name[s.get("name")] = uid
            rc = self.interpreter.runtime_context
            ec = self.interpreter.execution_context
            for name, value in state.items():
                sym_uid = sym_uid_by_name.get(name)
                declared_type = (
                    ec.resolve_type_from_symbol(sym_uid) if sym_uid else None
                )
                # quoted 保真物化（⑦ 状态契约：Rust Quoted 值 = 源串显示
                # 形态——declared quoted 声明的值经 IbQuoted 物化[源串全
                # 保真——repr 面单一权威]，运行时序列化/边界契约同面）
                _decl_name = getattr(declared_type, "name", None) or ""
                if (
                    _decl_name.split("[", 1)[0].strip() == "quoted"
                    and isinstance(value, str)
                ):
                    quoted_cls = self.interpreter.registry.get_class("quoted")
                    if quoted_cls is not None:
                        try:
                            from core.runtime.objects.primitives.quoted import (
                                IbQuoted,
                            )

                            value = IbQuoted(quoted_cls, source=value)
                        except Exception:
                            pass
                # 双路径镜像（⑦ 状态契约，声明家族驱动）：
                # - 数据家族声明（int/float/str/bool/any/list/dict/Optional
                #   ——镜像值 = 真数据值）= define_variable（VM 权威运行时
                #   类型检查面同构——语义错误集经同一 _check_type 发射）；
                # - 非数据家族声明（vector/quoted/knowledge/tuple/函数/类
                #   等——镜像值 = 显示形态串或保真度缺口）= materialize_
                #   variable（符号物化——declared_type 内省契约保留，
                #   类型检查面不适用）。
                # 容器特化身份（Python VM 同面：list[int]/dict[str,int] 声明
                # 的容器值对象 ib_class = 水化特化类——运行时特化身份/
                # 可赋值性契约；registry 面解析[特化类经 prepare 期水化
                # 注册]，非注册特化 = 保守基类值）
                # 容器特化身份绑定（VM 同面——递归嵌套；registry 面解析）
                value = self._bind_container_specialization(value, declared_type)
                declared_name = getattr(declared_type, "name", None) or ""
                declared_base = declared_name.split("[", 1)[0].strip()
                # 函数声明 = 宿主可调用代理物化（⑦ host 桥接面：.call
                # 薄包装语义经 Rust 会话调用——函数值宿主调用契约；
                # 值形态 = 会话函数值[显示串仅作 repr 面]）
                kind = (
                    getattr(declared_type, "kind", None)
                    if declared_type is not None
                    else None
                )
                if kind in ("function", "bound_method", "callable_sig"):
                    from core.runtime.kernels import RustFunctionProxy

                    value = RustFunctionProxy(
                        kernel, _handle, name, self.interpreter.registry
                    )
                if declared_base in (
                    "int", "float", "str", "bool", "any", "list", "dict",
                    "Optional",
                ):
                    rc.define_variable(name, value, declared_type=declared_type)
                else:
                    rc.materialize_variable(name, value, declared_type=declared_type, uid=sym_uid)
        return True

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

    def request_spawn_isolated(self, entry_path: Optional[str] = None, policy: Dict[str, Any] = None,
                               silent: bool = True, output_callback=None,
                               code: Optional[str] = None) -> str:
        """
        [IKernelOrchestrator] 非阻塞版本的隔离执行系统调用（**单一 spawn 核心，
        两源形式**：文件源 / 字符串源）。在独立子进程中启动全新的 Engine 实例
        （进程级隔离——消除同进程 sys.modules/模块级状态共享边界）；
        立即返回 handle 字符串。调用方随后通过 request_collect(handle) 阻塞等待
        结果。

        源形式（**恰好其一**，fail-fast）：
        - **文件源** = ``entry_path``：子进程运行一个 .ibci 文件；隔离反转
          校验（子 entry 须在父 project_root 内）+ 子 project_root = 子 entry_dir。
        - **字符串源** = ``code``：子进程运行一段 IBCI 代码字符串（写入临时
          .ibci 文件）；子 project_root = 父 project_root。

        通信协议：subprocess + JSON（stdout 末行 ``--result-json`` trailer）。
        子进程 = ``python main.py run <entry> --result-json --export-variables
        --root <project_root> --no-journal``。

        ``collect_timeout``（经 IsolationPolicy 传入）：
            None = 无界等待；正数 = 墙钟上限（超时 kill 子进程）。

        ``output_callback``：子脚本 print 输出收集器（Callable[[str], None]）；
        子进程 stdout 中 result JSON 之前的行经此回调逐行投递。
        """
        # 源形式判定：恰好其一（fail-fast——双源/零源 = 契约违约）。
        if (entry_path is None) == (code is None):
            raise InterpreterError(
                "request_spawn_isolated 须恰好一个源形式：entry_path（文件源）或 "
                "code（字符串源）。",
                None,
            )

        # 子 project_root 派生（文件源 = 隔离反转校验 + 子 entry_dir；
        # 字符串源 = 父 project_root）。
        if code is None:
            abs_path, sub_root_dir = self._validate_and_derive_isolated(entry_path)
            source_label = f"file:{abs_path}"
        else:
            if not self._root_initialized:
                self._ensure_root_initialized(self._establish_project_root(None))
            sub_root_dir = self.root_dir
            source_label = "string"

        policy_obj = IsolationPolicy.from_dict(policy) if isinstance(policy, dict) else policy

        # 字符串源 → 临时文件（须在子 project_root 内——安全策略约束）
        temp_files: list = []
        if code is not None:
            temp_dir = os.path.join(sub_root_dir, ".tmp_ibci_spawn")
            os.makedirs(temp_dir, exist_ok=True)
            temp_files.append(temp_dir)  # 记录目录以便清理
            fd, temp_path = tempfile.mkstemp(suffix=".ibci", prefix="ibci_spawn_", dir=temp_dir)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(code)
            temp_files.append(temp_path)
            abs_path = temp_path

        # LLM 配置继承快照 → 临时 JSON 文件（经环境变量传递路径）
        llm_state_file = None
        _llm_provider = self.capability_registry.get(CapabilityRegistry.CAP_LLM_PROVIDER)
        if _llm_provider is not None:
            try:
                from core.extension.ibcext import IbStatefulPlugin
                if isinstance(_llm_provider, IbStatefulPlugin):
                    llm_snapshot = _llm_provider.save_plugin_state()
                    if llm_snapshot:
                        fd, llm_state_file = tempfile.mkstemp(
                            suffix=".json", prefix="ibci_llm_state_")
                        with os.fdopen(fd, "w", encoding="utf-8") as f:
                            json.dump(llm_snapshot, f, ensure_ascii=False)
                        temp_files.append(llm_state_file)
            except Exception:
                llm_state_file = None

        # 构建子进程命令 + 环境变量
        main_py = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "main.py",
        )
        cmd = [
            sys.executable, main_py, "run", abs_path,
            "--result-json", "--export-variables",
            "--root", sub_root_dir,
            "--no-journal",
        ]

        # 环境变量：传递 LLM 状态文件路径（子进程启动时加载）
        env = os.environ.copy()
        if llm_state_file:
            env["IBCI_LLM_STATE_FILE"] = llm_state_file

        # 资源限制（进程级隔离下施加于子进程；仅 POSIX 有效）
        preexec_fn = None
        if policy_obj.resource_limits:
            try:
                import resource as _resource
                limits = policy_obj.resource_limits
                def _apply_rlimits():
                    if "max_memory_mb" in limits:
                        limit_bytes = int(limits["max_memory_mb"] * 1024 * 1024)
                        _resource.setrlimit(_resource.RLIMIT_AS, (limit_bytes, limit_bytes))
                    if "max_cpu_seconds" in limits:
                        _resource.setrlimit(_resource.RLIMIT_CPU,
                                           (limits["max_cpu_seconds"], limits["max_cpu_seconds"]))
                preexec_fn = _apply_rlimits
            except ImportError:
                pass  # 非 POSIX 平台（Windows）：no-op

        # 启动子进程
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=sub_root_dir,
            env=env,
            preexec_fn=preexec_fn,
        )

        # output_holder: (stdout_lines, result_json_str, returncode)
        output_holder: list = [None]
        # 子进程完成的唤醒回调表
        wake_callbacks: list = []

        def _watch_child():
            """看门线程：等待子进程完成，收集 stdout+stderr，触发唤醒回调。

            output_holder[0] = (stdout_lines, result_json_str, returncode, stderr_str)
            """
            stderr_str = ""
            try:
                stdout_lines = []
                result_json_str = None
                # 逐行读 stdout：末行 = result JSON trailer，其余 = print 输出
                for line in proc.stdout:
                    stripped = line.rstrip("\n")
                    if stripped.startswith('{"v":') and '"exit_status"' in stripped:
                        result_json_str = stripped
                    else:
                        stdout_lines.append(stripped)
                        if output_callback:
                            try:
                                output_callback(stripped)
                            except Exception:
                                pass
                        elif not silent:
                            # silent=False（run_isolated）：子输出经父 stdout 可见
                            try:
                                import sys as _sys
                                print(stripped, file=_sys.stdout, flush=True)
                            except Exception:
                                pass
                proc.wait()
                # 读取 stderr（诊断用，不阻塞）
                try:
                    stderr_str = proc.stderr.read() or ""
                except Exception:
                    pass
                output_holder[0] = (stdout_lines, result_json_str, proc.returncode, stderr_str)
            except Exception:
                output_holder[0] = ([], None, -1, "watcher exception")
            finally:
                # 子进程完成 → 触发全部唤醒回调（调度器即时唤醒）
                with self._spawned_tasks_lock:
                    callbacks = wake_callbacks[:]
                    wake_callbacks[:] = []
                for ev in callbacks:
                    ev.set()
                # 关闭管道（防止资源泄漏）
                try:
                    proc.stdout.close()
                except Exception:
                    pass
                try:
                    proc.stderr.close()
                except Exception:
                    pass

        watcher = threading.Thread(
            target=_watch_child, daemon=True,
            name=f"ibci-spawn-watch-{source_label}",
        )
        watcher.start()

        handle = f"spawn_{uuid.uuid4().hex[:16]}"
        with self._spawned_tasks_lock:
            self._spawned_tasks[handle] = (
                proc, watcher, output_holder, temp_files,
                policy_obj.collect_timeout, wake_callbacks,
            )

        return handle

    def register_spawn_wake(self, handle: str, event) -> bool:
        """[IKernelOrchestrator] 为 spawn handle 注册完成通知。

        子进程完成时设置 ``event``（调度器即时唤醒）。返回 False 表示 handle
        已不存在/已完成（调用方退回首轮询）。
        """
        with self._spawned_tasks_lock:
            task = self._spawned_tasks.get(handle)
            if task is None:
                return False
            _proc, watcher, _output, _temp, _to, wake_callbacks = task
            if not watcher.is_alive():
                # 已完成：立即唤醒（竞态下注册晚于完成）
                event.set()
                return True
            wake_callbacks.append(event)
            return True

    def is_spawn_done(self, handle: str) -> bool:
        """[IKernelOrchestrator] 非破坏性检查 spawn handle 的子进程是否已执行完成。

        供 ``HostAwaitable.is_done`` 轮询；不消费 handle（不 pop），与
        ``request_collect`` 的消费语义互补。handle 不存在/已消费视为已完成。
        """
        with self._spawned_tasks_lock:
            task = self._spawned_tasks.get(handle)
        if task is None:
            return True
        return not task[1].is_alive()  # watcher thread

    def request_collect(self, handle: str) -> Dict[str, Any]:
        """
        [IKernelOrchestrator] 阻塞等待 spawn handle 对应的子进程执行完成。
        子进程退出后解析 stdout 末行 JSON（result trailer），提取变量返回。

        collect_timeout（spawn 时由 IsolationPolicy 传入）：
            None = 无界等待（默认，阻塞至子进程退出）；
            正数 = 墙钟等待上限（秒），超时 kill 子进程并抛 RuntimeError。
        """
        with self._spawned_tasks_lock:
            task = self._spawned_tasks.pop(handle, None)
        if task is None:
            raise RuntimeError(f"Unknown spawn handle: {handle!r}. "
                               "The handle may have already been collected or never spawned.")

        proc, watcher, output_holder, temp_files, collect_timeout, _wake_callbacks = task

        # 等待 watcher 线程（它阻塞在 proc.stdout 读取 + proc.wait）
        watcher.join(timeout=collect_timeout)
        if watcher.is_alive():
            # 超时：kill 子进程（与线程不同，进程可被 OS 强杀）
            proc.kill()
            watcher.join(timeout=5)  # 给 watcher 时间清理
            raise RuntimeError(
                f"collect({handle!r}) timed out after {collect_timeout}s; "
                "the isolated child process was killed."
            )

        # 清理临时文件/目录（字符串源 + LLM 状态文件）
        for tf in temp_files:
            try:
                if os.path.isdir(tf):
                    import shutil
                    shutil.rmtree(tf, ignore_errors=True)
                else:
                    os.unlink(tf)
            except OSError:
                pass

        # 解析子进程输出
        stdout_lines, result_json_str, returncode, stderr_str = (
            output_holder[0] if output_holder[0] else ([], None, -1, "")
        )

        if result_json_str is None:
            # 子进程未输出 result JSON（异常退出 / crash）
            raise RuntimeError(
                f"Isolated execution ({handle!r}) failed: child process exited "
                f"with code {returncode} without producing a result JSON. "
                f"stderr: {stderr_str[:500] if stderr_str else '<empty>'}"
            )

        try:
            result_data = json.loads(result_json_str)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Isolated execution ({handle!r}) produced malformed result JSON: {e}"
            ) from e

        # 错误透传（携带结构化错误码——`build_exception_record` 经
        # `getattr(exc, "error_code", None)` 提取）
        if result_data.get("exit_status") != "ok":
            exc = result_data.get("exception")
            exc_msg = exc.get("message") if isinstance(exc, dict) else str(exc)
            err = RuntimeError(
                f"Isolated execution ({handle!r}) raised an exception: {exc_msg}"
            )
            if isinstance(exc, dict):
                err.error_code = exc.get("code")
            raise err

        # 提取变量（子进程已导出为原生 Python 值）
        return result_data.get("variables", {})


# ------------------------------------------------------------------ #
# ihost 子环境 LLM 配置继承（进程级隔离下 = 子进程经 api_config.json
# 自动发现继承父端点/模型/密钥；运行时 model_registry 变化继承
# 归 B2 批次——temp JSON 文件传递 save_plugin_state 快照）
# ------------------------------------------------------------------ #
