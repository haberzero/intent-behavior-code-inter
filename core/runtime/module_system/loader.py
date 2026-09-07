# IBCI 运行时不扫描磁盘查找用户插件（用户侧扩展唯一边 =
# 宿主绑定 bind）。本 loader 仅负责对构造期已注册的内置模块做契约绑定与
# setup(capabilities) 注入（load_and_register_all 单一入口）。
import inspect
import weakref
from typing import Any, Optional

from core.runtime.exceptions import RegistryIsolationError
from core.base.enums import RegistrationState

from core.runtime.interfaces import IModuleLoader, ServiceContext
from core.runtime.interfaces import IExecutionContext
from core.runtime.objects.kernel.base import unbox
from core.base.interfaces import IStateReader, IIntentManager
from core.runtime.module_system.proxy import create_proxy
from core.extension.capabilities import ExtensionCapabilities
from core.kernel.issue import InterpreterError
from core.kernel.spec import MethodMemberSpec, IbSpec, TypeKind


# 跨引擎单例守卫：process 级 weak map（实现对象 -> 首次绑定 registry 身份）。
# 保留"同一实现对象不得绑定到两个活跃引擎"的加载期隔离语义（如模块导出
# 模块级 ``implementation`` 单例时），同时避免向实现对象注入私有属性。
_BOUND_IMPLEMENTATIONS: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()

