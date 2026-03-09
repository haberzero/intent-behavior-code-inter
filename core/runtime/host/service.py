from typing import Any, Dict, Optional, List, TYPE_CHECKING
import os
import json
import uuid
from core.runtime.serialization.runtime_serializer import RuntimeSerializer, RuntimeDeserializer
from core.runtime.interfaces import ServiceContext, IHostService, IInterpreterFactory
from core.foundation.host_interface import HostInterface
from core.runtime.module_system.loader import ModuleLoader

class HostService(IHostService):
    """
    IBCI 2.0 内核级宿主服务子系统。
    负责运行现场的持久化、隔离执行以及元编程能力。
    """
    def __init__(self, context: ServiceContext, factory: IInterpreterFactory):
        self.context = context
        self.factory = factory

    def sync(self):
        """
        安全点同步 (Safe Point Sync) 原语。
        目前在单线程环境下，其作用是触发所有已注册资源的清理与状态导出。
        """
        # TODO: 未来多线程环境下，此处将触发 Global Barrier
        pass

    def save_state(self, path: str):
        """深度序列化当前运行时上下文并保存到磁盘"""
        self.sync() # 必须先同步
        serializer = RuntimeSerializer(self.context.registry)
        data = serializer.serialize_context(self.context.runtime_context)
        
        abs_path = os.path.abspath(path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_state(self, path: str):
        """从磁盘加载快照并恢复当前现场"""
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"State file not found: {abs_path}")
            
        with open(abs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        deserializer = RuntimeDeserializer(self.context.registry)
        # [IES 2.0] 使用特权恢复模式重建上下文
        new_ctx = deserializer.deserialize_context(data)
        
        # 重新绑定环境能力 (Intrinsics & Plugins)
        self._rebind_environment(new_ctx, deserializer)
        
        # 强制同步到当前解释器实例
        self.context.interpreter.context = new_ctx

    def _rebind_environment(self, context: Any, deserializer: Optional[Any] = None):
        """
        环境重绑定：将快照中的“空壳”重新链接到当前物理环境的功能实现。
        """
        # 1. 重新注入内置函数 (Intrinsics) - 使用特权覆盖
        self.context.interpreter.setup_context(context, force=True, deserializer=deserializer)
        
        # 2. 重新注入原生插件 (Native Plugins)
        from core.runtime.objects.kernel import IbObject, IbNativeObject
        for name in self.context.interop.host_interface.get_all_module_names():
            pkg = self.context.interop.get_package(name)
            if pkg:
                if not isinstance(pkg, IbObject):
                    pkg_obj = IbNativeObject(pkg, self.context.registry.get_class("Object"))
                else:
                    pkg_obj = pkg
                # [IES 2.0 Privileged] 强制覆盖常量符号
                context.global_scope.define(name, pkg_obj, is_const=True, force=True)

    def run_isolated(self, path: str, policy: Dict[str, Any]) -> bool:
        """通过协调器工厂开启隔离的解释器子运行环境"""
        # 1. 自动快照（用于 Snapshot-Try-Restore 事务模型）
        serializer = RuntimeSerializer(self.context.registry)
        snapshot = serializer.serialize_context(self.context.runtime_context)
        
        try:
            abs_path = os.path.abspath(path)
            artifact = self.context.compiler.compile_file(abs_path)
            
            # 2. 根据 policy 决定能力继承
            sub_host_interface = HostInterface()
            inherit_plugins = policy.get("inherit_plugins", [])
            if inherit_plugins is True:
                inherit_plugins = self.context.interop.host_interface.get_all_module_names()
            
            for p_name in inherit_plugins:
                impl = self.context.interop.host_interface.get_module_implementation(p_name)
                meta = self.context.interop.host_interface.get_module_type(p_name)
                if impl:
                    sub_host_interface.register_module(p_name, impl, meta)
            
            # 3. 通过工厂创建隔离解释器 (彻底切断对 Interpreter 类的物理依赖)
            sub_interpreter = self.factory.spawn_interpreter(
                artifact=artifact, 
                registry=self.context.registry,
                host_interface=sub_host_interface,
                root_dir=os.path.dirname(abs_path),
                parent_context=self.context.runtime_context
            )
            
            # 4. 状态继承逻辑
            if policy.get("inherit_intents", False):
                sub_interpreter.context.intent_stack = list(self.context.runtime_context.intent_stack)
            
            # 5. 执行
            return sub_interpreter.run()
            
        except Exception as e:
            # 事务回滚
            deserializer = RuntimeDeserializer(self.context.registry)
            restored_ctx = deserializer.deserialize_context(snapshot)
            self._rebind_environment(restored_ctx)
            self.context.interpreter.context = restored_ctx
            raise e

    def get_source(self) -> str:
        """元编程：获取当前运行模块的源代码"""
        current_mod = self.context.interpreter.current_module_name
        return self.context.compiler.get_module_source(current_mod) or ""
