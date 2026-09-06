from typing import Any, Dict, Optional, List, TYPE_CHECKING, Callable
import os
import json

# =============================================================================
# 架构边界说明：HostService（DynamicHost）= 编排者，不亲自执行 IBCI 代码
# =============================================================================
# HostService 是 IBCI 宿主子系统的编排者（orchestrator）。
# 职责：管理运行现场的持久化（Artifact 序列化/反序列化）、
# 子解释器实例的隔离执行调度，以及元编程能力的暴露接口。
#
# HostService 本身不执行任何 IBCI 代码；执行始终发生在 Interpreter 内部。
# HostService 通过 IInterpreterFactory 创建 Interpreter 实例，
# 然后将执行委托给这些实例，自身只负责协调和状态管理。
# =============================================================================
from core.runtime.serialization.runtime_serializer import RuntimeSerializer, RuntimeDeserializer
from core.runtime.serialization.immutable_artifact import ImmutableArtifact
from core.runtime.interfaces import ServiceContext, IHostService, IInterpreterFactory, InterOp, IExecutionContext, IKernelOrchestrator
from core.kernel.host_interface import HostInterface
from core.kernel.registry import KernelRegistry
from core.runtime.objects.kernel import IbObject
from core.kernel.issue import InterpreterError
from core.runtime.host.awaitable import HostAwaitable
from core.extension.ibcext import IbStatefulPlugin

# 序列化格式约定：save_state 外化资产时用此哨兵占位，load_state 据此回填。
_EXTERNAL_FILE_REF_SENTINEL = "__EXTERNAL_FILE_REF__"

