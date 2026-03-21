from typing import Any, Dict, Optional
from core.extension import ibcext

class HostImplementation(ibcext.IbPlugin):
    """
    Host 2.1: 宿主能力插件。
    """
    def __init__(self):
        super().__init__()

    @ibcext.method("save_state")
    def ib_save_state(self, path: str):
        sc = self._capabilities.service_context
        if sc:
            sc.host_service.save_state(path)

    @ibcext.method("load_state")
    def ib_load_state(self, path: str):
        sc = self._capabilities.service_context
        if sc:
            sc.host_service.load_state(path)

    @ibcext.method("run_isolated")
    def ib_run(self, path: str, policy: Dict[str, Any]) -> bool:
        sc = self._capabilities.service_context
        if sc:
            return sc.host_service.run_isolated(path, policy)
        return False

    @ibcext.method("get_source")
    def ib_get_source(self) -> str:
        sc = self._capabilities.service_context
        if sc:
            return sc.host_service.get_source()
        return ""

def create_implementation():
    return HostImplementation()
