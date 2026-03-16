from typing import Any, Dict, Optional, List, Mapping
from core.runtime.interfaces import (
    IObjectFactory, Scope, IIbClass, IIbModule, IIbObject, IIbList, IIbIntent
)
from core.foundation.registry import Registry
from .runtime_context import ScopeImpl
from core.runtime.objects.kernel import IbModule, IbNativeObject
from core.runtime.objects.builtins import IbBehavior, IbList
from core.runtime.objects.intent import IbIntent

class RuntimeObjectFactory(IObjectFactory):
    """
    运行时对象工厂实现。
    集成了 Registry 和解释器上下文，负责所有核心运行时对象的创建。
    """
    def __init__(self, registry: Registry):
        self._registry = registry

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
        from core.domain.intent_logic import IntentMode, IntentRole
        return IbIntent(
            ib_class=self._registry.get_class("Intent"),
            content=content,
            mode=mode or IntentMode.APPEND,
            tag=tag,
            role=role or IntentRole.BLOCK
        )

    def create_intent_from_node(self, node_uid: str, node_data: Mapping[str, Any], role: Any = None) -> IIbIntent:
        from core.domain.intent_logic import IntentRole
        return IbIntent.from_node_data(
            node_uid,
            node_data,
            ib_class=self._registry.get_class("Intent"),
            role=role or IntentRole.BLOCK
        )
