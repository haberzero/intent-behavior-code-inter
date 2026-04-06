import uuid
import copy
import os
from typing import Any, Dict, List, Optional, Mapping, Callable

from core.runtime.interfaces import (
    IRuntimeScheduler, ExecutionRequest, ExecutionSignal, 
    IsolationLevel, ServiceContext, IExecutionContext,
    IStateProvider
)
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger

# 顶层导入核心实现类，已通过接口化解除物理循环依赖
from core.runtime.interpreter.interpreter import Interpreter
from core.runtime.interpreter.service_context import ServiceContextImpl
from core.runtime.host.service import HostService
from core.runtime.serialization.runtime_serializer import RuntimeSerializer, RuntimeDeserializer
from core.runtime.interpreter.handlers.stmt_handler import StmtHandler
from core.runtime.interpreter.handlers.expr_handler import ExprHandler
from core.runtime.interpreter.handlers.import_handler import ImportHandler
from core.runtime.interpreter.llm_executor import LLMExecutorImpl
from core.runtime.module_system.discovery import ModuleDiscoveryService
from core.runtime.module_system.loader import ModuleLoader

class RuntimeSchedulerImpl:
    """
     RuntimeScheduler 核心调度器实现。
    负责管理解释器实例生命周期、资源调度及宏观状态同步。
    """
    def __init__(self, service_context: Optional[ServiceContext] = None):
        self.service_context = service_context
        self.debugger = service_context.debugger if service_context else core_debugger
        self.instances: Dict[str, Any] = {} # instance_id -> Interpreter
        self._main_instance_id: Optional[str] = None
        
    def hydrate(self, service_context: ServiceContext):
        """延迟水化调度器，注入运行时服务"""
        self.service_context = service_context
        self.debugger = service_context.debugger
    # TODO: 可能是代码异味？此处是智能体快速vibe实现，还没严格审查，暂时保留
    def _resolve_builtin_path(self) -> str:
        """标准化内置模块路径发现逻辑"""
        import ibci_modules
        return os.path.dirname(os.path.abspath(ibci_modules.__file__))

    def spawn(self, 
              artifact: Any, 
              isolation: str = IsolationLevel.NONE,
              instance_id: Optional[str] = None,
              **kwargs) -> str:
        """
         创建并初始化一个新的解释器实例。
        承担了原 Engine._prepare_interpreter 的装配职责。
        """
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Spawning new interpreter instance (Isolation: {isolation})")
        
        if not instance_id:
            instance_id = f"inst_{uuid.uuid4().hex[:8]}"
            
        # 1. 准备配置参数
        sc = self.service_context
        
        # 自动配置工厂 (如果提供了)
        obj_factory = kwargs.get('object_factory', sc.object_factory if sc else None)
        if obj_factory:
            self._configure_factory(obj_factory)
            
        root_dir = kwargs.get('root_dir')
        
        # 如果是隔离模式，必须确保 root_dir 已正确设置
        if isolation != IsolationLevel.NONE and not root_dir:
             if isinstance(artifact, str) and (os.path.isabs(artifact) or os.path.exists(artifact)):
                 root_dir = os.path.dirname(os.path.abspath(artifact))
        
        # 2. 处理隔离逻辑 (Registry, HostInterface, PluginLoader)
        effective_registry = kwargs.get('registry', sc.registry if sc else None)
        effective_host_interface = kwargs.get('host_interface')
        effective_plugin_loader = kwargs.get('plugin_loader')
        
        if isolation != IsolationLevel.NONE:
            # A. 克隆注册表，确保子环境对类的修改不影响父环境
            if effective_registry:
                self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, "Cloning Registry for isolated instance")
                effective_registry = effective_registry.clone()
            
            # B. [Total Isolation] 重新发现并加载子环境特有的插件
            if root_dir:
                self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Total Isolation: Re-discovering plugins for {root_dir}")
                
                builtin_path = self._resolve_builtin_path()
                plugins_path = os.path.join(root_dir, "plugins")
                
                # 重新执行发现流程
                discovery = ModuleDiscoveryService([builtin_path, plugins_path])
                effective_host_interface = discovery.discover_all(effective_registry)
                
                # 创建全新的插件加载器
                sub_loader = ModuleLoader(
                    [builtin_path, plugins_path], 
                    capability_registry=sc.capability_registry if sc else None
                )
                # 定义加载钩子
                effective_plugin_loader = lambda sc_sub, ec, im: sub_loader.load_and_register_all(sc_sub, ec)

        # 3. 实例化 Interpreter (不再处理编译，编译由外界传入或由 Orchestrator 负责)
        effective_artifact = artifact
        if isolation != IsolationLevel.NONE and isinstance(effective_artifact, dict):
            # 隔离模式下进行深拷贝防止交叉污染
            effective_artifact = copy.deepcopy(effective_artifact)

        # 4. 实例化 Interpreter
        interpreter = Interpreter(
            issue_tracker=kwargs.get('issue_tracker', sc.issue_tracker if sc else None),
            artifact=effective_artifact,
            registry=effective_registry,
            host_interface=effective_host_interface,
            debugger=kwargs.get('debugger', sc.debugger if sc else self.debugger),
            root_dir=root_dir,
            source_provider=kwargs.get('source_provider', sc.source_provider if sc else None),
            factory=kwargs.get('factory'),
            object_factory=kwargs.get('object_factory', sc.object_factory if sc else None),
            plugin_loader=effective_plugin_loader,
            kernel_token=kwargs.get('kernel_token'),
            output_callback=kwargs.get('output_callback'),
            input_callback=kwargs.get('input_callback'),
            instance_id=instance_id,
            strict_mode=kwargs.get('strict_mode', True),
            orchestrator=kwargs.get('orchestrator', getattr(sc, 'orchestrator', None) if sc else None),
            entry_file=kwargs.get('entry_file'),
            entry_dir=kwargs.get('entry_dir')
        )

        # 4. 装配 ServiceContext
        sub_sc = interpreter.service_context
        if hasattr(sub_sc, 'hydrate'):
             sub_sc.hydrate(
                 issue_tracker=kwargs.get('issue_tracker', sc.issue_tracker if sc else None),
                 registry=effective_registry,
                 host_interface=effective_host_interface,
                 debugger=kwargs.get('debugger', sc.debugger if sc else self.debugger),
                 root_dir=root_dir,
                 source_provider=kwargs.get('source_provider', sc.source_provider if sc else None),
                 orchestrator=getattr(sc, 'orchestrator', None) if sc else None,
                 execution_context=interpreter._execution_context,
                 interop=sub_sc.interop,
                 factory=kwargs.get('factory'),
                 setup_context_callback=interpreter.setup_context,
                 object_factory=kwargs.get('object_factory', sc.object_factory if sc else None),
                 scheduler=self
             )
            
        # 5. 装配 HostService
        # TODO: 此处的getattr是否是代码异味？
        host_service = HostService(
            registry=effective_registry,
            execution_context=interpreter._execution_context,
            interop=sub_sc.interop,
            orchestrator=getattr(sc, 'orchestrator', None) if sc else None,
            setup_context_callback=interpreter.setup_context,
            get_current_module_callback=lambda: interpreter.current_module_name
        )
        if hasattr(sub_sc, '_host_service'):
            setattr(sub_sc, '_host_service', host_service)

        # 6. 注册实例
        self.instances[instance_id] = interpreter
        if not self._main_instance_id:
            self._main_instance_id = instance_id
            
        return instance_id

    def execute(self, artifact: Any, variables: Optional[Dict[str, Any]] = None, output_callback: Optional[Callable[[str], None]] = None) -> bool:
        """
         顶层执行入口。
        调度一个解释器实例并开始执行。
        """
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, "Starting top-level execution via scheduler")
        
        # 获取或创建主实例
        instance_id = self._main_instance_id
        if not instance_id or instance_id not in self.instances:
            # 如果尚未 spawn，则报错。顶层执行应由 Engine 调用 spawn 后触发。
            # 目前为了兼容 Engine.execute，我们假设实例已在 _prepare_interpreter 中创建
            interpreter = getattr(self.service_context, 'interpreter', None)
        else:
            interpreter = self.instances[instance_id]

        if not interpreter:
            return False

        # 2. 注入初始变量
        if variables:
            for name, val in variables.items():
                # 确保变量被正确装箱
                if not hasattr(val, 'ib_class'):
                    val = interpreter.registry.box(val)
                interpreter.runtime_context.define_variable(name, val)
        
        # 3. 启动执行
        return interpreter.run()

    def dispatch(self, request: ExecutionRequest, execution_context: IExecutionContext) -> ExecutionSignal:
        """
         分发执行请求。处理隔离运行逻辑。
        """
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Dispatching execution request for node: {request.node_uid}")
        
        # 1. 自动决定隔离级别 (如果请求中未指定)
        isolation = request.isolation or IsolationLevel.SCOPE
        
        # 2. 获取主实例信息
        main_interpreter = self.instances.get(self._main_instance_id)
        if not main_interpreter:
            return ExecutionSignal(type="exit", value=False)
            
        # 3. 孵化子实例 (所有隔离细节已下沉到 spawn)
        sub_id = self.spawn(
            artifact=request.node_uid, # 必须是已编译好的产物字典
            isolation=isolation,
            instance_id=None,
            # 继承必要的全局上下文
            factory=main_interpreter.factory,
            object_factory=main_interpreter.object_factory,
            kernel_token=main_interpreter._kernel_token,
            output_callback=main_interpreter.output_callback,
            input_callback=getattr(main_interpreter, 'input_callback', None),
            source_provider=main_interpreter.source_provider
        )
        
        sub_interpreter = self.instances[sub_id]
        
        # 4. 同步状态 (Sync State)
        sub_interpreter.sync_state(execution_context.runtime_context, request.payload)
        
        try:
            # 5. 执行子环境
            # 如果 node_uid 是文件，Interpreter 会识别并执行
            success = sub_interpreter.execute_module(
                request.node_uid, 
                sub_interpreter.current_module_name, 
                sub_interpreter.runtime_context.current_scope
            )
            return ExecutionSignal(type="exit", value=success)
        finally:
            # 6. 销毁子环境
            self.terminate(sub_id)

    def snapshot(self, instance_id: str) -> Dict[str, Any]:
        """
        获取指定实例的状态快照。
        """
        self.debugger.trace(CoreModule.RUNTIME, DebugLevel.DETAIL, f"Creating snapshot for instance: {instance_id}")
        interpreter = self.instances.get(instance_id)
        if not interpreter:
            return {}
            
        serializer = RuntimeSerializer(interpreter.registry)
        return serializer.serialize_context(
            interpreter.runtime_context,
            execution_context=interpreter._execution_context
        )

    def restore(self, instance_id: str, snapshot: Dict[str, Any]) -> None:
        """
        恢复指定实例的状态。
        """
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL, f"Restoring snapshot for instance: {instance_id}")
        interpreter = self.instances.get(instance_id)
        if not interpreter:
            return
            
        deserializer = RuntimeDeserializer(interpreter.registry, factory=interpreter.object_factory)
        new_ctx = deserializer.deserialize_context(snapshot)
        
        # 更新解释器的上下文
        interpreter.runtime_context = new_ctx
        # 注意：这里可能还需要重新绑定执行上下文
        interpreter._execution_context.runtime_context = new_ctx

    def terminate(self, instance_id: str) -> None:
        """
        销毁指定的解释器实例。
        """
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Terminating instance: {instance_id}")
        if instance_id in self.instances:
            del self.instances[instance_id]
            if self._main_instance_id == instance_id:
                self._main_instance_id = None

    def _configure_factory(self, factory: Any):
        """ 配置工厂的 IoC 注册表。从 Engine 迁移而来。"""
        # 1. 注册逻辑处理器 (Handlers)
        factory.register_handler_factory(lambda sc, ec: StmtHandler(sc, ec))
        factory.register_handler_factory(lambda sc, ec: ExprHandler(sc, ec))
        factory.register_handler_factory(lambda sc, ec: ImportHandler(sc, ec))
        
        # 2. 注册 LLM 执行器
        factory.register_llm_executor_factory(lambda sc, ec: LLMExecutorImpl(sc, ec))
