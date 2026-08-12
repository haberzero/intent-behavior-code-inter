from typing import Optional
from abc import ABC, abstractmethod

from core.extension.capabilities import PluginCapabilities, ExtensionCapabilities


# ---------------------------------------------------------------------------
# IBC-Inter 插件体系层次说明
# ---------------------------------------------------------------------------
#
# IBC-Inter 插件分为两个层次：
#
# 【内核原生层（Kernel-Native Level）】
#   - 随内核发行，构造期预注册，IMPORT_GATED
#   - 不继承 IbPlugin，不走 ModuleLoader 插件发现流程
#   - 通过 engine 直接注册为 Provenance.KERNEL_NATIVE + Visibility.IMPORT_GATED
#   - 适合：与内核深度耦合的能力模块（LLM、文件系统、动态宿主、调试、系统查询）
#   - 代表模块：ai, file, ihost, idbg, isys
#
# 【非侵入层（Non-Invasive Level）】
#   - 零内核依赖：_spec.py 只含纯 dict vtable，实现类不导入 core.*
#   - 通过 setup(capabilities) 接收注入的能力容器，只按需取用浅层能力
#     （如 capabilities.service_context.permission_manager）
#   - 适合：数学计算、JSON、HTTP 等无状态工具性插件
#   - 代表模块：ibci_math, ibci_json, ibci_time, ibci_net, ibci_schema
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
# 【无状态插件（默认）】
#   - 插件不继承任何特殊基类即为"无状态"
#   - HostService 在 save/restore 时跳过此类插件，只重新调用 setup()
#   - 适合：ibci_math, ibci_json, ibci_time, ibci_schema 等
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
    - plugin_id 唯一标识符

    非侵入层插件不需要继承此类，直接实现 setup(capabilities) 方法即可。
    能力注册统一经 ``PluginCapabilities.expose/revoke``（ModuleLoader 在
    setup 前注入当前插件身份 plugin_id），插件自身不需调用注册表。
    """
    def __init__(self, plugin_id: Optional[str] = None):
        self._plugin_id = plugin_id
        self._capabilities: Optional[PluginCapabilities] = None

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
