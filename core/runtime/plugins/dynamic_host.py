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
        serializer = RuntimeSerializer(self.context.registry)
        # 获取最新的运行时上下文
        ctx = self.context.runtime_context
        data = serializer.serialize_context(ctx)
        
        # 确保目录存在
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_state(self, path: str):
        """[Meta] 从文件加载并覆盖当前运行现场"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"State file not found: {path}")
            
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        deserializer = RuntimeDeserializer(self.context.registry)
        new_ctx = deserializer.deserialize_context(data)
        
        # 覆盖当前解释器的上下文
        self.context.interpreter.context = new_ctx

    def run(self, path: str) -> bool:
        """[Meta] 隔离运行另一个 ibci 文件，运行失败会自动回滚当前环境"""
        # 1. 自动快照：序列化当前上下文作为回滚点
        serializer = RuntimeSerializer(self.context.registry)
        snapshot_data = serializer.serialize_context(self.context.runtime_context)
        
        try:
            # 2. 编译目标文件
            artifact = self.context.compiler.compile_file(path)
            
            # 3. 创建全新的隔离解释器
            # 注意：不传递 artifact_dict 缓存，迫使子解释器重新构建池
            sub_interpreter = Interpreter(
                issue_tracker=self.context.issue_tracker,
                artifact=artifact, # 传入编译产物对象
                registry=self.context.registry, # 共享注册表
                source_provider=self.context.source_provider,
                compiler=self.context.compiler,
                root_dir=os.path.dirname(os.path.abspath(path))
            )
            
            # 4. 执行
            # 找到入口模块的 root_node_uid
            # 由于 compile_file 返回的是 CompilationArtifact，我们需要在子解释器内部获取 UID
            # 实际上，sub_interpreter.run() 应该能处理这个逻辑。
            # 让我们检查一下 Interpreter 是否有 run() 方法。
            if hasattr(sub_interpreter, 'run'):
                return sub_interpreter.run()
            else:
                # Fallback to execute_module
                artifact_dict = sub_interpreter.artifact_dict
                entry_mod = artifact_dict.get("entry_module", "main")
                mod_data = artifact_dict.get("modules", {}).get(entry_mod, {})
                root_uid = mod_data.get("root_node_uid")
                if not root_uid:
                    raise RuntimeError(f"Entry module {entry_mod} not found in artifact.")
                return sub_interpreter.execute_module(root_uid, module_name=entry_mod)
                
        except Exception as e:
            # 5. 事务回滚：如果出错，恢复到之前的快照
            deserializer = RuntimeDeserializer(self.context.registry)
            restored_ctx = deserializer.deserialize_context(snapshot_data)
            self.context.interpreter.context = restored_ctx
            raise e

    def get_self_source(self) -> str:
        """[Meta] 获取当前模块的源代码"""
        return self.context.compiler.get_module_source(self.context.interpreter.current_module_name) or ""

def setup(context: ServiceContext):
    """插件注册入口"""
    host = DynamicHost(context)
    
    # 将插件方法注册为内置函数或对象
    # 这里我们将其注册为一个名为 'host' 的全局对象，或者一组全局函数
    # 按照用户要求，这应该是“动态宿主”插件提供的功能。
    
    # 我们创建一个 IbObject 包装它，或者直接注册函数。
    # 为了方便 ibci 调用，我们注册为全局函数。
    
    context.interpreter.intrinsic_manager.register("host_save_state", host.save_state)
    context.interpreter.intrinsic_manager.register("host_load_state", host.load_state)
    context.interpreter.intrinsic_manager.register("host_run", host.run)
    context.interpreter.intrinsic_manager.register("host_get_source", host.get_self_source)
