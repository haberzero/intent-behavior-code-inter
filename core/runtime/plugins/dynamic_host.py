import os
import json
import copy
from typing import Any, Dict, Optional
from core.runtime.serialization.runtime_serializer import RuntimeSerializer, RuntimeDeserializer
from core.runtime.interfaces import ServiceContext, Interpreter as InterpreterInterface
from core.runtime.interpreter.interpreter import Interpreter

class DynamicHost:
    """
    IBCI 2.0 动态宿主第一方插件。
    实现运行时持久化、隔离执行、事务快照和元编程能力。
    """
    def __init__(self, context: ServiceContext):
        self.context = context

    def save_state(self, path: str):
        """[Meta] 显式保存当前运行现场到文件"""
        if self.context.host_service:
            self.context.host_service.save_state(path)

    def load_state(self, path: str):
        """[Meta] 从文件加载并覆盖当前运行现场"""
        if self.context.host_service:
            self.context.host_service.load_state(path)

    def run(self, path: str) -> bool:
        """[Meta] 隔离运行另一个 ibci 文件，运行失败会自动回滚当前环境"""
        if self.context.host_service:
            # 默认继承所有插件
            policy = {"inherit_plugins": True, "inherit_intents": True}
            return self.context.host_service.run_isolated(path, policy)
        return False

    def get_self_source(self) -> str:
        """[Meta] 获取当前模块的源代码"""
        if self.context.host_service:
            return self.context.host_service.get_source()
        return ""

def setup(context: ServiceContext, intrinsic_manager: Any):
    """插件注册入口"""
    host = DynamicHost(context)
    
    intrinsic_manager.register("host_save_state", host.save_state)
    intrinsic_manager.register("host_load_state", host.load_state)
    intrinsic_manager.register("host_run", host.run)
    intrinsic_manager.register("host_get_source", host.get_self_source)
