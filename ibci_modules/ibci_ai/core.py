"""``core`` —— ai 模块宿主（IBCI 胶水层）。

:class:`AIPlugin` 是 ibci ``ai`` 模块的插件宿主：继承推荐 provider
（:class:`ibci_modules.ibci_ai.provider_impl.RecommendedProvider`）获得全部纯 provider
逻辑（``call`` / ``stream`` / ``probe`` / 配置应用 / MOCK / 命名模型 / 断点状态），
本文件只保留 **IBCI 模块胶水**：

- 生命周期与注册：``setup``（经 ``CapabilityRegistry.CAP_LLM_PROVIDER`` 暴露 self）；
- 配置加载入口：``load_config`` / ``load_project_config``（执行上下文 / 文件系统 /
  默认配置适配器，均为内核侧能力）；
- 运行面：``run_batch`` / ``stream_call`` / ``stream_channel``（委托内核执行器与
  流对象）；
- 意图管理：``set_global_intent`` 等（经 capabilities 的 ``intent_manager``）；
- 内省：``get_current_call_info``（优先内核 LLM 执行器主线程单写槽）。

**自定义 LLM 底层**：经宿主绑定声明自定义 provider 并 ``ai.set_provider``
注册为激活的 llm_provider（HIGH 优先级覆盖内置默认 :class:`RecommendedProvider`）；
``provider_impl.py`` 仅作**内置默认实现**保留（未 set_provider 时生效），不再是用户
自定义入口。本宿主文件不改（改它会破坏 ``ai`` 模块的 IBCI 集成）。
"""

import os
from typing import Any, Dict, List, Optional

from core.extension.ibcext import ExtensionCapabilities, IbStatefulPlugin
from core.kernel.issue import InterpreterError
from core.kernel.path import PathValidator
from core.runtime.capability_registry import CapabilityRegistry
from core.runtime.objects.kernel.base import unbox

from ibci_modules.ibci_ai.config_loader import ApiConfig
from ibci_modules.ibci_ai.config_source_adapter import ProjectApiConfigAdapter
from ibci_modules.ibci_ai.embedding_impl import EmbeddingService
from ibci_modules.ibci_ai.provider_impl import RecommendedProvider


