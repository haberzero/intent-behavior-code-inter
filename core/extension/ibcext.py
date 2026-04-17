from typing import Any, Callable, Optional, List, Dict
from abc import ABC, abstractmethod

from core.extension.exceptions import PluginError, InterpreterError, CompilerError
from core.extension.capabilities import PluginCapabilities, ExtensionCapabilities


# ---------------------------------------------------------------------------
# IBC-Inter 插件体系层次说明
# ---------------------------------------------------------------------------
#
# IBC-Inter 插件分为两个层次：
#
# 【非侵入层（Non-Invasive Level）】
#   - 零内核依赖：_spec.py 只含纯 dict vtable，实现类不导入 core.*
#   - 通过 setup(capabilities) 接收注入的能力容器，只按需取用浅层能力
#     （如 capabilities.service_context.permission_manager）
#   - 适合：数学计算、JSON、HTTP、文件操作等无状态工具性插件
#   - 代表模块：ibci_math, ibci_json, ibci_time, ibci_net, ibci_schema
#
#   【例外：ibci_file（轻量依赖型）】
#     ibci_file 导入了 core.runtime.path.IbPath（纯 @dataclass(frozen=True)，无状态）
#     并通过 capabilities.execution_context.resolve_path() 进行路径解析。
#     IbPath 没有解释器状态依赖，属于可接受的工具类导入，但严格意义上不符合
#     "零内核依赖"定义。因此 ibci_file 可视为"轻量依赖型"非侵入插件。
#
# 【核心层（Core Level）】
#   - 继承本文件中的 IbPlugin 基类
#   - 通过 PluginCapabilities 深度访问内核能力：
#       stack_inspector  调用栈/意图栈内省
#       state_reader     运行时变量和 LLM 结果读取
#       llm_executor     LLM 执行器
#       service_context  ServiceContext（含 host_service、scheduler 等）
#   - 可通过 capabilities.expose("xxx_provider", self) 向 CapabilityRegistry
#     注册自身，供其他插件或内核代码发现
#   - 适合：运行时调试、系统状态查询、宿主能力（持久化/隔离执行）等
#   - 代表模块：ibci_ihost, ibci_idbg, ibci_isys
#
# 两种层次使用相同的 _spec.py 协议（__ibcext_metadata__ + __ibcext_vtable__）
# 和相同的 ModuleLoader 加载流程。核心层仅在实现类上额外继承 IbPlugin。
#
# ---------------------------------------------------------------------------
# 有状态/无状态声明协议（ihost 断点协议）
# ---------------------------------------------------------------------------
#
# IBCI 断点/动态宿主机制要求每个插件声明自身的状态可恢复性：
#
# 【IbStatelessPlugin】
#   - Mixin 标记：插件运行时无需持久化任何内部状态
#   - HostService 在 save/restore 时跳过此类插件，只重新调用 setup()
#   - 适合：ibci_math, ibci_json, ibci_time, ibci_schema, ibci_isys, ibci_file 等
#
# 【IbStatefulPlugin】
#   - 继承此 ABC：插件持有跨断点的内部状态（如网络配置、AI 配置等）
#   - 必须实现 save_plugin_state() → dict  和  restore_plugin_state(state: dict)
#   - HostService 在 snapshot 时调用 save_plugin_state()，恢复时调用 restore_plugin_state()
#   - 适合：ibci_ai（LLM 配置/意图状态），ibci_net（认证 token/会话配置）等
#   - 约束：save_plugin_state() 必须返回 JSON 可序列化的纯 dict，不能包含不可序列化对象
#
# 无论哪种，HostService 在恢复后都会重新调用 setup(capabilities) 重新绑定内核能力。
# ---------------------------------------------------------------------------


