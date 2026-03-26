"""
[IES 2.2] Host 宿主能力插件核心实现
"""
from typing import Any, Dict, Optional
from core.extension.ibcext import IbPlugin, ExtensionCapabilities


class HostImplementation(IbPlugin):
    """
    [IES 2.2] Host 宿主能力插件。
    核心级插件，必须继承 IbPlugin 以获取 ServiceContext 能力。
    """
    def __init__(self):
        super().__init__()
        self._capabilities: Optional[ExtensionCapabilities] = None

    def setup(self, capabilities: ExtensionCapabilities):
        self._capabilities = capabilities

    @property
    def plugin_id(self) -> str:
        return "ibc:host"

    @property
    def plugin_name(self) -> str:
        return "Host"

    def save_state(self, path: str):
        if self._capabilities and self._capabilities.service_context:
            self._capabilities.service_context.host_service.save_state(path)

    def load_state(self, path: str):
        if self._capabilities and self._capabilities.service_context:
            self._capabilities.service_context.host_service.load_state(path)

    def run_isolated(self, path: str, policy: Dict[str, Any]) -> bool:
        if self._capabilities and self._capabilities.service_context:
            return self._capabilities.service_context.host_service.run_isolated(path, policy)
        return False

    def get_source(self) -> str:
        if self._capabilities and self._capabilities.service_context:
            return self._capabilities.service_context.host_service.get_source()
        return ""


def create_implementation():
    return HostImplementation()