class HostService(IHostService):
    """
    IBCI 2.0 内核级宿主服务子系统。
    负责运行现场的持久化、隔离执行以及元编程能力。
    """
    def __init__(self,
                 registry: KernelRegistry,
                 execution_context: IExecutionContext,
                 interop: InterOp,
                 setup_context_callback: Callable,
                 get_current_module_callback: Callable):
        self.registry = registry
        self.execution_context = execution_context
        self.interop = interop
        self._orchestrator = None
        self.setup_context_callback = setup_context_callback
        self.get_current_module_callback = get_current_module_callback

    @property
    def orchestrator(self) -> Optional[IKernelOrchestrator]:
        """内核协调器（由 ServiceContext.set_orchestrator 统一注入）。"""
        return self._orchestrator

    @orchestrator.setter
    def orchestrator(self, value: Optional[IKernelOrchestrator]) -> None:
        self._orchestrator = value

    @staticmethod
    def _contains_disk_backed_instance(execution_context: IExecutionContext) -> bool:
        """扫描当前及外层作用域，检查是否存在 disk-backed 实例（file/media）。

        仅检查**实例**（值为 IbClass 的类型对象不算——类是类型定义，非
        disk-backed 数据）；class file_handle/audio/image/video 的类对象
        常驻 prelude，若误判会导致 save_state 永久拒绝。
        """
        from core.runtime.objects.kernel.ib_class import IbClass

        runtime_context = execution_context.runtime_context
        if runtime_context is None:
            return False
        scope = runtime_context.get_current_scope()
        while scope is not None:
            for sym in scope.get_all_symbols().values():
                val = sym.value
                if val is None:
                    continue
                if isinstance(val, IbClass):
                    # 类型对象（类）不是实例，跳过。
                    continue
                ib_class = getattr(val, "ib_class", None)
                spec = getattr(ib_class, "spec", None)
                if spec is not None and getattr(spec, "is_disk_backed", False):
                    return True
            scope = getattr(scope, "parent", None)
        return False

    def save_state(self, path: str):
        """深度序列化当前运行时上下文并保存到磁盘"""
        # 路径经 IbPath 规范化；资产外化布局委托 SnapshotLayout（策略集中化）。
        # 注：save_state 是宿主级特权操作（用户显式调用），不经 PermissionManager 沙箱校验--
        # 这是有意设计（host op 应能写用户指定位置），非安全缺口。
        # 注：assets 的 "__EXTERNAL_FILE_REF__" 哨兵是序列化格式约定。
        from core.kernel.path import IbPath, SnapshotLayout

        # 在序列化之前扫描活跃变量，若存在磁盘型容器则直接拒绝。
        if self._contains_disk_backed_instance(self.execution_context):
            raise InterpreterError(
                "save_state is not supported when the execution context contains "
                "active file_handle/audio/image/video variables. "
                "Use file.write to persist artifacts explicitly."
            )

        # 线程对象/容器是瞬态；save_state 时检测到未完成线程直接失败。
        runtime_context = self.execution_context.runtime_context
        coordinator = runtime_context.peek_runtime_coordinator() if runtime_context is not None else None
        if coordinator is not None:
            unfinished = coordinator.unfinished_handles()
            if unfinished:
                raise InterpreterError(
                    "save_state is not supported while threads are running: "
                    f"unfinished thread(s) {unfinished}. "
                    "Join or cancel all threads before saving state."
                )

        data = self.snapshot()

        save_path = IbPath.from_native(path).resolve_dot_segments()
        abs_path = save_path.to_native()
        base_dir = (save_path.parent.to_native() if save_path.parent else "")
        os.makedirs(base_dir, exist_ok=True)

        # 文本资产外部化持久化（布局走 SnapshotLayout）
        assets = data["pools"].get("assets", {})
        if assets:
            asset_dir_path = SnapshotLayout.asset_dir_for(save_path)
            os.makedirs(asset_dir_path.to_native(), exist_ok=True)
            for uid, content in assets.items():
                asset_path = SnapshotLayout.asset_file(asset_dir_path, uid).to_native()
                with open(asset_path, "w", encoding="utf-8") as af:
                    af.write(content)
            data["pools"]["assets"] = {uid: _EXTERNAL_FILE_REF_SENTINEL for uid in assets}

        with open(abs_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_state(self, path: str):
        """从磁盘加载快照并恢复当前现场"""
        from core.kernel.path import IbPath, SnapshotLayout
        save_path = IbPath.from_native(path).resolve_dot_segments()
        abs_path = save_path.to_native()
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"State file not found: {abs_path}")

        with open(abs_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 恢复外部文本资产（布局走 SnapshotLayout，与 save_state 一致）
        asset_dir_path = SnapshotLayout.asset_dir_for(save_path)
        asset_dir = asset_dir_path.to_native()
        if os.path.exists(asset_dir):
            assets = data["pools"].get("assets", {})
            for uid in assets:
                asset_path = SnapshotLayout.asset_file(asset_dir_path, uid).to_native()
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
                # 显式持久化契约：插件状态保存失败必须暴露（fail-fast），
                # 不静默降级为哨兵——否则 save_state 用户无感知地丢数据。
                plugin_states[name] = pkg.save_plugin_state()
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
        # 直接使用注册表查询方法，消除 HostInterface 兼容性接口依赖。
        # 模块对象按 import 路径同构构造（vtable/白名单契约 + IbModule 包装）——
        # 缺契约的裸 NativeObject 会在成员访问时被模块契约门拒绝。
        live_modules: Dict[str, Any] = {}
        for name in self.interop.get_all_package_names():
            pkg = self.interop.get_package(name)
            if pkg:
                if not isinstance(pkg, IbObject):
                    # 使用工厂创建 Native 对象，消除对 kernel.IbNativeObject 的直接依赖
                    contract = self.interop.get_native_contract(name)
                    native_obj = self.execution_context.factory.create_native_object(
                        pkg,
                        self.registry.get_class("Object"),
                        vtable=contract[0] if contract else None,
                        whitelist=contract[1] if contract else None,
                        registry_id=self.interop.get_registry_id(name),
                    )
                    pkg_obj = self.execution_context.factory.create_module(name, native_obj)
                else:
                    pkg_obj = pkg
                live_modules[name] = pkg_obj
                # 强制覆盖常量符号
                context.global_scope.define(name, pkg_obj, is_const=True, force=True)

        # 2.5 恢复作用域树中的内核原生模块绑定（KERNEL_ISSUE-SER-1）：import 产生的
        # 模块变量位于模块作用域（非 global），其值经快照反序列化为 scope_native 空
        # scope 占位（见 runtime_serializer._collect_module 契约：实现由本方法重绑）。
        # 重绑必须覆盖全部已恢复作用域——仅修 global 时，模块作用域的死占位会遮蔽
        # 活绑定，load 后模块成员访问 AttributeError。
        # 就地变更符号值（不重建符号）：编译期符号 UID 与运行期 uid 键是同一符号的
        # 多别名，重建会触发别名清理丢失编译期键。
        if deserializer is not None and live_modules:
            for scope in deserializer.restored_scopes():
                for sym in scope.get_all_symbols_by_uid().values():
                    live_obj = live_modules.get(sym.name)
                    if live_obj is not None:
                        sym.value = live_obj
                        sym.current_type = type(live_obj)
                for sym in scope.get_all_symbols().values():
                    live_obj = live_modules.get(sym.name)
                    if live_obj is not None:
                        sym.value = live_obj
                        sym.current_type = type(live_obj)

        # 3. 恢复有状态插件的内部状态（fail-fast：恢复失败必须暴露，不静默跳过）
        if plugin_states:
            for name, saved in plugin_states.items():
                pkg = self.interop.get_package(name)
                if pkg and isinstance(pkg, IbStatefulPlugin):
                    pkg.restore_plugin_state(saved)

    def run_isolated(self, path: str, policy: Dict[str, Any]) -> "HostAwaitable":
        """
        隔离执行：在独立子引擎中运行 ``path``，返回 ``HostAwaitable``（可等待句柄）。

        语义与 ``spawn_isolated`` 统一——子引擎在后台线程中运行；本方法返回
        ``HostAwaitable``，VM 调度器对它 ``yield`` 挂起并等待完成，经 ``result()``
        取回子环境导出的变量字典（多返回值）。对脚本而言即"阻塞式"运行并等待。

        父与子之间不做隐式内存交互，变量不跨隔离边界继承；父->子 数据传递应
        通过显式 file 读写完成。
        """
        if not self.orchestrator:
            raise RuntimeError("Kernel Orchestrator not available. Isolated execution cannot be performed.")

        abs_path = self._resolve_isolated_path(path)
        handle = self.orchestrator.request_spawn_isolated(abs_path, policy, silent=False)
        return HostAwaitable(self.orchestrator, handle)

    def spawn_isolated(self, path: str, policy: Dict[str, Any]) -> str:
        """
        非阻塞隔离执行。通过内核协调器在后台线程中启动子引擎，立即返回 handle。
        调用方随后通过 collect(handle) 等待完成并取回结果变量。
        """
        if not self.orchestrator:
            raise RuntimeError("Kernel Orchestrator not available. Spawned execution cannot be performed.")

        abs_path = self._resolve_isolated_path(path)
        return self.orchestrator.request_spawn_isolated(abs_path, policy)

    def collect(self, handle: str) -> "HostAwaitable":
        """
        返回 ``HostAwaitable``（可等待句柄）：VM 调度器对它 ``yield`` 挂起，等待
        对应 ``spawn_isolated`` 子执行完成，经 ``result()`` 取回子环境导出的变量
        字典。handle 消费后失效；重复 collect 同一 handle 将抛出 RuntimeError。
        """
        if not self.orchestrator:
            raise RuntimeError("Kernel Orchestrator not available.")

        return HostAwaitable(self.orchestrator, handle)

    def _resolve_isolated_path(self, path: str) -> str:
        """
        把 ``ihost.run_isolated``/``spawn_isolated`` 传入的脚本路径解析为绝对路径。

        委托规范解析器 ``PathResolver``（entry_dir 单锚点契约），与
        ``ExecutionContextImpl.resolve_path`` / ``file.read`` 的相对入口目录语义一致。
        """
        from core.kernel.path import PathResolver, IbPath
        entry_dir = self.execution_context.get_entry_dir()
        resolver = PathResolver(entry_dir=IbPath.from_native(entry_dir) if entry_dir else None)
        return resolver.resolve(path).to_native()

    def get_source(self) -> str:
        """元编程：获取当前运行模块的源代码"""
        current_mod = self.get_current_module_callback()
        provider = getattr(self.execution_context.service_context, 'source_provider', None)
        if provider:
            return provider.get_module_source(current_mod) or ""
        return ""
