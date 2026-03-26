import uuid
import copy
from typing import Any, Dict, List, Optional, Mapping, Callable

from core.runtime.interfaces import (
    IRuntimeScheduler, ExecutionRequest, ExecutionSignal, 
    IsolationLevel, ServiceContext, IExecutionContext,
    IStateProvider
)
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger

# [IES 2.2] 顶层导入核心实现类，已通过接口化解除物理循环依赖
from core.runtime.interpreter.interpreter import Interpreter
from core.runtime.interpreter.service_context import ServiceContextImpl
from core.runtime.host.service import HostService
from core.runtime.serialization.runtime_serializer import RuntimeSerializer, RuntimeDeserializer
from core.runtime.interpreter.handlers.stmt_handler import StmtHandler
from core.runtime.interpreter.handlers.expr_handler import ExprHandler
from core.runtime.interpreter.handlers.import_handler import ImportHandler
from core.runtime.interpreter.llm_executor import LLMExecutorImpl

class RuntimeSchedulerImpl:
    """
    [IES 2.2] RuntimeScheduler 核心调度器实现。
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
        
    def spawn(self, 
              artifact: Any, 
              isolation: str = IsolationLevel.NONE,
              instance_id: Optional[str] = None,
              **kwargs) -> str:
        """
        [IES 2.2] 创建并初始化一个新的解释器实例。
        承担了原 Engine._prepare_interpreter 的装配职责。
        """
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Spawning new interpreter instance (Isolation: {isolation})")
        
        if not instance_id:
            instance_id = f"inst_{uuid.uuid4().hex[:8]}"
            
        # 1. 准备配置参数
        sc = self.service_context
        
        # [IES 2.2] 自动配置工厂 (如果提供了)
        obj_factory = kwargs.get('object_factory', sc.object_factory if sc else None)
        if obj_factory:
            self._configure_factory(obj_factory)
            
        issue_tracker = kwargs.get('issue_tracker', sc.issue_tracker if sc else None)
        registry = kwargs.get('registry', sc.registry if sc else None)
        host_interface = kwargs.get('host_interface')
        debugger = kwargs.get('debugger', sc.debugger if sc else self.debugger)
        root_dir = kwargs.get('root_dir')
        source_provider = kwargs.get('source_provider', sc.source_provider if sc else None)
        compiler = kwargs.get('compiler', sc.compiler if sc else None)
        factory = kwargs.get('factory')
        object_factory = kwargs.get('object_factory', sc.object_factory if sc else None)
        plugin_loader = kwargs.get('plugin_loader')
        kernel_token = kwargs.get('kernel_token')
        output_callback = kwargs.get('output_callback')
        input_callback = kwargs.get('input_callback')

        # 2. 处理隔离逻辑
        effective_registry = registry
        if isolation == IsolationLevel.REGISTRY:
            # TODO: 实现 Registry 克隆逻辑
            pass
            
        effective_artifact = artifact
        if isolation != IsolationLevel.NONE and isinstance(artifact, dict):
            effective_artifact = copy.deepcopy(artifact)

        # 3. 实例化 Interpreter
        interpreter = Interpreter(
            issue_tracker=issue_tracker,
            artifact=effective_artifact,
            registry=effective_registry,
            host_interface=host_interface,
            debugger=debugger,
            root_dir=root_dir,
            source_provider=source_provider,
            compiler=compiler,
            factory=factory,
            object_factory=object_factory,
            plugin_loader=plugin_loader,
            kernel_token=kernel_token,
            output_callback=output_callback,
            input_callback=input_callback,
            instance_id=instance_id
        )

        # 4. 装配 ServiceContext
        sub_sc = interpreter.service_context
        if hasattr(sub_sc, '_scheduler'):
            setattr(sub_sc, '_scheduler', self)
        if hasattr(sub_sc, '_capability_registry') and sc:
            setattr(sub_sc, '_capability_registry', sc.capability_registry)
            
        # 5. 装配 HostService
        host_service = HostService(
            registry=effective_registry,
            execution_context=interpreter._execution_context,
            interop=sub_sc.interop,
            compiler=compiler,
            factory=factory,
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
        [IES 2.2] 顶层执行入口。
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
        [IES 2.2] 分发执行请求。处理隔离运行逻辑。
        """
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, f"Dispatching execution request for node: {request.node_uid}")
        
        # 1. 自动决定隔离级别 (如果请求中未指定)
        isolation = request.isolation or IsolationLevel.SCOPE
        
        # 2. 孵化子环境
        # 获取当前主实例的元数据用于克隆环境
        main_interpreter = self.instances.get(self._main_instance_id)
        if not main_interpreter:
            return ExecutionSignal(type="exit", value=False)
            
        # 这里的 spawn 逻辑需要能继承父环境的部分配置
        sub_id = self.spawn(
            artifact=main_interpreter._artifact, # 共享蓝图
            isolation=isolation,
            registry=main_interpreter.registry,
            host_interface=main_interpreter.host_interface,
            root_dir=main_interpreter.root_dir,
            factory=main_interpreter.factory,
            object_factory=main_interpreter.object_factory,
            plugin_loader=main_interpreter.plugin_loader,
            kernel_token=main_interpreter._kernel_token,
            output_callback=main_interpreter.output_callback,
            input_callback=getattr(main_interpreter, 'input_callback', None)
        )
        
        sub_interpreter = self.instances[sub_id]
        
        # 3. 同步状态 (Sync State)
        # 根据隔离策略，将父环境的状态同步到子环境
        sub_interpreter.sync_state(execution_context.runtime_context, request.payload)
        
        try:
            # 4. 执行子环境
            success = sub_interpreter.execute_module(
                request.node_uid, 
                sub_interpreter.current_module_name, 
                sub_interpreter.runtime_context.current_scope
            )
            return ExecutionSignal(type="exit", value=success)
        finally:
            # 5. 销毁子环境
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
        """[IES 2.2] 配置工厂的 IoC 注册表。从 Engine 迁移而来。"""
        # 1. 注册逻辑处理器 (Handlers)
        factory.register_handler_factory(lambda sc, ec: StmtHandler(sc, ec))
        factory.register_handler_factory(lambda sc, ec: ExprHandler(sc, ec))
        factory.register_handler_factory(lambda sc, ec: ImportHandler(sc, ec))
        
        # 2. 注册 LLM 执行器
        factory.register_llm_executor_factory(lambda sc, ec: LLMExecutorImpl(sc, ec))
