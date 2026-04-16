import os
import importlib.util
import inspect
import sys
from typing import List, Dict, Any, Optional, Set
from core.runtime.exceptions import RegistryIsolationError
from core.base.enums import RegistrationState

from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_trace
from core.runtime.interfaces import IModuleLoader, ServiceContext
from core.runtime.interfaces import IExecutionContext
from core.base.interfaces import IStateReader, ILLMExecutor, ISymbolView, IIntentManager
from core.extension.capabilities import ExtensionCapabilities
from core.kernel.issue import InterpreterError
from core.kernel.spec import MethodMemberSpec
from core.kernel.symbols import FunctionSymbol

class ModuleLoader(IModuleLoader):
    """
    IBC-Inter 运行时模块加载器。
    负责在执行阶段动态加载模块实现，并注入所需的依赖。
    """
    def __init__(self, search_paths: List[str], capability_registry: Optional[Any] = None):
        self.search_paths = [os.path.abspath(p) for p in search_paths]
        self.capability_registry = capability_registry

    def _validate_and_bind(self, module_name: str, implementation: Any, context: ServiceContext, capabilities: ExtensionCapabilities, registry: Any):
        """
        严格契约绑定。
        
        1. 元数据必须已通过 Discovery 阶段从 _spec.py 加载并注册到 HostInterface。
        2. 实现对象必须包含元数据中声明的所有成员。
        3. 严禁隐式反射，所有暴露给 IBC-Inter 的成员必须在 _spec.py 中显式声明。
        """
        # [Registry Isolation] 虚表隔离检查
        if hasattr(implementation, '_ibci_registry_id'):
            if implementation._ibci_registry_id != id(context.registry):
                raise RegistryIsolationError(f"Security Violation: Plugin '{module_name}' is already bound to another engine instance.")
        
        implementation._ibci_registry_id = id(context.registry)

        # 从元数据注册表解析 (元数据来源于 _spec.py)
        metadata = context.interop.metadata.resolve(module_name)
        from core.kernel.spec import ModuleSpec
        if not metadata or not isinstance(metadata, ModuleSpec):
            raise InterpreterError(f"Plugin Protocol Error: Module '{module_name}' metadata not found. "
                                   f"Ensure _spec.py exists and declares __ibcext_vtable__.")

        proxy_vtable = {}
        whitelist = []

        # 遍历元数据中声明的所有成员 (源自 _spec.py)
        for spec_name, spec_member in metadata.members.items():
            # Determine if this member is a callable (new MethodMemberSpec or old Symbol/descriptor compat)
            is_callable_member = isinstance(spec_member, MethodMemberSpec)
            param_count = len(spec_member.param_type_names) if is_callable_member else 0


            # 1. 处理函数/方法
            if is_callable_member:
                # 强制要求实现对象具有同名属性
                if not hasattr(implementation, spec_name):
                    raise InterpreterError(f"Plugin implementation error: Module '{module_name}' is missing required method '{spec_name}' "
                                           f"declared in _spec.py")
                
                py_func = getattr(implementation, spec_name)
                
                if not callable(py_func):
                    raise InterpreterError(f"Plugin implementation error: Module '{module_name}.{spec_name}' is not callable.")
                
                # 校验参数签名
                sig = inspect.signature(py_func)
                params = [p for p in sig.parameters.values() if p.name != 'self']
                fixed_params = [p for p in params if p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)]
                
                # 允许实现层的参数比 spec 多（如果有默认值），但不能少
                if len(fixed_params) < param_count:
                    raise InterpreterError(f"Plugin Error: Module '{module_name}.{spec_name}' signature mismatch. "
                                           f"Spec expects {param_count} params, but implementation has only {len(fixed_params)}.")
                
                def create_proxy(target_func, reg):
                    def proxy_wrapper(*args, **kwargs):
                        # UTS: 自动拆箱 (IbObject -> Native)
                        native_args = [a.to_native() if hasattr(a, 'to_native') else a for a in args]
                        native_kwargs = {k: (v.to_native() if hasattr(v, 'to_native') else v) for k, v in kwargs.items()}
                        
                        # 执行 Python 函数
                        result = target_func(*native_args, **native_kwargs)
                        
                        # UTS: 自动装箱 (Native -> IbObject)
                        return reg.box(result)
                    return proxy_wrapper

                proxy_vtable[spec_name] = create_proxy(py_func, registry)
            
            # 2. 处理变量 (Variable / plain MemberSpec)
            else:
                # 只要在元数据中声明了，就加入白名单允许通过 __getattr__ 访问
                if not hasattr(implementation, spec_name):
                     raise InterpreterError(f"Plugin implementation error: Module '{module_name}' is missing required variable '{spec_name}' "
                                           f"declared in _spec.py")
                whitelist.append(spec_name)

        # 封印虚表和白名单到实现对象上
        implementation._ibci_vtable = proxy_vtable
        implementation._ibci_whitelist = whitelist

    def _setup_implementation(self, implementation, context: ServiceContext, capabilities: ExtensionCapabilities):
        """强制依赖注入协议：必须且仅接受 capabilities 参数"""
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

        # 准备扩展能力集合
        capabilities = ExtensionCapabilities(_registry=registry, _capability_registry=self.capability_registry)

        # 注入 execution_context，使插件可以访问入口文件路径
        capabilities.execution_context = execution_context

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
        
        # 优先处理 HostInterface 中已手动注册的实现 (用于测试和热插拔)
        # 这确保了手动注册的 Mock 对象能被正确初始化并同步到 capabilities
        # 直接遍历元数据注册表，消除兼容性接口
        interop = context.interop
        for entry in interop.metadata.get_all_modules().keys():
            implementation = interop.get_package(entry)
            if not implementation: continue

            self._validate_and_bind(entry, implementation, context, capabilities, registry)
            
            self._setup_implementation(implementation, context, capabilities)
                
            loaded_modules.add(entry)

        # 扫描搜索路径，加载所有物理存在的模块
        for path in self.search_paths:
            if not os.path.isdir(path):
                continue
                
            for entry in os.listdir(path):
                if entry in loaded_modules:
                    continue
                
                # [SECURITY] 仅加载 HostInterface 中已注册元数据的模块 (已发现的模块)
                # 通过 discovery_map 映射物理目录名到逻辑模块名
                module_name = interop.get_module_name_by_discovery(entry)
                if not module_name:
                    continue
                    
                module_dir = os.path.join(path, entry)
                if not os.path.isdir(module_dir):
                    continue
                
                # 实现层通常在 __init__.py 中
                impl_path = os.path.join(module_dir, "__init__.py")
                if not os.path.exists(impl_path):
                    continue
                    
                try:
                    # 动态加载实现层
                    # 必须支持跨项目根目录加载（如 examples_temp/plugins/calc）
                    pkg_dir = os.path.dirname(module_dir)
                    if pkg_dir not in sys.path:
                        sys.path.insert(0, pkg_dir)
                    
                    # 使用 importlib 直接导入文件夹作为包，这能正确处理内部的相对导入
                    mod = importlib.import_module(entry)
                    
                    # 实例化：优先寻找 create_implementation 工厂
                    if hasattr(mod, 'create_implementation'):
                        implementation = mod.create_implementation()
                    elif hasattr(mod, 'implementation'):
                        # 其次寻找导出名为 implementation 的对象
                        implementation = mod.implementation
                    else:
                        # 兼容直接导出的类或函数（如有必要可扩展）
                        continue

                    # 1. 自动依赖注入 (基于 setup 方法签名)
                    # 必须在校验前注入，因为插件可能根据注入的能力动态决定其虚表 (vtable)
                    self._setup_implementation(implementation, context, capabilities)
                    
                    # 2. 校验与绑定 (Proxy VTable)
                    self._validate_and_bind(module_name, implementation, context, capabilities, registry)
                    
                    # 绑定到运行时宿主
                    interop.register_package(module_name, implementation)
                    loaded_modules.add(entry)
                    
                except Exception as e:
                    # 插件加载失败必须导致初始化中断，严禁静默失败
                    raise InterpreterError(f"Plugin Critical Error: Failed to load implementation for module '{entry}': {e}")
