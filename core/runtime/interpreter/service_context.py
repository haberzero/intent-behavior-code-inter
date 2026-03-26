from typing import Any, Optional, TYPE_CHECKING, Callable
from core.runtime.objects.kernel import IbObject
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger
from core.base.interfaces import IssueTracker, ISourceProvider, ICompilerService
from core.runtime.interfaces import ServiceContext

if TYPE_CHECKING:
    from core.runtime.interfaces import (
        LLMExecutor, ModuleManager, IObjectFactory, InterOp, 
        PermissionManager, IHostService, Interpreter, IRuntimeScheduler
    )

class ServiceContextImpl(ServiceContext):
    """
    [IES 2.1 Regularization] 运行时核心服务上下文实现。
    作为横向服务定位器，它持有一组独立的服务组件。
    它不持有 Interpreter 实例，也不提供对 RuntimeContext 的访问，以实现职责单一化。
    """
    def __init__(self, 
                 issue_tracker: IssueTracker,
                 llm_executor: 'LLMExecutor',
                 module_manager: 'ModuleManager',
                 interop: 'InterOp',
                 permission_manager: 'PermissionManager',
                 object_factory: 'IObjectFactory',
                 registry: Any,
                 host_service: Optional['IHostService'] = None,
                 source_provider: Optional[ISourceProvider] = None,
                 compiler: Optional[ICompilerService] = None,
                 debugger: Any = None,
                 output_callback: Optional[Callable[[str], None]] = None,
                 input_callback: Optional[Callable[[str], str]] = None,
                 scheduler: Optional['IRuntimeScheduler'] = None,
                 capability_registry: Optional[Any] = None,
                 interpreter: Optional['Interpreter'] = None):
        self._issue_tracker = issue_tracker
        self._llm_executor = llm_executor
        self._module_manager = module_manager
        self._interop = interop
        self._permission_manager = permission_manager
        self._object_factory = object_factory
        self._registry = registry
        self._host_service = host_service
        self._source_provider = source_provider
        self._compiler = compiler
        self._debugger = debugger
        self._output_callback = output_callback
        self._input_callback = input_callback
        self._scheduler = scheduler
        self._capability_registry = capability_registry
        self._interpreter = interpreter

    @property
    def scheduler(self) -> Optional['IRuntimeScheduler']:
        return self._scheduler

    @property
    def capability_registry(self) -> Optional[Any]:
        return self._capability_registry

    @property
    def interpreter(self) -> Optional['Interpreter']:
        return self._interpreter

    @property
    def output_callback(self) -> Optional[Callable[[str], None]]:
        return self._output_callback

    @output_callback.setter
    def output_callback(self, value: Callable[[str], None]):
        self._output_callback = value

    @property
    def input_callback(self) -> Optional[Callable[[str], str]]:
        return self._input_callback

    @input_callback.setter
    def input_callback(self, value: Callable[[str], str]):
        self._input_callback = value

    @property
    def registry(self) -> Any:
        return self._registry

    @property
    def issue_tracker(self) -> IssueTracker:
        return self._issue_tracker

    @property
    def llm_executor(self) -> 'LLMExecutor':
        return self._llm_executor

    @property
    def module_manager(self) -> 'ModuleManager':
        return self._module_manager

    @property
    def object_factory(self) -> 'IObjectFactory':
        return self._object_factory

    @property
    def interop(self) -> 'InterOp':
        return self._interop

    @property
    def permission_manager(self) -> 'PermissionManager':
        return self._permission_manager

    @property
    def host_service(self) -> Optional['IHostService']:
        return self._host_service

    @property
    def source_provider(self) -> Optional[ISourceProvider]:
        return self._source_provider

    @property
    def compiler(self) -> Optional[ICompilerService]:
        return self._compiler

    @property
    def debugger(self) -> Any:
        return self._debugger
