import os
import importlib.util
from typing import List
from ..interpreter.interfaces import ServiceContext
from core.runtime.ext.capabilities import ExtensionCapabilities, IStateReader, IStackInspector, ILLMProvider

class ModuleLoader:
    """
    IBC-Inter 运行时模块加载器。
    负责在执行阶段动态加载模块实现，并注入所需的依赖。
    """
    def __init__(self, search_paths: List[str]):
        self.search_paths = [os.path.abspath(p) for p in search_paths]

    def load_and_register_all(self, context: ServiceContext):
        """
        扫描搜索路径，加载所有模块实现并绑定到 InterOp。
        """
        interop = context.interop
        permission_manager = context.permission_manager
        llm_executor = context.llm_executor
        
        # 准备扩展能力集合 (IES 架构核心)
        capabilities = ExtensionCapabilities()
        if isinstance(context.runtime_context, IStateReader):
            capabilities.state_reader = context.runtime_context
        if isinstance(context.interpreter, IStackInspector):
            capabilities.stack_inspector = context.interpreter
        # 注意：llm_provider 初始为 None，可能由模块（如 ai）在 setup 时填充
        
        loaded_modules = set()
        
        for path in self.search_paths:
            if not os.path.isdir(path):
                continue
                
            for entry in os.listdir(path):
                if entry in loaded_modules:
                    continue
                    
                module_dir = os.path.join(path, entry)
                if not os.path.isdir(module_dir):
                    continue
                
                # 实现层通常在 __init__.py 中
                impl_path = os.path.join(module_dir, "__init__.py")
                if not os.path.exists(impl_path):
                    continue
                    
                try:
                    # 动态加载实现
                    internal_name = f"ibc_impl_{entry}"
                    spec = importlib.util.spec_from_file_location(internal_name, impl_path)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    
                    # 实例化：优先寻找 create_implementation 工厂
                    if hasattr(mod, 'create_implementation'):
                        implementation = mod.create_implementation()
                    elif hasattr(mod, 'implementation'):
                        # 其次寻找导出名为 implementation 的对象
                        implementation = mod.implementation
                    else:
                        # 兼容直接导出的类或函数（如有必要可扩展）
                        continue
                    
                    # 自动依赖注入 (基于 setup 方法签名)
                    if hasattr(implementation, 'setup'):
                        import inspect
                        sig = inspect.signature(implementation.setup)
                        params = {}
                        if 'permission_manager' in sig.parameters:
                            params['permission_manager'] = permission_manager
                        if 'executor' in sig.parameters:
                            params['executor'] = llm_executor
                        if 'service_context' in sig.parameters:
                            params['service_context'] = context
                        if 'capabilities' in sig.parameters:
                            params['capabilities'] = capabilities
                        
                        if params:
                            implementation.setup(**params)
                    
                    # 核心能力同步：如果模块提供了 LLMProvider，同步到内核执行器
                    if capabilities.llm_provider and hasattr(llm_executor, 'llm_callback'):
                        llm_executor.llm_callback = capabilities.llm_provider
                    
                    # 绑定到运行时宿主
                    interop.register_package(entry, implementation)
                    loaded_modules.add(entry)
                    
                except Exception as e:
                    print(f"Warning: Failed to load implementation for module '{entry}': {e}")
