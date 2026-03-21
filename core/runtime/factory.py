from typing import Any, Dict, Optional, List, Mapping, Callable
from core.runtime.interfaces import (
    IObjectFactory, Scope, IIbClass, IIbModule, IIbObject, IIbList, IIbIntent
)
from core.kernel.registry import KernelRegistry

# 这些导入需要指向它们的新物理位置
from core.runtime.interpreter.runtime_context import ScopeImpl
from core.runtime.objects.kernel import IbModule, IbNativeObject
from core.runtime.objects.builtins import IbBehavior, IbList
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole

class RuntimeObjectFactory(IObjectFactory):
    """
    运行时对象工厂实现。
    [IES 2.1 IoC Refactor] 
    1. 物理归位：迁移至 core/runtime，作为公共基础设施。
    2. 控制反转：采用注册制，消除对逻辑组件（Handlers/Executor）的硬编码物理引用。
    """
    def __init__(self, registry: KernelRegistry):
        self._registry = registry
        self._handler_factories: List[Callable] = []
        self._llm_executor_factory: Optional[Callable] = None

    # --- IoC 注册接口 ---

    def register_handler_factory(self, factory: Callable) -> None:
        """注册语句/表达式处理器的构造工厂"""
        self._handler_factories.append(factory)

    def register_llm_executor_factory(self, factory: Callable) -> None:
        """注册 LLM 执行器的构造工厂"""
        self._llm_executor_factory = factory

    # --- 对象创建接口 ---

    def create_module(self, name: str, scope: Scope) -> IIbModule:
        return IbModule(name, scope, registry=self._registry)

    def create_scope(self, parent: Optional[Scope] = None) -> Scope:
        return ScopeImpl(parent=parent, registry=self._registry)

    def create_native_object(self, py_obj: Any, ib_class: IIbClass, vtable: Optional[Dict[str, Any]] = None) -> IIbObject:
        return IbNativeObject(py_obj, ib_class, vtable=vtable)

    def create_behavior(self, node_uid: str, captured_intents: List[Any], expected_type: Optional[str] = None) -> Any:
        return IbBehavior(node_uid, captured_intents, ib_class=self._registry.get_class("behavior"), expected_type=expected_type)

    def create_list(self, elements: List[IIbObject]) -> IIbList:
        return IbList(elements, ib_class=self._registry.get_class("list"))

    def create_intent(self, content: str = "", mode: Any = None, tag: Optional[str] = None, role: Any = None) -> IIbIntent:
        return IbIntent(
            ib_class=self._registry.get_class("Intent"),
            content=content,
            mode=mode or IntentMode.APPEND,
            tag=tag,
            role=role or IntentRole.BLOCK
        )

    def create_intent_from_node(self, node_uid: str, node_data: Mapping[str, Any], role: Any = None) -> IIbIntent:
        return IbIntent.from_node_data(
            node_uid,
            node_data,
            ib_class=self._registry.get_class("Intent"),
            role=role or IntentRole.BLOCK
        )

    # --- 逻辑组件创建 (IoC 实现) ---

    def create_handlers(self, service_context: Any, execution_context: Any) -> List[Any]:
        """[IES 2.1 IoC] 动态创建已注册的所有处理器，无物理硬编码引用"""
        return [f(service_context, execution_context) for f in self._handler_factories]

    def create_llm_executor(self, service_context: Any, execution_context: Any) -> Any:
        """[IES 2.1 IoC] 动态创建已注册的 LLM 执行器"""
        if not self._llm_executor_factory:
            # 这种情况下通常意味着系统装配逻辑有误
            raise RuntimeError("RuntimeObjectFactory: LLMExecutor factory not registered.")
        return self._llm_executor_factory(service_context, execution_context)
