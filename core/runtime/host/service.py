from typing import Any, Dict, Optional, List, TYPE_CHECKING, Callable
import os
import json
from core.runtime.serialization.runtime_serializer import RuntimeSerializer, RuntimeDeserializer
from core.runtime.serialization.immutable_artifact import ImmutableArtifact
from core.runtime.interfaces import ServiceContext, IHostService, IInterpreterFactory, InterOp, IIbObject, IExecutionContext
from core.runtime.host.host_interface import HostInterface
from core.kernel.registry import KernelRegistry
from core.runtime.host.sync_manager import SyncManager
from core.compiler.serialization.serializer import FlatSerializer

class HostService(IHostService):
    """
    IBCI 2.0 内核级宿主服务子系统。
    负责运行现场的持久化、隔离执行以及元编程能力。
    """
    def __init__(self,
                 registry: KernelRegistry,
                 execution_context: IExecutionContext,
                 interop: InterOp,
                 compiler: Any,
                 factory: IInterpreterFactory,
                 setup_context_callback: Callable,
                 get_current_module_callback: Callable):
        self.registry = registry
        self.execution_context = execution_context
        self.interop = interop
        self.compiler = compiler
        self.factory = factory
        self.setup_context_callback = setup_context_callback
        self.get_current_module_callback = get_current_module_callback
        self._sync_manager = SyncManager()

    def sync(self) -> bool:
        """
        [IES 2.1] 安全点同步 (Safe Point Sync) 原语。
        等待所有执行上下文达到一致状态后返回。
        """
        return self._sync_manager.sync()

    def save_state(self, path: str):
        """深度序列化当前运行时上下文并保存到磁盘"""
        self.sync() # 必须先同步
        serializer = RuntimeSerializer(self.registry)
        data = serializer.serialize_context(
            self.execution_context.runtime_context, 
            execution_context=self.execution_context
        )
        
        abs_path = os.path.abspath(path)
        base_dir = os.path.dirname(abs_path)
        os.makedirs(base_dir, exist_ok=True)
        
        # [IES 2.2 Security Update] 文本资产外部化持久化
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
            
        # [IES 2.2 Security Update] 恢复外部文本资产
        asset_dir = abs_path + ".assets"
        if os.path.exists(asset_dir):
            assets = data["pools"].get("assets", {})
            for uid in assets:
                asset_path = os.path.join(asset_dir, f"{uid}.txt")
                if os.path.exists(asset_path):
                    with open(asset_path, "r", encoding="utf-8") as af:
                        assets[uid] = af.read()
                        
        deserializer = RuntimeDeserializer(self.registry)
        new_ctx = deserializer.deserialize_context(data)
        
        # 重新绑定环境能力 (Intrinsics & Plugins)
        self._rebind_environment(new_ctx, deserializer)
        
        # 强制同步到当前解释器实例 (通过容器更新)
        self.execution_context.runtime_context = new_ctx

    def snapshot(self) -> Dict[str, Any]:
        """内存快照原语"""
        serializer = RuntimeSerializer(self.registry)
        snapshot = serializer.serialize_context(
            self.execution_context.runtime_context, 
            execution_context=self.execution_context
        )
        return snapshot

    def _rebind_environment(self, context: Any, deserializer: Optional[Any] = None):
        """
        环境重绑定：将快照中的“空壳”重新链接到当前物理环境的功能实现。
        """
        # 1. 重新注入内置函数 (Intrinsics) - 使用特权覆盖 (通过回调)
        self.setup_context_callback(context, force=True, deserializer=deserializer)
        
        # 2. 重新注入原生插件 (Native Plugins)
        # [IES 2.1 Refactor] 直接使用注册表查询方法，消除 HostInterface 兼容性接口依赖
        for name in self.interop.host_interface.metadata.get_all_modules().keys():
            pkg = self.interop.get_package(name)
            if pkg:
                if not isinstance(pkg, IIbObject):
                    # [IES 2.1 Factory] 使用工厂创建 Native 对象，消除对 kernel.IbNativeObject 的直接依赖
                    pkg_obj = self.execution_context.factory.create_native_object(
                        pkg, 
                        self.registry.get_class("Object")
                    )
                else:
                    pkg_obj = pkg
                # [IES 2.0 Privileged] 强制覆盖常量符号
                context.global_scope.define(name, pkg_obj, is_const=True, force=True)

    def run_isolated(self, path: str, policy: Dict[str, Any]) -> bool:
        """通过协调器工厂开启隔离的解释器子运行环境"""
        serializer = RuntimeSerializer(self.registry)
        snapshot = serializer.serialize_context(
            self.execution_context.runtime_context,
            execution_context=self.execution_context
        )

        try:
            abs_path = os.path.abspath(path)
            artifact = self.compiler.compile_file(abs_path)

            # [P2-A] 将 CompilationArtifact 序列化为不可变 dict，消除对象引用穿透
            flat_serializer = FlatSerializer()
            artifact_dict = flat_serializer.serialize_artifact(artifact)

            # [P2-D] 包装为 ImmutableArtifact，防止解释器修改 artifact
            immutable_artifact = ImmutableArtifact(artifact_dict)

            sub_host_interface = HostInterface()
            inherit_plugins = policy.get("inherit_plugins", [])
            if inherit_plugins is True:
                inherit_plugins = list(self.interop.host_interface.metadata.get_all_modules().keys())

            for p_name in inherit_plugins:
                impl = self.interop.host_interface.get_module_implementation(p_name)
                meta = self.interop.host_interface.metadata.resolve(p_name)
                if impl:
                    sub_host_interface.register_module(p_name, impl, meta)

            isolated = policy.get("isolated", True)

            # [P2-A.1] 由HostService负责registry克隆，隔离策略的决定权在调用者
            effective_registry = self.registry.clone() if isolated else self.registry

            sub_interpreter = self.factory.spawn_interpreter(
                artifact=immutable_artifact,
                registry=effective_registry,
                host_interface=sub_host_interface,
                root_dir=os.path.dirname(abs_path),
                parent_context=self.execution_context.runtime_context,
                isolated=False  # 已在HostService层处理
            )

            sub_interpreter.sync_state(self.execution_context.runtime_context, policy)
            return sub_interpreter.run()

        except Exception as e:
            deserializer = RuntimeDeserializer(self.registry)
            restored_ctx = deserializer.deserialize_context(snapshot)
            self._rebind_environment(restored_ctx)
            self.execution_context.runtime_context = restored_ctx
            raise e

    def get_source(self) -> str:
        """元编程：获取当前运行模块的源代码"""
        current_mod = self.get_current_module_callback()
        return self.compiler.get_module_source(current_mod) or ""
