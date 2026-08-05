from core.runtime.objects.kernel import IbModule
from core.runtime.objects.intent import IbIntent
from core.runtime.module_system.loader import ModuleLoader
from core.runtime.module_system.discovery import ModuleDiscoveryService
from core.runtime.interfaces import RuntimeContext, InterOp, ModuleInstance, Scope, IObjectFactory, ServiceContext, IIbModule
from typing import List, Dict, Any, Optional, Callable, Tuple, TYPE_CHECKING
from core.kernel import ast as ast
from core.kernel.spec import TypeDef as ModuleType
from core.kernel.issue import InterpreterError
from core.base.diagnostics.codes import DEP_MODULE_NOT_FOUND
from core.runtime.interfaces import IExecutionContext
from core.kernel.registry import KernelRegistry

if TYPE_CHECKING:
    from core.kernel.blueprint import CompilationArtifact

class ModuleInstanceImpl:
    def __init__(self, name: str, scope: Scope):
        self.name = name
        self.scope = scope
        
    def get_variable(self, name: str) -> Any:
        try:
            return self.scope.get(name)
        except (KeyError, AttributeError):
            raise InterpreterError(f"Module '{self.name}' has no attribute '{name}'")

    def __getattr__(self, name: str) -> Any:
        return self.get_variable(name)

