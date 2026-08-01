# Python plugin loading boundary — native paths intentional.
#
# 本模块位于 IBCI 运行时与 Python importlib 的交界：扫描到的目录最终喂给
# os.listdir / os.path.isdir / os.path.exists、sys.path.insert 以及
# importlib.import_module。这些 API 必须使用原生字符串，因此保留 os.path
# 进行 FS 查询与 importlib 路径构造，不在每个边界点强行 IbPath 化。
#
# 路径规范化责任上移：IBCIEngine._resolve_plugin_search_paths 已通过
# PathValidator.canonicalize_for_security / InstallPaths.modules_dir().to_native()
# 提供绝对原生路径，此处不再重复 os.path.abspath。
import os
import importlib.util
import inspect
import sys
from typing import List, Dict, Any, Optional, Set

from core.base.path import IbPath
from core.runtime.exceptions import RegistryIsolationError
from core.base.enums import RegistrationState
from core.runtime.path import InstallPaths

from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_trace
from core.runtime.interfaces import IModuleLoader, ServiceContext
from core.runtime.interfaces import IExecutionContext
from core.base.interfaces import IStateReader, ISymbolView, IIntentManager


def _is_callable_object(obj: Any) -> bool:
    """判断对象是否为可调用实例（behavior / fn_callable / callable）。

    可调用实例不是数据值：应原样透传给插件实现层，而非拆箱成 native
    （未执行的可调用对象 ``to_native()`` 会显式抛错）。
    """
    cls = getattr(obj, "ib_class", None)
    if cls is None:
        return False
    name = getattr(cls, "name", "") or ""
    return (
        name in ("behavior", "fn_callable", "callable")
        or name.startswith("fn_callable[")
        or name.startswith("behavior[")
    )
from core.extension.capabilities import ExtensionCapabilities
from core.kernel.issue import InterpreterError
from core.kernel.spec import MethodMemberSpec, IbSpec, TypeKind
from core.kernel.symbols import FunctionSymbol

