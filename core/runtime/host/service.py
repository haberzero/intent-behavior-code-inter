from typing import Any, Dict, Optional, List, TYPE_CHECKING, Callable
import os
import json
from core.runtime.serialization.runtime_serializer import RuntimeSerializer, RuntimeDeserializer
from core.runtime.serialization.immutable_artifact import ImmutableArtifact
from core.runtime.interfaces import ServiceContext, IHostService, IInterpreterFactory, InterOp, IExecutionContext, IKernelOrchestrator
from core.runtime.host.host_interface import HostInterface
from core.kernel.registry import KernelRegistry
from core.runtime.host.sync_manager import SyncManager
from core.runtime.objects.kernel import IbObject
from core.extension.ibcext import IbStatefulPlugin

class HostService(IHostService):
    """
    IBCI 2.0 内核级宿主服务子系统。
    负责运行现场的持久化、隔离执行以及元编程能力。
    """
    def __init__(self,
                 registry: KernelRegistry,
                 execution_context: IExecutionContext,
                 interop: InterOp,
                 orchestrator: Optional[IKernelOrchestrator],
                 setup_context_callback: Callable,
                 get_current_module_callback: Callable):
        self.registry = registry
        self.execution_context = execution_context
        self.interop = interop
        self.orchestrator = orchestrator
        self.setup_context_callback = setup_context_callback
        self.get_current_module_callback = get_current_module_callback
        self._sync_manager = SyncManager()

    def sync(self) -> bool:
        """
         安全点同步 (Safe Point Sync) 原语。
        等待所有执行上下文达到一致状态后返回。
        """
        return self._sync_manager.sync()

    def save_state(self, path: str):
        """深度序列化当前运行时上下文并保存到磁盘"""
        self.sync() # 必须先同步
        data = self.snapshot()
        
        abs_path = os.path.abspath(path)
        base_dir = os.path.dirname(abs_path)
        os.makedirs(base_dir, exist_ok=True)
        
        # 文本资产外部化持久化
        assets = data["pools"].get("assets", {})
        if assets:
            asset_dir = abs_path + ".assets"
            os.makedirs(asset_dir, exist_ok=True)
            for uid, content in assets.items():
                asset_path = os.path.join(asset_dir, f"{uid}.txt")
                with open(asset_path, "w", encoding="utf-8") as af:
                    af.write(content)
            data["pools"]["assets"] = {uid: f"__EXTERNAL_FILE_REF__" for uid in assets}

        with open(abs_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_state(self, path: str):
        """从磁盘加载快照并恢复当前现场"""
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"State file not found: {abs_path}")
            
        with open(abs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # 恢复外部文本资产
        asset_dir = abs_path + ".assets"
        if os.path.exists(asset_dir):
            assets = data["pools"].get("assets", {})
            for uid in assets:
                asset_path = os.path.join(asset_dir, f"{uid}.txt")
                if os.path.exists(asset_path):
                    with open(asset_path, "r", encoding="utf-8") as af:
                        assets[uid] = af.read()
                        
        deserializer = RuntimeDeserializer(self.registry, factory=self.execution_context.factory)
        new_ctx = deserializer.deserialize_context(data)
        
        # 重新绑定环境能力 (Intrinsics & Plugins)
        plugin_states = data.get("plugin_states", {}) if isinstance(data, dict) else {}
        self._rebind_environment(new_ctx, deserializer, plugin_states=plugin_states)
        
        # 强制同步到当前解释器实例 (通过容器更新)
        self.execution_context.runtime_context = new_ctx

    def snapshot(self) -> Dict[str, Any]:
        """内存快照原语。同时捕获有状态插件的状态。"""
        serializer = RuntimeSerializer(self.registry)
        snapshot = serializer.serialize_context(
            self.execution_context.runtime_context,
            execution_context=self.execution_context
        )
        # 收集所有有状态插件的快照
        plugin_states: Dict[str, Any] = {}
        for name in self.interop.get_all_package_names():
            pkg = self.interop.get_package(name)
            if pkg and isinstance(pkg, IbStatefulPlugin):
                try:
                    plugin_states[name] = pkg.save_plugin_state()
                except Exception as e:
                    # 插件状态保存失败不中断快照，但需要记录
                    plugin_states[name] = {"__save_error__": str(e)}
        if plugin_states:
            snapshot["plugin_states"] = plugin_states
        return snapshot

    def _rebind_environment(self, context: Any, deserializer: Optional[Any] = None, plugin_states: Optional[Dict[str, Any]] = None):
        """
        环境重绑定：将快照中的“空壳”重新链接到当前物理环境的功能实现。
        对 IbStatefulPlugin 插件，额外调用 restore_plugin_state() 恢复其内部状态。
        """
        # 1. 重新注入内置函数 (Intrinsics) - 使用特权覆盖 (通过回调)
        self.setup_context_callback(context, force=True)
        
        # 2. 重新注入原生插件 (Native Plugins)
        # 直接使用注册表查询方法，消除 HostInterface 兼容性接口依赖
        for name in self.interop.get_all_package_names():
            pkg = self.interop.get_package(name)
            if pkg:
                if not isinstance(pkg, IbObject):
                    # 使用工厂创建 Native 对象，消除对 kernel.IbNativeObject 的直接依赖
                    pkg_obj = self.execution_context.factory.create_native_object(
                        pkg,
                        self.registry.get_class("Object")
                    )
                else:
                    pkg_obj = pkg
                # 强制覆盖常量符号
                context.global_scope.define(name, pkg_obj, is_const=True, force=True)

        # 3. 恢复有状态插件的内部状态
        if plugin_states:
            for name, saved in plugin_states.items():
                pkg = self.interop.get_package(name)
                if pkg and isinstance(pkg, IbStatefulPlugin) and "__save_error__" not in saved:
                    try:
                        pkg.restore_plugin_state(saved)
                    except Exception:
                        pass  # 恢复失败不中断整体流程

    def run_isolated(self, path: str, policy: Dict[str, Any]) -> IbObject:
        """
         通过内核协调器开启完全隔离的解释器环境。
        不再负责手动孵化实例或编译代码，而是将请求作为系统调用上报。
        """
        if not self.orchestrator:
            raise RuntimeError("Kernel Orchestrator not available. Isolated execution cannot be performed.")
            
        # 根据 policy 提取 initial_vars (如果需要传递状态)
        initial_vars = None
        if policy.get("inherit_variables", False):
            # 提取父环境的全局变量 (排除内部变量)
            global_symbols = self.execution_context.runtime_context.global_scope.get_all_symbols()
            initial_vars = {}
            for name, sym in global_symbols.items():
                if not name.startswith("__") and not sym.metadata.get("is_builtin", False):
                    # 仅传递基础类型值或可安全序列化的值，此处简化为值引用传递，
                    # 实际在 Engine 接收端会被装箱
                    val = self.execution_context.runtime_context.global_scope.resolve(name)
                    if hasattr(val, 'get_value'):
                        initial_vars[name] = val.get_value()

        # 发起系统调用，阻塞等待执行完成
        abs_path = os.path.abspath(path)
        success = self.orchestrator.request_isolated_run(abs_path, policy, initial_vars)
        
        # TODO: 怀疑此处有vibe带来的妥协性问题。当前MVP Demo阶段不深究。
        # 返回执行结果 (暂简化为布尔值的 IbObject 封装)
        return self.registry.box(success)

    def get_source(self) -> str:
        """元编程：获取当前运行模块的源代码"""
        current_mod = self.get_current_module_callback()
        provider = getattr(self.execution_context.service_context, 'source_provider', None)
        if provider:
            return provider.get_module_source(current_mod) or ""
        return ""
