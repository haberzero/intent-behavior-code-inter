from typing import Any, Dict, Optional
from core.runtime.interfaces import ServiceContext
from core.extension import sdk as ibci

class HostImplementation:
    """
    IBCI 2.0 动态宿主第一方模块实现。
    作为内核 core/runtime/host/service.py 的薄包装层。
    """
    def __init__(self):
        self.context: Optional[ServiceContext] = None

    def setup(self, service_context: ServiceContext):
        """IES 2.0 自动依赖注入协议"""
        self.context = service_context

    @ibci.method("save_state")
    def ib_save_state(self, path: str):
        """[Meta] 显式保存当前运行现场到文件"""
        if self.context:
            self.context.host_service.save_state(path)

    @ibci.method("load_state")
    def ib_load_state(self, path: str):
        """[Meta] 从文件加载并覆盖当前运行现场"""
        if self.context:
            self.context.host_service.load_state(path)

    @ibci.method("run")
    def ib_run(self, path: str, policy: Dict[str, Any]) -> bool:
        """[Meta] 隔离/继承运行另一个 ibci 文件"""
        if self.context:
            return self.context.host_service.run_isolated(path, policy)
        return False

    @ibci.method("get_source")
    def ib_get_source(self) -> str:
        """[Meta] 获取当前模块的源代码"""
        if self.context:
            return self.context.host_service.get_source()
        return ""

def create_implementation():
    return HostImplementation()
