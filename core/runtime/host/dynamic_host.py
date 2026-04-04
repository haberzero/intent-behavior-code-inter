from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from core.extension.ibcext import IbPlugin
from core.runtime.host.isolation_policy import IsolationPolicy


@dataclass
class IsolatedRunResult:
    """
     隔离子环境运行结果。
    替代简单的 bool 返回值，提供完整的执行状态信息。
    """
    success: bool
    diagnostics: List[Any] = field(default_factory=list)
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    return_value: Optional[Any] = None


def _dynamic_host_vtable() -> Dict[str, Any]:
    """ DynamicHost 虚表"""
    impl = DynamicHost()
    return {
        "save_state": impl.save_state,
        "load_state": impl.load_state,
        "run_isolated": impl.run_isolated,
        "get_source": impl.get_source,
        "generate_and_run": impl.generate_and_run,
    }


class DynamicHost(IbPlugin):
    """
     动态宿主插件。
    实现运行时持久化、隔离执行、事务快照和元编程能力。
    """
    def __init__(self):
        super().__init__()
        self._ibcext_vtable_func = _dynamic_host_vtable

    @property
    def plugin_id(self) -> str:
        return "core:dynamic_host"

    @property
    def plugin_name(self) -> str:
        return "DynamicHost"

    def setup(self, capabilities: Any) -> None:
        super().setup(capabilities)

    def _validate_return_value(self, value: Any) -> Any:
        """
        [IES 2.1 Security] 验证返回值是否允许从隔离环境返回。
        只允许基本内置类型 (int/str/bool/float/none) 返回。
        """
        if value is None:
            return self.registry.get_none() if hasattr(self, 'registry') and self.registry else None

        from core.runtime.objects.kernel import IbObject
        if not isinstance(value, IbObject):
            return value

        desc = getattr(value, 'descriptor', None)
        if not desc:
            return value

        axiom = getattr(desc, '_axiom', None)
        if axiom and hasattr(axiom, 'can_return_from_isolated'):
            if axiom.can_return_from_isolated():
                return value

        allowed = {"int", "str", "bool", "float", "None"}
        type_name = getattr(desc, 'name', None)
        if type_name in allowed:
            return value

        return self.registry.get_none() if hasattr(self, 'registry') and self.registry else None

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

    def run_isolated(self, path: str, policy: Dict[str, Any]) -> 'IsolatedRunResult':
        """[Meta] 隔离运行另一个 ibci 文件"""
        sc = self._capabilities.service_context
        if sc and sc.host_service:
            try:
                isolation_policy = IsolationPolicy.from_dict(policy) if isinstance(policy, dict) else policy
                result = sc.host_service.run_isolated(path, isolation_policy.to_dict())
                validated_value = self._validate_return_value(result)
                return IsolatedRunResult(
                    success=True,
                    diagnostics=[],
                    exception_type=None,
                    exception_message=None,
                    return_value=validated_value
                )
            except Exception as e:
                return IsolatedRunResult(
                    success=False,
                    diagnostics=[],
                    exception_type=type(e).__name__,
                    exception_message=str(e),
                    return_value=None
                )
        return IsolatedRunResult(success=False, diagnostics=[], exception_type=None, exception_message=None, return_value=None)

    def get_source(self) -> str:
        """[Meta] 获取当前模块的源代码"""
        sc = self._capabilities.service_context
        if sc and sc.host_service:
            return sc.host_service.get_source()
        return ""

    def generate_and_run(self, code: str, policy: Dict[str, Any]) -> 'IsolatedRunResult':
        """ 动态生成 IBCI 代码并执行"""
        import tempfile
        import os
        sc = self._capabilities.service_context
        if not sc or not sc.compiler:
            return IsolatedRunResult(
                success=False,
                diagnostics=[],
                exception_type="RuntimeError",
                exception_message="Compiler not available",
                return_value=None
            )

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
        except Exception as e:
            return IsolatedRunResult(
                success=False,
                diagnostics=[],
                exception_type=type(e).__name__,
                exception_message=str(e),
                return_value=None
            )


def create_implementation() -> DynamicHost:
    """工厂函数：创建 DynamicHost 实现"""
    return DynamicHost()
