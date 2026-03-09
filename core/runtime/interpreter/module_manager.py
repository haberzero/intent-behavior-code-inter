from core.runtime.interfaces import ModuleManager, RuntimeContext, InterOp, ModuleInstance, Scope
import os
from typing import List, Dict, Any, Optional, Callable, Tuple, TYPE_CHECKING
from core.domain import ast as ast
from core.domain.types.descriptors import ModuleMetadata as ModuleType
from core.domain.issue import InterpreterError
from core.foundation.diagnostics.codes import DEP_MODULE_NOT_FOUND

if TYPE_CHECKING:
    from core.runtime.interfaces import Interpreter
    from core.domain.blueprint import CompilationArtifact

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
    def __init__(self, interop: InterOp, artifact: Optional['CompilationArtifact'] = None, root_dir: str = ".", interpreter: Optional['Interpreter'] = None):
        self.interop = interop
        self.artifact = artifact
        self.root_dir = root_dir
        self.interpreter = interpreter  # 现在持有主 Interpreter 引用，而非 factory
        self._loaded_modules: Dict[str, ModuleInstance] = {}

    def set_interpreter(self, interpreter: 'Interpreter'):
        """允许延迟注入 Interpreter"""
        self.interpreter = interpreter

    def import_module(self, module_name: str, context: RuntimeContext) -> Any:
        """
        处理 import module_name，返回模块实例
        """
        # 1. 优先从 InterOp 注册包中查找 (Python 扩展/标准库)
        package = self.interop.get_package(module_name)
        if package:
            # [IES 2.0 FIX] 确保 Python 插件实现被正确包装为 IbNativeObject 以支持消息传递
            from core.runtime.objects.kernel import IbObject, IbNativeObject
            if not isinstance(package, IbObject):
                return IbNativeObject(package, self.interpreter.registry.get_class("Object"))
            return package

        # 2. 检查是否已经加载过该模块
        if module_name in self._loaded_modules:
            return self._loaded_modules[module_name]

        # 3. 联动 Artifact (编译蓝图) 处理模块导入
        if self.artifact:
            module_data = self.artifact.get("modules", {}).get(module_name)
            if module_data:
                root_node_uid = module_data.get("root_node_uid")
                if not self.interpreter:
                    raise InterpreterError("Interpreter not available for module loading.")
                
                # 创建该模块的 Global Scope
                from .runtime_context import ScopeImpl
                module_scope = ScopeImpl(registry=self.interpreter.registry)
                
                # [FIX] 预先创建并缓存模块实例，以支持循环引用 (a -> b -> a)
                from core.runtime.objects.kernel import IbModule
                module_instance = IbModule(module_name, module_scope, registry=self.interpreter.registry)
                self._loaded_modules[module_name] = module_instance
                
                # 在新 Scope 下复用 Interpreter 执行
                try:
                    self.interpreter.execute_module(root_node_uid, module_name=module_name, scope=module_scope)
                except Exception:
                    # 如果执行失败，清除缓存以允许后续重试（或防止污染）
                    if module_name in self._loaded_modules:
                        del self._loaded_modules[module_name]
                    raise
                
                return module_instance

        raise InterpreterError(f"Module '{module_name}' not found or not registered in artifact.", error_code=DEP_MODULE_NOT_FOUND)

    def import_from(self, module_name: str, names: List[tuple], context: RuntimeContext) -> None:
        """
        处理 from module_name import x as y, z 或 from module_name import *
        names 为 (name, asname) 的元组列表
        """
        # 1. 优先从 InterOp 注册包中查找
        package = self.interop.get_package(module_name)
        if package:
            # Check if any alias is '*'
            if any(name == '*' for name, _ in names):
                # 导入所有非私有属性
                for attr_name in dir(package):
                    if not attr_name.startswith('_'):
                        try:
                            attr_val = getattr(package, attr_name)
                            context.define_variable(attr_name, attr_val)
                        except AttributeError: pass
            else:
                for name, asname in names:
                    try:
                        attr_val = getattr(package, name)
                        target_name = asname or name
                        context.define_variable(target_name, attr_val)
                    except AttributeError:
                        raise InterpreterError(f"Cannot import name '{name}' from module '{module_name}'")
            return

        # 2. 处理 IBC 文件模块的 import from 逻辑
        if self.artifact:
            # 确保模块已加载
            if module_name not in self._loaded_modules:
                self.import_module(module_name, context)
            
            module_instance = self._loaded_modules.get(module_name)
            if module_instance:
                if any(name == '*' for name, _ in names):
                    # 使用接口公开方法获取符号
                    symbols = module_instance.scope.get_all_symbols()
                    for sym_name, sym in symbols.items():
                        if not sym.is_const: # 排除 print, int 等内置符号
                            context.define_variable(sym_name, sym.value, declared_type=sym.declared_type)
                else:
                    for name, asname in names:
                        try:
                            val = module_instance.get_variable(name)
                            symbol = module_instance.scope.get_symbol(name)
                            target_name = asname or name
                            context.define_variable(target_name, val, declared_type=symbol.declared_type if symbol else None)
                        except (InterpreterError, KeyError):
                            raise InterpreterError(f"Cannot import name '{name}' from module '{module_name}'")
                return

        raise InterpreterError(f"Module '{module_name}' not found or not registered.")
