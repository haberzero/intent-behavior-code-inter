import uuid
from typing import Any, Dict, List, Optional, Callable

from core.runtime.interfaces import (
    IRuntimeScheduler, ServiceContext
)
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger

# 顶层导入核心实现类，通过接口化解除物理循环依赖
from core.runtime.interpreter.interpreter import Interpreter
from core.runtime.interpreter.service_context import ServiceContextImpl
from core.runtime.host.service import HostService
from core.runtime.serialization.runtime_serializer import RuntimeSerializer, RuntimeDeserializer
from core.runtime.interpreter.llm_executor import LLMExecutorImpl

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

    def spawn(self, 
              artifact: Any, 
              instance_id: Optional[str] = None,
              **kwargs) -> str:
        """
         创建并初始化一个新的解释器实例。
        承担了原 Engine._prepare_interpreter 的装配职责。
        """
        self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.BASIC, "Spawning new interpreter instance")
        
        if not instance_id:
            instance_id = f"inst_{uuid.uuid4().hex[:8]}"
            
        # 1. 准备配置参数
        sc = self.service_context
        
        # 自动配置工厂 (如果提供了)
        obj_factory = kwargs.get('object_factory', sc.object_factory if sc else None)
        if obj_factory:
            self._configure_factory(obj_factory)
            
        root_dir = kwargs.get('root_dir')

        # 2. 准备运行时组件（由 Engine 传入，不再在调度器内重发现）
        effective_registry = kwargs.get('registry', sc.registry if sc else None)
        effective_host_interface = kwargs.get('host_interface')
        effective_plugin_loader = kwargs.get('plugin_loader')
        
        # 3. 实例化 Interpreter (不再处理编译，编译由外界传入或由 Orchestrator 负责)
        interpreter = Interpreter(
            issue_tracker=kwargs.get('issue_tracker', sc.issue_tracker if sc else None),
            artifact=artifact,
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

        # 4. 装配 ServiceContext（延迟注入，打破循环依赖）
        sub_sc = interpreter.service_context
        sub_sc.set_scheduler(self)
        sub_sc.set_capability_registry(kwargs.get('capability_registry'))

        # 5. 装配 HostService
        host_service = HostService(
            registry=effective_registry,
            execution_context=interpreter._execution_context,
            interop=sub_sc.interop,
            orchestrator=sc.orchestrator if sc else None,
            setup_context_callback=interpreter.setup_context,
            get_current_module_callback=lambda: interpreter.current_module_name
        )
        sub_sc.set_host_service(host_service)

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
            # 这里沿用 Engine.execute 的当前调用约定：实例已在 _prepare_interpreter 中创建。
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
        """ 配置工厂的 IoC 注册表。"""
        # VMExecutor CPS dispatch table 是唯一的 AST→执行映射，无需注册。
        
        # 注册 LLM 执行器
        factory.register_llm_executor_factory(lambda sc, ec: LLMExecutorImpl(sc, ec))