class AIPlugin(RecommendedProvider, IbStatefulPlugin):
    """
    AI LLM 供应者插件宿主（ibci ``ai`` 模块）。

    - **协议身份**：本插件经 :class:`LLMProvider` 契约向内核提供 LLM 抽象动作；
      协议方法（``call`` / ``stream`` / ``probe`` / ``get_retry`` /
      ``is_auto_intent_injection_enabled`` / ``get_current_call_info``）继承自
      推荐 provider（:class:`RecommendedProvider`）。
    - **用户 API**：``set_config`` / ``probe_model`` / ``load_project_config`` /
      ``register_model`` / 意图方法 / ``run_batch`` 等经 spec 元数据供 IBCI 脚本调用
      （继承自推荐 provider 或本文件胶水）。
    - **可插拔**：用户自定义 LLM 底层 = 经宿主绑定提供自定义 provider 并
      ``ai.set_provider`` 注册（`provider_impl.py` 仅为内置默认实现）。
    """

    def __init__(self):
        super().__init__()
        self._capabilities: Optional[ExtensionCapabilities] = None
        # embedding 服务面（组合——批 ① 契约包推荐实现 + 配置/mock/检索胶水；
        # 与 LLM 面同模块单入口（ai = 模型 I/O 面），配置单源 = api_config）
        self._embedding: Optional[EmbeddingService] = None

    def _require_embedding(self) -> EmbeddingService:
        """解析 embedding 服务面（setup 后惰性构造；fail-fast）。"""
        if self._embedding is None:
            if self._capabilities is None or self._capabilities.kernel_registry is None:
                raise InterpreterError(
                    "embedding 服务面不可用（ai 模块未 setup）",
                    None,
                )
            self._embedding = EmbeddingService(self._capabilities.kernel_registry)
        return self._embedding

    # ------------------------------------------------------------------ #
    # IbStatefulPlugin 断点状态（状态本体在推荐 provider 侧，此处显式确认契约）
    # ------------------------------------------------------------------ #

    def save_plugin_state(self) -> dict:
        """导出插件状态（推荐 provider 的 config / 返回类型提示，JSON 可序列化）。"""
        return super().save_plugin_state()

    def restore_plugin_state(self, state: dict) -> None:
        """从快照恢复插件状态（委托推荐 provider 的状态恢复）。"""
        super().restore_plugin_state(state)

    # ------------------------------------------------------------------ #
    # 生命周期 / 能力注册
    # ------------------------------------------------------------------ #

    def setup(self, capabilities: ExtensionCapabilities):
        self._capabilities = capabilities
        # 向能力注册表注册自己为 LLM Provider（.call/.stream 契约）。
        # 默认 NORMAL 优先级；`set_provider` 可经宿主绑定的自定义 provider
        # 以更高优先级覆盖之（见 set_provider）。
        capabilities.expose(CapabilityRegistry.CAP_LLM_PROVIDER, self)

    # ------------------------------------------------------------------ #
    # 自定义 provider 注册（宿主绑定统一 provider 自定义）
    # ------------------------------------------------------------------ #

    def set_provider(self, provider: Any) -> None:
        """注册自定义 LLM provider（宿主绑定对象 → 激活 provider）。

        统一 provider 自定义：用户在项目里写一个 Python 类实现
        :class:`LLMProvider` 契约（``call`` / ``stream`` / ``get_retry`` /
        ``is_auto_intent_injection_enabled`` / ``get_current_call_info``），
        导出为模块级实例（如 ``provider = MyProvider()``），经宿主绑定声明后
        ``ai.set_provider(lib.provider)`` 把它注册为**激活的** llm_provider
        （以 HIGH 优先级覆盖默认 :class:`RecommendedProvider`）。

        ``provider`` 是宿主绑定的原生对象（IBCI 侧 `bound` 值，经调用边界拆箱
        为原生 Python 实例）。契约校验缺失即 fail-fast（不静默降级）；未调用本
        方法时默认 provider（内置 ``RecommendProvider``）生效。
        """
        # 调用边界拆箱：bound 原生对象 → 原生 Python 实例（幂等：原生值原样透传）
        provider = unbox(provider)
        required = (
            "call",
            "stream",
            "get_retry",
            "is_auto_intent_injection_enabled",
            "get_current_call_info",
        )
        missing = [m for m in required if not callable(getattr(provider, m, None))]
        if missing:
            raise InterpreterError(
                f"ai.set_provider: 自定义 provider 缺少 LLMProvider 契约方法: {missing}",
                None,
            )
        if self._capabilities is None:
            raise InterpreterError(
                "ai.set_provider: 能力上下文不可用（ai 模块未 setup）",
                None,
            )
        # HIGH 优先级覆盖默认 provider（capability_registry 主选 = 最高优先级，
        # 惰性 get 使下次 LLM 调用起生效；单一 primary，非双通道）。
        from core.runtime.capability_registry import CapabilityPriority
        self._capabilities.expose(
            CapabilityRegistry.CAP_LLM_PROVIDER, provider,
            priority=int(CapabilityPriority.HIGH),
        )

    # ------------------------------------------------------------------ #
    # 内省（优先内核 LLM 执行器主线程单写槽，回退 provider 本地槽）
    # ------------------------------------------------------------------ #

    def get_current_call_info(self) -> Dict[str, Any]:
        """最近一次调用/解析的诊断信息（优先内核 LLM 执行器主线程单写槽）。"""
        kr = self._capabilities.kernel_registry if self._capabilities else None
        if kr is not None:
            executor = kr.get_llm_executor()
            if executor is not None:
                return dict(executor.get_current_call_info())
        return super().get_current_call_info()

    # ------------------------------------------------------------------ #
    # 配置加载入口（执行上下文 / 文件系统，IBCI 侧能力）
    # ------------------------------------------------------------------ #

    def load_config(self, path: str) -> None:
        """从指定 ``api_config.json`` 加载配置并应用（指定路径入口）。"""
        if self._capabilities is None or self._capabilities.execution_context is None:
            raise InterpreterError("ai.load_config: 执行上下文不可用，无法解析配置路径")
        ec = self._capabilities.execution_context
        project_root = ec.get_project_root()
        if not project_root:
            raise InterpreterError("ai.load_config: execution_context 未确立 project_root")
        raw = path if os.path.isabs(path) else os.path.join(project_root, path)
        abs_path = PathValidator.canonicalize_for_security(raw).to_native()
        config = ApiConfig.load(abs_path)
        self.apply_config(config)

    def load_project_config(self) -> None:
        """显式加载 ``api_config.json`` 并应用（一等入口）。

        经可插拔的 :class:`ConfigSourceAdapter`（本插件使用
        :class:`ProjectApiConfigAdapter` 识别默认文件 schema：自 project_root
        向上发现最近配置，仓库根单源即可服务全部子目录；具体读取/校验/env
        展开委托 :class:`ApiConfig`，并把 ``defaults.mock`` 等 provider 测试模式
        一并应用）。用户可自写适配器改写 api_config.json 书写格式。
        """
        if self._capabilities is None or self._capabilities.execution_context is None:
            raise InterpreterError("ai.load_project_config: 执行上下文不可用，无法定位 api_config.json")
        ec = self._capabilities.execution_context
        project_root = ec.get_project_root()
        if not project_root:
            raise InterpreterError("ai.load_project_config: execution_context 未确立 project_root")
        adapter = ProjectApiConfigAdapter()
        if not adapter.can_load(project_root):
            return
        config = adapter.load(project_root)  # LLMConnectionConfig
        raw_dict = adapter.load_raw_dict(project_root)  # 含 defaults.mock
        self.apply_config(config, mock=raw_dict.get("defaults", {}).get("mock", False))

    # ------------------------------------------------------------------ #
    # run_batch（委托内核 LLM 执行器）
    # ------------------------------------------------------------------ #

    def run_batch(self, behavior: Any, items: List[Any]) -> List[Any]:
        """并发批量执行行为 / LLMCallable 实例（`ai.run_batch`）。"""
        executor = self._require_llm_executor("run_batch")
        from core.runtime.frame import get_current_execution_context
        ec = get_current_execution_context()
        if ec is None:
            raise RuntimeError("run_batch: no execution context available")
        return executor.run_batch(behavior, list(items), ec)

    def stream_call(self, target: Any) -> Any:
        """流式 LLM 调用：接受任何 LLMCallable 实例（行为值或用户 llm 可调用类）。

        经统一装配入口（帧内 CPS，含 ``__intent__`` 可选改写）装配请求后流式执行，
        返回帧内 CPS 驱动的 Waitable——VM 主路径装配 → ``IbStreamHandle``；
        ``await`` / 赋值自动等待返回完整文本（与既有流式范式一致）。
        """
        executor = self._require_llm_executor("stream_call")
        from core.runtime.frame import get_current_execution_context
        ec = get_current_execution_context()
        if ec is None:
            raise RuntimeError("stream_call: no execution context available")
        return executor.make_stream_callable_drive(
            target, ec, provider_stream=self.stream, channel_mode=False
        )

    def stream_channel(self, target: Any) -> Any:
        """流式 LLM 调用：返回承载增量块的 stream Channel（LLMCallable 消费面）。"""
        executor = self._require_llm_executor("stream_channel")
        from core.runtime.frame import get_current_execution_context
        ec = get_current_execution_context()
        if ec is None:
            raise RuntimeError("stream_channel: no execution context available")
        return executor.make_stream_callable_drive(
            target, ec, provider_stream=self.stream, channel_mode=True
        )

    def _require_llm_executor(self, api: str):
        """解析内核 LLM 执行器（fail-fast；run_batch/stream 共用）。"""
        kr = self._capabilities.kernel_registry if self._capabilities else None
        if kr is None:
            raise RuntimeError(f"{api}: LLM executor not available")
        executor = kr.get_llm_executor()
        if executor is None:
            raise RuntimeError(f"{api}: LLM executor does not support {api}")
        return executor

    # ------------------------------------------------------------------ #
    # 意图管理（经 capabilities 的 intent_manager）
    # ------------------------------------------------------------------ #

    def set_global_intent(self, intent: str) -> None:
        if self._capabilities and self._capabilities.intent_manager:
            self._capabilities.intent_manager.set_global_intent(intent)

    def clear_global_intents(self) -> None:
        if self._capabilities and self._capabilities.intent_manager:
            self._capabilities.intent_manager.clear_global_intents()

    def remove_global_intent(self, intent: str) -> None:
        if self._capabilities and self._capabilities.intent_manager:
            self._capabilities.intent_manager.remove_global_intent(intent)

    def mask(self, tag_pattern: str) -> None:
        if self._capabilities and self._capabilities.intent_manager:
            self._capabilities.intent_manager.push_intent("", mode="-", tag=tag_pattern)

    def get_global_intents(self) -> List[str]:
        if self._capabilities and self._capabilities.intent_manager:
            return self._capabilities.intent_manager.get_global_intents()
        return []

    def get_current_intent_stack(self) -> List[str]:
        if self._capabilities and self._capabilities.intent_manager:
            global_ints = self._capabilities.intent_manager.get_global_intents()
            active_infos = self._capabilities.intent_manager.get_active_intents()
            active_ints = [i.content for i in active_infos]
            res = []
            seen = set()
            for i in global_ints + active_ints:
                if i not in seen:
                    res.append(i)
                    seen.add(i)
            return res
        return []

    # ------------------------------------------------------------------ #
    # embedding 服务面（用户 API；委托 EmbeddingService——批 ① 契约包）
    # ------------------------------------------------------------------ #

    def apply_config(self, config, mock: bool = False) -> None:
        """应用逻辑配置（LLM 面 + embedding 面——embedding_models 条目落地）。

        embedding 面仅在有 embedding 条目且模块已 setup（能力上下文可用）
        时应用——直构场景（未 setup）与无 embedding 条目零副作用。
        """
        super().apply_config(config, mock=mock)
        if (
            self._capabilities is not None
            and hasattr(config, "embedding_models")
            and config.embedding_models
        ):
            self._require_embedding().apply_config(config)

    def embed(self, texts: Any, model: Any = None, dimensions: Any = None) -> Any:
        """embedding 调用：str → vector（单文本）/ list[str] → list[vector]。"""
        svc = self._require_embedding()
        return svc.embed(
            texts,
            model=model.to_native() if hasattr(model, "to_native") else model,
            dimensions=dimensions.to_native() if hasattr(dimensions, "to_native") else dimensions,
        )

    def set_embedding_config(self, url: str, key: str, model: str, timeout: float = 30.0) -> None:
        """显式配置 embedding 连接（对称 LLM set_config）。"""
        self._require_embedding().set_config(url, key, model, timeout=timeout)

    def register_embedding_model(
        self, name: str, url: str, key: str, model: str, timeout: float = 30.0
    ) -> None:
        """注册命名 embedding 模型（与 LLM register_model 同型）。"""
        self._require_embedding().register_model(name, url, key, model, timeout=timeout)

    def set_embedding_model(self, name: str) -> None:
        """选择当前激活的命名 embedding 模型。"""
        self._require_embedding().set_model(name)

    def set_embedding_mock(self, enable: bool = True, dim: int = 128, seed: int = 0) -> None:
        """显式进入/退出 embedding MOCK 模式（MOCK:VEC 确定性向量）。"""
        self._require_embedding().set_mock_mode(enable, dim=dim, seed=seed)

    def retrieve(self, query: Any, corpus: Any, k: Any) -> List[Any]:
        """线性 top-k 检索：vector × list[vector] → list[dict]（index/score）。"""
        k_native = k.to_native() if hasattr(k, "to_native") else k
        return self._require_embedding().retrieve(query, corpus, k_native)

    def get_embedding_call_info(self) -> Dict[str, Any]:
        """最近一次 embedding 调用的诊断信息（内省/观测面）。"""
        return self._require_embedding().get_call_info()

    def probe_embedding(self) -> str:
        """探测 embedding 服务/模型能力（含实际维度）。"""
        return self._require_embedding().probe()


def create_implementation():
    return AIPlugin()