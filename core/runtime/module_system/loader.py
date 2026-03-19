import os
import importlib.util
import inspect
import sys
from typing import List, Dict, Any, Optional, Set
from core.runtime.exceptions import RegistryIsolationError
from core.runtime.enums import RegistrationState
from core.extension import ibcext

from core.foundation.diagnostics.core_debugger import CoreModule, DebugLevel, core_trace
from core.runtime.interfaces import (
    IModuleLoader, ServiceContext
)
from core.foundation.interfaces import (
    ExtensionCapabilities, IExecutionContext,
    IStackInspector, IStateReader, IIntentManager, ILLMExecutor, ILLMProvider, ISymbolView
)
from core.domain.issue import InterpreterError
from core.domain.types.descriptors import FunctionMetadata
from core.domain.symbols import FunctionSymbol

class ModuleLoader(IModuleLoader):
    """
    IBC-Inter 运行时模块加载器。
    负责在执行阶段动态加载模块实现，并注入所需的依赖。
    """
    def __init__(self, search_paths: List[str]):
        self.search_paths = [os.path.abspath(p) for p in search_paths]

    def _validate_and_bind(self, module_name: str, implementation: Any, context: ServiceContext, capabilities: ExtensionCapabilities):
        """[IES 2.0] 强制执行显式契约绑定并构建自动装箱虚函数表 (Proxy VTable)"""
        # [Registry Isolation] 虚表隔离检查：严禁跨引擎复用已关联虚表的插件对象
        if hasattr(implementation, '_ibci_registry_id'):
            if implementation._ibci_registry_id != id(context.registry):
                raise RegistryIsolationError(f"Security Violation: Plugin '{module_name}' is already bound to another engine instance. [IES 2.0 Isolation Rule]")
        
        # 记录绑定身份
        implementation._ibci_registry_id = id(context.registry)

        # [IES 2.1 Refactor] 直接通过元数据注册表解析，消除 HostInterface 兼容性依赖
        metadata = context.interop.host_interface.metadata.resolve(module_name)
        if not metadata or not metadata.is_module():
            raise InterpreterError(f"Plugin Error: Module '{module_name}' metadata not found or invalid. Discovery must happen before loading.")

        if not hasattr(implementation, 'get_vtable'):
            raise InterpreterError(f"Plugin Error: Module '{module_name}' implementation is missing 'get_vtable()'.")
            
        # [IES 2.1 Refactor] 统一使用 IbPlugin 契约或显式 VTable
        raw_vtable = implementation.get_vtable()
        if not isinstance(raw_vtable, dict):
            raise InterpreterError(f"Plugin Error: Module '{module_name}' get_vtable() must return a dictionary.")
            
        proxy_vtable = {}

        # 遍历元数据中声明的所有成员函数
        for spec_name, spec_member in metadata.members.items():
            # [IES 2.0] 成员可能已经被水合为 Symbol，需要检查其底层描述符
            spec_desc = spec_member.descriptor if hasattr(spec_member, 'descriptor') else spec_member
            # [IES 2.1 Refactor] 使用能力探测替代 isinstance 检查
            if not (spec_desc.get_call_trait() and not spec_desc.is_class()): 
                continue
                
            if spec_name not in raw_vtable:
                raise InterpreterError(f"Plugin Error: Module '{module_name}' implementation is missing required method '{spec_name}'")
            
            py_func = raw_vtable[spec_name]
            if not callable(py_func):
                raise InterpreterError(f"Plugin Error: Module '{module_name}.{spec_name}' implementation is not callable.")
            
            # 校验参数签名
            sig = inspect.signature(py_func)
            # 忽略 self
            params = [p for p in sig.parameters.values() if p.name != 'self']
            # 仅校验固定位置参数数量，忽略 *args 和 **kwargs
            fixed_params = [p for p in params if p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)]
            
            if len(fixed_params) != len(spec_desc.param_types):
                raise InterpreterError(f"Plugin Error: Module '{module_name}.{spec_name}' signature mismatch. Spec expects {len(spec_desc.param_types)} params, but Python implementation has {len(fixed_params)}.")
            
            # [IES 2.0 Proxy] 自动装箱代理：拦截 Python 返回值并应用 SDK.box()
            def create_proxy(target_func):
                def proxy_wrapper(*args, **kwargs):
                    # 自动拆箱：将 IbObject 参数转换为 Python 原生类型
                    native_args = [a.to_native() if hasattr(a, 'to_native') else a for a in args]
                    native_kwargs = {k: (v.to_native() if hasattr(v, 'to_native') else v) for k, v in kwargs.items()}
                    
                    result = target_func(*native_args, **native_kwargs)
                    
                    # 自动平权包装：确保返回给解释器的永远是 IbObject
                    return capabilities.box(result)
                return proxy_wrapper

            proxy_vtable[spec_name] = create_proxy(py_func)

        # 封印虚表到实现对象上
        implementation._ibci_vtable = proxy_vtable

    def _setup_implementation(self, implementation, context: ServiceContext, capabilities: ExtensionCapabilities):
        """IES 2.0 强制依赖注入协议：必须且仅接受 capabilities 参数"""
        if not hasattr(implementation, 'setup'): return
        
        # 统一注入 ServiceContext 到容器中
        capabilities.service_context = context
        
        sig = inspect.signature(implementation.setup)
        # 强制要求 setup(capabilities) 或 setup(self, capabilities)
        if 'capabilities' not in sig.parameters:
            raise InterpreterError(f"Plugin Error: Module setup method must accept 'capabilities' parameter.")
            
        # 执行注入
        implementation.setup(capabilities=capabilities)

    def load_and_register_all(self, context: ServiceContext, execution_context: IExecutionContext):
        """
        扫描搜索路径，加载所有模块实现并绑定到 InterOp。
        """
        registry = execution_context.registry
        if registry:
            registry.verify_level(RegistrationState.STAGE_4_PLUGIN_IMPL.value)
            
        interop = context.interop
        permission_manager = context.permission_manager
        llm_executor = context.llm_executor
        
        # 准备扩展能力集合 (IES 2.0 SDK)
        capabilities = ExtensionCapabilities(registry=registry)
        
        rt_context = execution_context.runtime_context
        if rt_context:
            if isinstance(rt_context, IStateReader):
                capabilities.state_reader = rt_context
            if isinstance(rt_context, IIntentManager):
                capabilities.intent_manager = rt_context
            
            # [Active Defense] 注入只读符号视图 (通过 RuntimeContext 获取)
            if hasattr(rt_context, 'get_symbol_view'):
                capabilities.symbol_view = rt_context.get_symbol_view()
                
        capabilities.stack_inspector = execution_context.stack_inspector
            
        if isinstance(context.llm_executor, ILLMExecutor):
            capabilities.llm_executor = context.llm_executor
        
        loaded_modules = set()
        
        # [IES Enhancement] 优先处理 HostInterface 中已手动注册的实现 (用于测试和热插拔)
        # 这确保了手动注册的 Mock 对象能被正确初始化并同步到 capabilities
        # [IES 2.1 Refactor] 直接遍历元数据注册表，消除兼容性接口
        host_interface = interop.host_interface
        for entry in host_interface.metadata.get_all_modules().keys():
            implementation = host_interface.get_module_implementation(entry)
            if not implementation: continue
            
            # [IES 2.0] 校验与绑定 (传入 capabilities 以支持 Proxy VTable 包装)
            self._validate_and_bind(entry, implementation, context, capabilities)
            
            self._setup_implementation(implementation, context, capabilities)
            
            # [IES 2.0 FIX] 必须显式注册到 InterOp，否则模块无法被 import
            interop.register_package(entry, implementation)
            
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
                
                # [SECURITY] 仅加载 HostInterface 中已注册元数据的模块 (已发现的模块)
                # 这防止了隔离环境下的子脚本通过扫描路径加载未授权的敏感插件
                # [IES 2.1 Refactor] 直接解析元数据以进行安全检查
                if not host_interface.metadata.resolve(entry):
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
                    # [IES 2.0] 使用标准的包路径加载，以支持内部相对导入
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                    if project_root not in sys.path:
                        sys.path.insert(0, project_root)
                    
                    # 使用全路径加载 (例如 ibc_modules.idbg)
                    full_pkg_name = f"ibc_modules.{entry}"
                    mod = importlib.import_module(full_pkg_name)
                    
                    # 实例化：优先寻找 create_implementation 工厂
                    if hasattr(mod, 'create_implementation'):
                        implementation = mod.create_implementation()
                    elif hasattr(mod, 'implementation'):
                        # 其次寻找导出名为 implementation 的对象
                        implementation = mod.implementation
                    else:
                        # 兼容直接导出的类或函数（如有必要可扩展）
                        continue
                    
                    # [IES 2.0] 1. 自动依赖注入 (基于 setup 方法签名)
                    # 必须在校验前注入，因为插件可能根据注入的能力动态决定其虚表 (vtable)
                    self._setup_implementation(implementation, context, capabilities)
                    
                    # [IES 2.0] 2. 校验与绑定 (Proxy VTable)
                    self._validate_and_bind(entry, implementation, context, capabilities)
                    
                    # 核心能力同步：如果模块提供了 LLMProvider，同步到内核执行器
                    if capabilities.llm_provider and hasattr(llm_executor, 'llm_callback'):
                        llm_executor.llm_callback = capabilities.llm_provider
                    
                    # 绑定到运行时宿主
                    interop.register_package(entry, implementation)
                    loaded_modules.add(entry)
                    
                except Exception as e:
                    # [IES 2.0 Strict] 插件加载失败必须导致初始化中断，严禁静默失败
                    raise InterpreterError(f"Plugin Critical Error: Failed to load implementation for module '{entry}': {e}")
