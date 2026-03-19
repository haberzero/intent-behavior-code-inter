from typing import Dict, Any, Optional
from core.foundation.interfaces import IIbObject
from core.extension import ibcext

class IDbgPlugin(ibcext.IbPlugin):
    """
    IDbg 2.1: 内核观察者。
    """
    def __init__(self):
        super().__init__()
        self.stack_inspector = None
        self.state_reader = None

    def setup(self, capabilities):
        super().setup(capabilities)
        self.stack_inspector = capabilities.stack_inspector
        self.state_reader = capabilities.state_reader

    @ibcext.method("vars")
    def get_vars(self):
        if not self.state_reader: return {}
        return self.state_reader.get_vars()

    @ibcext.method("last_llm")
    def get_last_llm(self) -> Dict[str, Any]:
        if not self._capabilities:
            return {}

        if self._capabilities.llm_executor:
            return self._capabilities.llm_executor.get_last_call_info()

        if self._capabilities.llm_provider:
            return self._capabilities.llm_provider.get_last_call_info()

        return {}

    @ibcext.method("env")
    def get_env(self) -> Dict[str, Any]:
        if not self._capabilities or not self._capabilities.stack_inspector:
            return {}

        inspector = self._capabilities.stack_inspector
        return {
            "instruction_count": inspector.get_instruction_count(),
            "call_stack_depth": inspector.get_call_stack_depth(),
            "active_intents": inspector.get_active_intents()
        }

    @ibcext.method("fields")
    def inspect_fields(self, obj: Any) -> Dict[str, Any]:
        if isinstance(obj, IIbObject):
            if hasattr(obj, 'serialize_for_debug'):
                data = obj.serialize_for_debug()
            else:
                data = obj.fields

            def _to_native(v):
                if hasattr(v, 'to_native'): return v.to_native()
                if isinstance(v, dict): return {k: _to_native(i) for k, i in v.items()}
                if isinstance(v, list): return [_to_native(i) for i in v]
                return v

            return {k: _to_native(v) for k, v in data.items()}
        return {}