class ModuleLoader(IModuleLoader):
    """
    IBC-Inter 运行时模块加载器。
    负责对已注册模块实现做严格契约绑定，并注入所需的依赖（setup）。
    """
    def __init__(self, capability_registry: Optional[Any] = None):
        self.capability_registry = capability_registry

    def _validate_and_bind(self, module_name: str, implementation: Any, context: ServiceContext, capabilities: ExtensionCapabilities, registry: Any):
        """
        严格契约绑定。

        1. 元数据必须已在 HostInterface 注册（内置模块 = 构造期内联 spec；
           宿主绑定 = bind 声明）。
        2. 实现对象必须包含元数据中声明的所有成员。
        3. 严禁隐式反射，所有暴露给 IBC-Inter 的成员必须在 spec 中显式声明。
        """
        # [Registry Isolation] 跨引擎单例守卫：同一实现对象已绑定其他引擎
        # registry → 拒绝（隔离身份经 BoundPlugin 容器 / weak map 承载，不注入属性）。
        bound_registry_id = _BOUND_IMPLEMENTATIONS.get(implementation)
        if bound_registry_id is not None and bound_registry_id != id(context.registry):
            raise RegistryIsolationError(f"Security Violation: Plugin '{module_name}' is already bound to another engine instance.")
        _BOUND_IMPLEMENTATIONS[implementation] = id(context.registry)

        # 从元数据注册表解析（内置模块 = 构造期内联 spec；宿主绑定 = bind 声明）
        metadata = context.interop.metadata.resolve(module_name)
        if not isinstance(metadata, IbSpec) or metadata.kind != TypeKind.MODULE.value:
            raise InterpreterError(f"Plugin Protocol Error: Module '{module_name}' metadata not found. "
                                   f"Ensure the module spec is registered (builtin inline spec / host binding).")

        proxy_vtable = {}
        whitelist = []

        # 遍历元数据中声明的所有成员
        for spec_name, spec_member in metadata.members.items():
            is_callable_member = isinstance(spec_member, MethodMemberSpec)

            # 1. 处理函数/方法
            if is_callable_member:
                # 强制要求实现对象具有同名属性
                if not hasattr(implementation, spec_name):
                    raise InterpreterError(f"Plugin implementation error: Module '{module_name}' is missing required method '{spec_name}' "
                                           f"declared in the module spec")
                
                py_func = getattr(implementation, spec_name)
                
                if not callable(py_func):
                    raise InterpreterError(f"Plugin implementation error: Module '{module_name}.{spec_name}' is not callable.")
                
                # 校验参数签名：声明的固定参数（非 *args/**kwargs）实现必须全部接受
                sig = inspect.signature(py_func)
                params = [p for p in sig.parameters.values() if p.name != 'self']
                fixed_params = [p for p in params if p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)]

                # 运行时参数元数据（供统一实参绑定器做具名/默认解析）
                param_meta = None
                has_declared_varkw = False
                declared_descriptors = getattr(spec_member, "param_descriptors", None) or []
                param_meta = [
                    (d.name, d.kind, ("value", d.default_value) if d.has_default else None)
                    for d in declared_descriptors
                ]
                has_declared_varkw = any(d.kind == "VAR_KEYWORD" for d in declared_descriptors)
                fixed_declared_count = sum(
                    1 for d in declared_descriptors
                    if d.kind in ("POSITIONAL_OR_KEYWORD", "KEYWORD_ONLY")
                )

                # 允许实现层的参数比 spec 多（如果有默认值），但不能少
                if len(fixed_params) < fixed_declared_count:
                    raise InterpreterError(f"Plugin Error: Module '{module_name}.{spec_name}' signature mismatch. "
                                           f"Spec expects {fixed_declared_count} fixed params, but implementation has only {len(fixed_params)}.")

                if declared_descriptors:
                    # 具名参数契约：声明名称必须被实现接受（具名调用依赖名称匹配）
                    impl_names = {p.name for p in params}
                    has_impl_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
                    for d in declared_descriptors:
                        if d.kind in ("POSITIONAL_OR_KEYWORD", "KEYWORD_ONLY") \
                                and d.name not in impl_names and not has_impl_varkw:
                            raise InterpreterError(
                                f"Plugin Error: Module '{module_name}.{spec_name}' declares param "
                                f"'{d.name}' but implementation does not accept it by name."
                            )
                    # **kwargs 契约：声明 VAR_KEYWORD 时实现必须接受 **kwargs
                    if has_declared_varkw and not has_impl_varkw:
                        raise InterpreterError(
                            f"Plugin Error: Module '{module_name}.{spec_name}' declares a "
                            f"VAR_KEYWORD param but implementation does not accept **kwargs."
                        )

                proxy_vtable[spec_name] = create_proxy(
                    py_func, registry, param_meta, has_declared_varkw,
                    unbox_args=getattr(spec_member, "unbox_args", True),
                )
            # 2. 处理变量 (Variable / plain MemberSpec)
            else:
                # 只要在元数据中声明了，就加入白名单允许通过 __getattr__ 访问
                if not hasattr(implementation, spec_name):
                     raise InterpreterError(f"Plugin implementation error: Module '{module_name}' is missing required variable '{spec_name}' "
                                           f"declared in the module spec")
                whitelist.append(spec_name)

        # 显式返回 vtable 与白名单（由调用方经 InterOp.bind_native_contract 承载）
        return proxy_vtable, whitelist

    def _setup_implementation(self, implementation, module_name: str, context: ServiceContext, capabilities: ExtensionCapabilities):
        """强制依赖注入协议：必须且仅接受 capabilities 参数"""
        if not hasattr(implementation, 'setup'): return
        
        # 统一注入 ServiceContext 到容器中
        capabilities.service_context = context
        # 以模块名作为当前插件身份（能力注册的 plugin_id）
        capabilities._plugin_id = module_name
        
        sig = inspect.signature(implementation.setup)
        # 强制要求 setup(capabilities) 或 setup(self, capabilities)
        if 'capabilities' not in sig.parameters:
            raise InterpreterError(f"Plugin Error: Module setup method must accept 'capabilities' parameter.")
            
        # 执行注入
        implementation.setup(capabilities=capabilities)

    def load_and_register_all(self, context: ServiceContext, execution_context: IExecutionContext):
        """
        对已注册模块实现做契约绑定与 setup 注入（无磁盘发现/扫描）。

        遍历元数据注册表中所有模块：存在实现（构造期内置模块 / host 绑定 /
        测试手动注册）则严格绑定；无实现（纯元数据）跳过——用户侧扩展不留
        磁盘加载路径（唯一边 = 宿主绑定 bind）。
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
            capabilities.symbol_view = rt_context.get_symbol_view()
                
        capabilities.stack_inspector = execution_context.stack_inspector

        capabilities.llm_executor = context.llm_executor
        
        interop = context.interop
        for entry in interop.metadata.get_all_modules().keys():
            implementation = interop.get_package(entry)
            if not implementation: continue

            vtable, whitelist = self._validate_and_bind(entry, implementation, context, capabilities, registry)
            interop.bind_native_contract(entry, vtable, whitelist)
            
            self._setup_implementation(implementation, entry, context, capabilities)