class ModuleLoader(IModuleLoader):
    """
    IBC-Inter 运行时模块加载器。
    负责在执行阶段动态加载模块实现，并注入所需的依赖。
    """
    def __init__(self, search_paths: List[str], capability_registry: Optional[Any] = None):
        # 仅做分隔符规范化；调用方保证路径为绝对路径。
        self.search_paths = [IbPath.from_native(p).to_native() for p in search_paths]
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
        if not isinstance(metadata, IbSpec) or metadata.kind != TypeKind.MODULE.value:
            raise InterpreterError(f"Plugin Protocol Error: Module '{module_name}' metadata not found. "
                                   f"Ensure _spec.py exists and declares __ibcext_vtable__.")

        proxy_vtable = {}
        whitelist = []

        # 遍历元数据中声明的所有成员 (源自 _spec.py)
        for spec_name, spec_member in metadata.members.items():
            is_callable_member = isinstance(spec_member, MethodMemberSpec)
            param_count = len(spec_member.param_types) if is_callable_member else 0


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

                # 运行时参数元数据（供统一实参绑定器做具名/默认解析）
                param_meta = None
                declared_descriptors = getattr(spec_member, "param_descriptors", None) or []
                if declared_descriptors:
                    param_meta = [
                        (d.name, d.kind, ("value", d.default_value) if d.has_default else None)
                        for d in declared_descriptors
                    ]
                    # 具名参数契约：声明名称必须被实现接受（具名调用依赖名称匹配）
                    impl_names = {p.name for p in params}
                    has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
                    for d in declared_descriptors:
                        if d.kind in ("POSITIONAL_OR_KEYWORD", "KEYWORD_ONLY") \
                                and d.name not in impl_names and not has_varkw:
                            raise InterpreterError(
                                f"Plugin Error: Module '{module_name}.{spec_name}' declares param "
                                f"'{d.name}' but implementation does not accept it by name."
                            )

                def create_proxy(target_func, reg, meta):
                    def proxy_wrapper(*args, **kwargs):
                        # UTS: 自动拆箱 (IbObject -> Native)
                        # 可调用实例（behavior/fn_callable/callable）不是数据值，
                        # 原样透传给实现层（插件按 IBCI 对象处理），避免误拆箱
                        # 触发未执行 callable 的 to_native() 抛错。
                        native_args = [
                            a if _is_callable_object(a)
                            else (a.to_native() if hasattr(a, 'to_native') else a)
                            for a in args
                        ]
                        native_kwargs = {
                            k: (v if _is_callable_object(v)
                                else (v.to_native() if hasattr(v, 'to_native') else v))
                            for k, v in kwargs.items()
                        }

                        # 执行 Python 函数
                        result = target_func(*native_args, **native_kwargs)

                        # UTS: 自动装箱 (Native -> IbObject)
                        return reg.box(result)
                    proxy_wrapper._ibci_param_meta = meta
                    return proxy_wrapper

                proxy_vtable[spec_name] = create_proxy(py_func, registry, param_meta)
            
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

        # 安装路径（ibci_modules/）与其他插件路径的 import 命名空间区分：
        # ibci_modules 下子目录须作为 ibci_modules.<name> 导入，避免 namespace
        # package 造成 ibci_ai 与 ibci_modules.ibci_ai 两个模块对象。
        install_path = InstallPaths.modules_dir().to_native()

        # 扫描搜索路径，加载所有物理存在的模块
        for path in self.search_paths:
            if not os.path.isdir(path):
                continue

            # 当前搜索路径是否为 ibci_modules 安装目录
            is_install_path = os.path.normcase(path) == os.path.normcase(install_path)

            for entry in os.listdir(path):
                if entry in loaded_modules:
                    continue

                # [SECURITY] 仅加载 HostInterface 中已注册元数据的模块 (已发现的模块)
                # 通过 discovery_map 映射物理目录名到逻辑模块名
                module_name = interop.get_module_name_by_discovery(entry)
                if not module_name:
                    continue

                # kernel-native 模块已在构造期预注册，不再从磁盘加载覆盖
                if interop.host_interface.is_kernel_native(module_name):
                    loaded_modules.add(entry)
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
                    added_paths = []
                    pkg_dir = os.path.dirname(module_dir)
                    if pkg_dir not in sys.path:
                        sys.path.insert(0, pkg_dir)
                        added_paths.append(pkg_dir)

                    # 安装路径下的包使用完整命名空间 ibci_modules.<name>，
                    # 用户插件路径仍使用目录名作为顶层包名。
                    import_name = f"ibci_modules.{entry}" if is_install_path else entry
                    if import_name in sys.modules:
                        core_trace(CoreModule.SCHEDULER, DebugLevel.DETAIL,
                                   f"Plugin '{import_name}' already loaded process-wide; reusing cached module per same-name identity contract.")
                    mod = importlib.import_module(import_name)
                    
                    # 实例化：优先寻找 create_implementation 工厂
                    if hasattr(mod, 'create_implementation'):
                        implementation = mod.create_implementation()
                    elif hasattr(mod, 'implementation'):
                        # 其次寻找导出名为 implementation 的对象
                        implementation = mod.implementation
                    else:
                        # 支持直接导出的类或函数（如有必要可扩展）
                        core_trace(CoreModule.SCHEDULER, DebugLevel.BASIC,
                                   f"Module '{module_name}' skipped: no create_implementation() or implementation export found")
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
                    raise InterpreterError(f"Plugin Critical Error: Failed to load implementation for module '{entry}': {e}") from e
                finally:
                    # sys.path 用后即还：插件代码已进入 sys.modules，包内相对导入经 __package__ 解析，
                    # 不再依赖 sys.path 残留；stdlib/core 经各自既定路径解析。
                    for p in added_paths:
                        if p in sys.path:
                            sys.path.remove(p)
