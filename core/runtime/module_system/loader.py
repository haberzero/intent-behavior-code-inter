import os
import importlib.util
import inspect
from typing import List, Any, Optional
from core.runtime.interfaces import ServiceContext
from core.foundation.interfaces import (
    ExtensionCapabilities, IStateReader, IStackInspector, 
    ILLMProvider, IIntentManager, ILLMExecutor
)
from core.domain.issue import InterpreterError

class ModuleLoader:
    """
    IBC-Inter 运行时模块加载器。
    负责在执行阶段动态加载模块实现，并注入所需的依赖。
    """
    def __init__(self, search_paths: List[str]):
        self.search_paths = [os.path.abspath(p) for p in search_paths]

    def _validate_and_bind(self, module_name: str, implementation: Any, context: ServiceContext):
        """[IES 2.0] 校验实现是否符合契约，并构建静态原生虚函数表 (Native VTable)"""
        host_interface = context.interop.host_interface
        metadata = host_interface.get_module_type(module_name)
        if not metadata: return

        # 构建 VTable 映射：契约方法名 -> 绑定的 Python 函数/方法
        vtable = {}
        for attr_name in dir(implementation):
            attr = getattr(implementation, attr_name)
            
            # [FIX] 处理 bound method，获取其原始函数上的元数据
            binding = getattr(attr, '_ibci_binding', None)
            if not binding and hasattr(attr, '__func__'):
                binding = getattr(attr.__func__, '_ibci_binding', None)
            
            if not binding: continue

            # 1. 契约存在性校验
            spec_name = binding.spec_name
            if spec_name not in metadata.members:
                raise InterpreterError(f"Plugin Error: Module '{module_name}' implementation '{attr_name}' binds to non-existent spec '{spec_name}'")

            # 2. 签名一致性校验
            spec_func = metadata.members[spec_name]
            from core.domain.types.descriptors import FunctionMetadata
            if not isinstance(spec_func, FunctionMetadata):
                continue

            sig = inspect.signature(attr)
            params = [p for p in sig.parameters.values() if p.name != 'self']
            fixed_params = [p for p in params if p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)]
            
            if len(fixed_params) != len(spec_func.param_types):
                raise InterpreterError(f"Plugin Error: Module '{module_name}.{spec_name}' signature mismatch. Spec expects {len(spec_func.param_types)} params, but Python implementation has {len(fixed_params)}.")

            # 3. 注册到 VTable
            vtable[spec_name] = attr

        # 将 VTable 附加到实现对象上，供 IbNativeObject 使用
        implementation._ibci_vtable = vtable

    def _setup_implementation(self, implementation, context: ServiceContext, capabilities: ExtensionCapabilities):
        """IES 2.0 自动依赖注入协议"""
        if not hasattr(implementation, 'setup'): return
        
        sig = inspect.signature(implementation.setup)
        params = {}
        if 'permission_manager' in sig.parameters:
            params['permission_manager'] = context.permission_manager
        if 'executor' in sig.parameters:
            params['executor'] = context.llm_executor
        if 'service_context' in sig.parameters:
            params['service_context'] = context
        if 'capabilities' in sig.parameters:
            params['capabilities'] = capabilities
        
        if params:
            implementation.setup(**params)

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
        if isinstance(context.runtime_context, IIntentManager):
            capabilities.intent_manager = context.runtime_context
        if isinstance(context.llm_executor, ILLMExecutor):
            capabilities.llm_executor = context.llm_executor
        
        # [Active Defense] 注入只读符号视图
        capabilities.symbol_view = context.symbol_view
        
        loaded_modules = set()
        
        # [IES Enhancement] 优先处理 HostInterface 中已手动注册的实现 (用于测试和热插拔)
        # 这确保了手动注册的 Mock 对象能被正确初始化并同步到 capabilities
        host_interface = interop.host_interface
        for entry in host_interface.get_all_module_names():
            implementation = host_interface.get_module_implementation(entry)
            if not implementation: continue
            
            # [IES 2.0] 校验与绑定
            self._validate_and_bind(entry, implementation, context)
            
            self._setup_implementation(implementation, context, capabilities)
            loaded_modules.add(entry)
            # 即使已存在，我们也尝试同步 LLM Provider (以防手动注册的是 AI 模块)
            if capabilities.llm_provider and hasattr(llm_executor, 'llm_callback'):
                llm_executor.llm_callback = capabilities.llm_provider

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
                    
                    # [IES 2.0] 校验与绑定
                    self._validate_and_bind(entry, implementation, context)
                    
                    # 自动依赖注入 (基于 setup 方法签名)
                    self._setup_implementation(implementation, context, capabilities)
                    
                    # 核心能力同步：如果模块提供了 LLMProvider，同步到内核执行器
                    if capabilities.llm_provider and hasattr(llm_executor, 'llm_callback'):
                        llm_executor.llm_callback = capabilities.llm_provider
                    
                    # 绑定到运行时宿主
                    interop.register_package(entry, implementation)
                    loaded_modules.add(entry)
                    
                except Exception as e:
                    print(f"Warning: Failed to load implementation for module '{entry}': {e}")
