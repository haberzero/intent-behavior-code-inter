from typing import Dict, Any, Optional, TYPE_CHECKING
from core.extension.ibcext import IbPlugin, ExtensionCapabilities

if TYPE_CHECKING:
    from core.runtime.interfaces import IIbObject


class IDbgPlugin(IbPlugin):
    """
    IDBG 内核观察者插件。
    核心级插件，必须继承 IbPlugin 以获取 stack_inspector 和 state_reader 能力。
    """
    def __init__(self):
        super().__init__()
        self.stack_inspector = None
        self.state_reader = None
        self._capabilities: Optional[ExtensionCapabilities] = None

    def setup(self, capabilities: ExtensionCapabilities):
        self._capabilities = capabilities
        self.stack_inspector = capabilities.stack_inspector
        self.state_reader = capabilities.state_reader
        # 向能力注册表注册自己为 Debugger Provider
        capabilities.expose("debugger_provider", self)

    def vars(self):
        if not self.state_reader: return {}
        return self.state_reader.get_vars()

    def last_llm(self) -> Dict[str, Any]:
        if not self._capabilities:
            return {}

        if self._capabilities.llm_executor:
            return self._capabilities.llm_executor.get_last_call_info()

        if self._capabilities.llm_provider:
            return self._capabilities.llm_provider.get_last_call_info()

        return {}

    def env(self) -> Dict[str, Any]:
        if not self._capabilities or not self._capabilities.stack_inspector:
            return {}

        inspector = self._capabilities.stack_inspector
        return {
            "instruction_count": inspector.get_instruction_count(),
            "call_stack_depth": inspector.get_call_stack_depth(),
            "active_intents": inspector.get_active_intents()
        }

    def fields(self, obj: Any) -> Dict[str, Any]:
        if hasattr(obj, 'fields'):
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


def create_implementation():
    return IDbgPlugin()
