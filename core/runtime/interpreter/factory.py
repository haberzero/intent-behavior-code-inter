from typing import Any, Dict, Optional
from core.runtime.interfaces import IObjectFactory, Scope, Registry, List
from .runtime_context import ScopeImpl
from core.runtime.objects.kernel import IbModule, IbNativeObject
from core.runtime.objects.builtins import IbBehavior

class RuntimeObjectFactory(IObjectFactory):
    """
    运行时对象工厂实现。
    集成了 Registry 和解释器上下文，负责所有核心运行时对象的创建。
    """
    def __init__(self, registry: Registry):
        self._registry = registry

    def create_module(self, name: str, scope: Scope) -> Any:
        return IbModule(name, scope, registry=self._registry)

    def create_scope(self, parent: Optional[Scope] = None) -> Scope:
        return ScopeImpl(parent=parent, registry=self._registry)

    def create_native_object(self, py_obj: Any, ib_class: Any, vtable: Optional[Dict[str, Any]] = None) -> Any:
        return IbNativeObject(py_obj, ib_class, vtable=vtable)

    def create_behavior(self, node_uid: str, captured_intents: List[Any], expected_type: Optional[str] = None) -> Any:
        return IbBehavior(node_uid, captured_intents, ib_class=self._registry.get_class("behavior"), expected_type=expected_type)