class ModuleManagerImpl:
    """
    模块管理器实现。
    负责模块的加载、缓存和导入处理。
    """
    def __init__(self, 
                 interop: InterOp, 
                 registry: KernelRegistry,
                 object_factory: IObjectFactory,
                 execute_module_callback: Callable,
                 artifact: Optional['CompilationArtifact'] = None):
        self.interop = interop
        self.registry = registry
        self.object_factory = object_factory
        self.execute_module_callback = execute_module_callback
        self.artifact = artifact
        self._loaded_modules: Dict[str, ModuleInstance] = {}

    def import_module(self, module_name: str, execution_context: IExecutionContext) -> Any:
        """
        处理 import module_name，返回模块实例
        """
        # 1. 优先从 InterOp 注册包中查找 (Python 扩展/标准库)
        package = self.interop.get_package(module_name)
        if package:
            # 确保 Python 插件实现被正确包装为 IbNativeObject 以支持消息传递
            if not hasattr(package, 'receive'): 
                # 从模块契约显式获取 vtable/白名单（替代私有属性注入）
                contract = self.interop.get_native_contract(module_name)
                vtable = contract[0] if contract else None
                whitelist = contract[1] if contract else None
                native_obj = self.object_factory.create_native_object(package, self.registry.get_class("Object"), vtable=vtable, whitelist=whitelist)
                # 包装为 IbModule 
                return self.object_factory.create_module(module_name, native_obj)
            return package

        # 2. 检查是否已经加载过该模块
        if module_name in self._loaded_modules:
            return self._loaded_modules[module_name]

        # 3. 联动 Artifact (编译蓝图) 处理模块导入
        if self.artifact:
            module_data = self.artifact.get("modules", {}).get(module_name)
            if module_data:
                root_node_uid = module_data.get("root_node_uid")
                
                # 创建该模块的 Global Scope
                module_scope = self.object_factory.create_scope(parent=None)
                
                # 预先创建并缓存模块实例，以支持循环引用 (a -> b -> a)
                module_instance = self.object_factory.create_module(module_name, module_scope)
                self._loaded_modules[module_name] = module_instance
                
                # 在新 Scope 下复用 Interpreter 执行 (通过回调)
                try:
                    self.execute_module_callback(root_node_uid, module_name=module_name, scope=module_scope)
                except Exception:
                    # 如果执行失败，清除缓存以允许后续重试
                    if module_name in self._loaded_modules:
                        del self._loaded_modules[module_name]
                    raise
                
                return module_instance

        raise InterpreterError(f"Module '{module_name}' not found or not registered in artifact.", error_code=DEP_MODULE_NOT_FOUND)

    def _import_star_uid_map(self, execution_context: IExecutionContext) -> Dict[str, str]:
        """读取编译器为 ``from x import *`` 注入当前模块的符号 uid 映射。

        编译器（scheduler）在语义分析期为 import-* 成员创建带 uid 的 Symbol
        （uid = ``scope_<importing_module>:<name>``），并序列化进当前模块
        根作用域的 ``pools.scopes[scope_uid].symbols``（name -> sym_uid）。
        运行时按同一 uid 注入变量，才能与使用点的 ``get_variable_by_uid`` 对齐。
        """
        if not self.artifact:
            return {}
        module_name = execution_context.current_module_name
        if not module_name:
            return {}
        module_data = self.artifact.get("modules", {}).get(module_name, {})
        root_scope_uid = module_data.get("root_scope_uid")
        if not root_scope_uid:
            return {}
        scopes = self.artifact.get("pools", {}).get("scopes", {})
        scope_symbols = scopes.get(root_scope_uid, {}).get("symbols", {})
        return dict(scope_symbols) if isinstance(scope_symbols, dict) else {}

    def import_from(self, module_name: str, names: List[tuple], execution_context: IExecutionContext) -> None:
        """
        处理 from module_name import names...
        names: List[Tuple[name, asname, uid]]
        """
        context = execution_context.runtime_context
        # 1. 优先从 InterOp 注册包中查找
        package = self.interop.get_package(module_name)
        if package:
            # Check if any alias is '*'
            if any(name == '*' for name, _, _ in names):
                # 从编译器注入符号表取 uid（name -> sym_uid），与运行时实际存在的
                # 公开属性取交集——既保证 uid 对齐，又只导出 spec 声明成员（不泄漏协议方法）
                uid_map = self._import_star_uid_map(execution_context)
                for attr_name in dir(package):
                    if attr_name.startswith('_'):
                        continue
                    if attr_name not in uid_map:
                        # 仅注入编译器声明为 import-* 成员的符号（spec 契约成员）
                        continue
                    try:
                        attr_val = getattr(package, attr_name)
                    except AttributeError:
                        # spec 声明成员但实现缺失 = 契约违例，显式暴露（与非星号路径一致）
                        raise InterpreterError(
                            f"Cannot import name '{attr_name}' from module '{module_name}'"
                        )
                    context.define_variable(attr_name, attr_val, uid=uid_map.get(attr_name))
            else:
                for name, asname, uid in names:
                    try:
                        attr_val = getattr(package, name)
                    except AttributeError:
                        raise InterpreterError(f"Cannot import name '{name}' from module '{module_name}'")
                    target_name = asname or name
                    context.define_variable(target_name, attr_val, uid=uid)
            return

        # 2. 处理 IBC 文件模块的 import from 逻辑
        try:
            if module_name not in self._loaded_modules:
                self.import_module(module_name, execution_context)
            
            module_instance = self._loaded_modules.get(module_name)
            if module_instance:
                if any(name == '*' for name, _, _ in names):
                    # 使用接口公开方法获取符号；uid 从导入文件编译器注入表取（保证 uid 对齐）
                    uid_map = self._import_star_uid_map(execution_context)
                    symbols = module_instance.scope.get_all_symbols()
                    for sym_name, sym in symbols.items():
                        if sym.is_const:  # 排除 print, int 等内置符号
                            continue
                        if sym_name not in uid_map:
                            continue
                        context.define_variable(sym_name, sym.value, declared_type=sym.declared_type, uid=uid_map.get(sym_name))
                else:
                    for name, asname, uid in names:
                        try:
                            val = module_instance.get_variable(name)
                            symbol = module_instance.scope.get_symbol(name)
                            target_name = asname or name
                            context.define_variable(target_name, val, declared_type=symbol.declared_type if symbol else None, uid=uid)
                        except (InterpreterError, KeyError):
                            raise InterpreterError(f"Cannot import name '{name}' from module '{module_name}'")
                return

        except Exception as e:
            if isinstance(e, InterpreterError):
                raise
            raise InterpreterError(f"Module '{module_name}' not found or not registered.") from e
