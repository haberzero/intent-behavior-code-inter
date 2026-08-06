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
                native_obj = self.object_factory.create_native_object(
                    package, self.registry.get_class("Object"),
                    vtable=vtable, whitelist=whitelist,
                    registry_id=self.interop.get_registry_id(module_name),
                )
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

    def _module_scope_uids(self, execution_context: IExecutionContext) -> Dict[str, str]:
        """读取当前模块根作用域的整张符号表（name -> sym_uid）。

        注意：该表含 prelude/内建 + 用户符号 + import-* 注入符号的**全部**模块级
        符号，不是 import-* 成员的专属映射。本方法只用于
        按名查询 import-* 成员的 uid（保证运行时绑定与使用点 get_variable_by_uid
        对齐）；"哪些名字是 import-* 成员"由 ``_import_star_members`` 精确提供。
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

    def _import_star_members(self, execution_context: IExecutionContext, module_name: str) -> List[str]:
        """读取编译器精确记录的 import-* 注入成员名（导入模块名 → 成员名列表）。

        精确契约集合只在编译期存在（scheduler 注入时已知 s_mod_type.members），
        序列化进当前模块 artifact 的 ``import_star_members``。运行时据此枚举，
        替代"读整张模块根作用域表 + dir(package) 交集"的粗糙代理——后者无法
        感知"spec 声明但实现缺失"的契约违例（import-* 与具名导入行为不对称）。
        """
        if not self.artifact:
            return []
        current_module = execution_context.current_module_name
        if not current_module:
            return []
        module_data = self.artifact.get("modules", {}).get(current_module, {})
        members_map = module_data.get("import_star_members", {})
        if not isinstance(members_map, dict):
            return []
        return list(members_map.get(module_name, []))

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
                # 精确枚举编译器记录的 import-* 成员（不再 dir(package) ∩ 整张模块表）：
                # spec 声明但实现缺失 = 契约违例，显式暴露（与具名导入一致）；
                # uid 按名从当前模块根作用域表查询，保证与使用点 get_variable_by_uid 对齐。
                uid_map = self._module_scope_uids(execution_context)
                for member_name in self._import_star_members(execution_context, module_name):
                    if member_name.startswith('_'):
                        continue
                    try:
                        attr_val = getattr(package, member_name)
                    except AttributeError:
                        raise InterpreterError(
                            f"Cannot import name '{member_name}' from module '{module_name}'"
                        )
                    context.define_variable(member_name, attr_val, uid=uid_map.get(member_name))
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
        if module_name not in self._loaded_modules:
            self.import_module(module_name, execution_context)

        module_instance = self._loaded_modules.get(module_name)
        if module_instance:
            if any(name == '*' for name, _, _ in names):
                # 与包分支同构：精确枚举编译器记录的 import-* 成员，按名取符号绑定。
                # 运行时符号缺失（编译注入但运行未定义）= 不一致，显式报错。
                uid_map = self._module_scope_uids(execution_context)
                for member_name in self._import_star_members(execution_context, module_name):
                    symbol = module_instance.scope.get_symbol(member_name)
                    if symbol is None:
                        raise InterpreterError(
                            f"Cannot import name '{member_name}' from module '{module_name}'"
                        )
                    context.define_variable(
                        member_name, symbol.value,
                        declared_type=symbol.declared_type,
                        uid=uid_map.get(member_name),
                    )
            else:
                for name, asname, uid in names:
                    try:
                        val = module_instance.scope.get(name)
                        symbol = module_instance.scope.get_symbol(name)
                        target_name = asname or name
                        context.define_variable(target_name, val, declared_type=symbol.declared_type if symbol else None, uid=uid)
                    except (InterpreterError, KeyError):
                        raise InterpreterError(f"Cannot import name '{name}' from module '{module_name}'")
            return