class IbPlugin(ABC):
    """
    核心层插件基类。

    提供：
    - setup(capabilities) 生命周期钩子，由 ModuleLoader 在加载时调用
    - expose()/revoke() 向 CapabilityRegistry 注册/撤销能力
    - plugin_id 唯一标识符

    非侵入层插件不需要继承此类，直接实现 setup(capabilities) 方法即可。
    """
    EXPOSE_LAZY = "lazy"
    EXPOSE_EAGER = "eager"

    def __init__(self, plugin_id: Optional[str] = None):
        self._plugin_id = plugin_id
        self._capabilities: Optional[PluginCapabilities] = None
        self._exposed_capabilities: Dict[str, Any] = {}

    @property
    def plugin_id(self) -> str:
        if self._plugin_id:
            return self._plugin_id
        return f"{self.__class__.__module__}:{self.__class__.__name__}"

    def setup(self, capabilities: PluginCapabilities) -> None:
        """
        插件初始化入口。
        子类若需重写，请务必调用 super().setup(capabilities) 或确保持有 capabilities 引用。
        """
        self._capabilities = capabilities

    def get_vtable(self) -> Dict[str, Callable]:
        """
         虚表生成。

        从模块级 __ibcext_vtable__ 函数获取方法映射表。
        """
        if hasattr(self, '_ibcext_vtable_func') and callable(self._ibcext_vtable_func):
            return self._ibcext_vtable_func()
        return {}

    def expose(
        self,
        capability_name: str,
        provider: Any,
        priority: int = 50,
        mode: str = EXPOSE_EAGER
    ) -> None:
        """
         暴露能力到注册表。
        允许插件向 CapabilityRegistry 注册自己的能力供其他插件使用。
        """
        if mode == self.EXPOSE_LAZY:
            self._exposed_capabilities[capability_name] = {
                "type": "lazy",
                "provider": provider,
                "priority": priority
            }
            return

        actual_provider = provider
        if callable(provider) and not isinstance(provider, type):
            import types
            actual_provider = types.MethodType(provider, self)

        self._do_expose(capability_name, actual_provider, priority)

    def _do_expose(self, capability_name: str, provider: Any, priority: int) -> None:
        """执行实际的暴露操作"""
        if self._capabilities and hasattr(self._capabilities, '_capability_registry') and self._capabilities._capability_registry:
            registry = self._capabilities._capability_registry
            registry.register(
                capability_name,
                provider,
                plugin_id=self.plugin_id,
                priority=priority
            )
        self._exposed_capabilities[capability_name] = provider

    def revoke(self, capability_name: str) -> None:
        """撤回一个能力"""
        if self._capabilities and hasattr(self._capabilities, '_capability_registry') and self._capabilities._capability_registry:
            registry = self._capabilities._capability_registry
            registry.unregister(capability_name, plugin_id=self.plugin_id)
        self._exposed_capabilities.pop(capability_name, None)

    def revoke_all(self) -> None:
        """撤回所有能力"""
        if self._capabilities and hasattr(self._capabilities, '_capability_registry') and self._capabilities._capability_registry:
            registry = self._capabilities._capability_registry
            registry.unregister_all(plugin_id=self.plugin_id)
        self._exposed_capabilities.clear()

    def get_exposed_capabilities(self) -> Dict[str, Any]:
        """获取已暴露的能力列表"""
        return dict(self._exposed_capabilities)


class IbStatelessPlugin:
    """
    无状态插件标记 Mixin。

    插件继承此类即声明："本插件运行时不持有任何跨断点的内部状态"。
    HostService 在 snapshot/restore 时对此类插件仅重新调用 setup()，
    无需保存/恢复任何额外数据。

    适合：ibci_math, ibci_json, ibci_time, ibci_schema, ibci_isys, ibci_file 等
    纯工具性、每次 setup 就能完整恢复的插件。

    使用示例：
        class MathLib(IbStatelessPlugin):
            def setup(self, capabilities): ...
    """
    pass


class IbStatefulPlugin(ABC):
    """
    有状态插件协议 ABC。

    插件继承此类即声明："本插件持有跨断点的内部状态，必须参与 HostService
    的断点保存/恢复流程"。

    必须实现：
    - save_plugin_state() → dict     以 JSON 可序列化的纯 dict 导出当前状态
    - restore_plugin_state(state)    从 dict 完整恢复状态

    约束：
    - save_plugin_state() 返回值必须为 JSON 可序列化的纯 dict（str/int/float/bool/list/dict/None）
    - restore_plugin_state() 在 setup() 之后被调用，可以安全访问 capabilities
    - 不应在此方法中执行网络 IO，仅恢复内存状态

    适合：ibci_ai（LLM 配置/意图状态），ibci_net（认证配置）等
    持有跨请求配置或会话状态的插件。

    使用示例：
        class AIPlugin(IbStatefulPlugin):
            def save_plugin_state(self) -> dict:
                return {"config": self._config, "intents": self._global_intents}

            def restore_plugin_state(self, state: dict) -> None:
                self._config.update(state.get("config", {}))
                self._global_intents = state.get("intents", [])
    """

    @abstractmethod
    def save_plugin_state(self) -> dict:
        """
        导出当前插件状态为 JSON 可序列化的纯 dict。

        此方法由 HostService 在 save_state()/snapshot() 时调用。
        返回值将被嵌入运行时快照文件，随断点一起持久化。
        """

    @abstractmethod
    def restore_plugin_state(self, state: dict) -> None:
        """
        从快照 dict 恢复插件状态。

        此方法由 HostService 在 load_state() 后、重新绑定环境时调用。
        调用时 setup(capabilities) 已执行完毕，capabilities 可用。
        """
