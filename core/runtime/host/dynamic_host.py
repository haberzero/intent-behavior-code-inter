from typing import Any, Dict, Optional
from core.extension.ibcext import IbPlugin, method
from core.runtime.host.isolation_policy import IsolationPolicy


class DynamicHost(IbPlugin):
    """
    [IES 2.1] 动态宿主插件。
    实现运行时持久化、隔离执行、事务快照和元编程能力。
    """
    @property
    def plugin_id(self) -> str:
        return "core:dynamic_host"

    @property
    def plugin_name(self) -> str:
        return "DynamicHost"

    def __init__(self):
        super().__init__()

    def setup(self, capabilities: Any) -> None:
        super().setup(capabilities)

    @method("save_state")
    def save_state(self, path: str) -> bool:
        """[Meta] 显式保存当前运行现场到文件"""
        sc = self._capabilities.service_context
        if sc and sc.host_service:
            try:
                sc.host_service.save_state(path)
                return True
            except Exception:
                return False
        return False

    @method("load_state")
    def load_state(self, path: str) -> bool:
        """[Meta] 从文件加载并覆盖当前运行现场"""
        sc = self._capabilities.service_context
        if sc and sc.host_service:
            try:
                sc.host_service.load_state(path)
                return True
            except Exception:
                return False
        return False

    @method("run_isolated")
    def run_isolated(self, path: str, policy: Dict[str, Any]) -> bool:
        """[Meta] 隔离运行另一个 ibci 文件"""
        sc = self._capabilities.service_context
        if sc and sc.host_service:
            try:
                isolation_policy = IsolationPolicy.from_dict(policy) if isinstance(policy, dict) else policy
                return sc.host_service.run_isolated(path, isolation_policy.to_dict())
            except Exception:
                return False
        return False

    @method("get_source")
    def get_source(self) -> str:
        """[Meta] 获取当前模块的源代码"""
        sc = self._capabilities.service_context
        if sc and sc.host_service:
            return sc.host_service.get_source()
        return ""

    @method("generate_and_run")
    def generate_and_run(self, code: str, policy: Dict[str, Any]) -> bool:
        """[IES 2.1] 动态生成 IBCI 代码并执行"""
        import tempfile
        import os
        sc = self._capabilities.service_context
        if not sc or not sc.compiler:
            return False

        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.ibci',
                delete=False,
                encoding='utf-8'
            ) as f:
                f.write(code)
                temp_path = f.name

            try:
                return self.run_isolated(temp_path, policy)
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        except Exception:
            return False


def create_implementation() -> DynamicHost:
    """工厂函数：创建 DynamicHost 实现"""
    return DynamicHost()
