import os
from typing import List, Dict, Any, Optional, Callable, TYPE_CHECKING
from .interfaces import ModuleManager, RuntimeContext, InterOp, ModuleInstance, Scope
from typedef.exception_types import InterpreterError

if TYPE_CHECKING:
    from .interfaces import Interpreter

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
    def __init__(self, interop: InterOp, scheduler: Optional[Any] = None, root_dir: str = ".", interpreter_factory: Optional[Callable[[], 'Interpreter']] = None):
        self.interop = interop
        self.scheduler = scheduler
        self.root_dir = root_dir
        self.interpreter_factory = interpreter_factory
        self._loaded_modules: Dict[str, ModuleInstance] = {}

    def import_module(self, module_name: str, context: RuntimeContext) -> None:
        """
        处理 import module_name
        优先从 InterOp 注册包中加载。
        其次尝试从已编译的 IBC 模块中加载。
        """
        # 1. 优先从 InterOp 注册包中查找 (Python 扩展/标准库)
        package = self.interop.get_package(module_name)
        if package:
            context.define_variable(module_name, package, is_const=True)
            return

        # 2. 检查是否已经加载过该模块
        if module_name in self._loaded_modules:
            context.define_variable(module_name, self._loaded_modules[module_name], is_const=True)
            return

        # 3. 联动 Scheduler 处理文件系统中的 IBC 模块导入
        if self.scheduler:
            ast_module = self.scheduler.get_module_ast(module_name)
            if ast_module:
                if not self.interpreter_factory:
                    raise InterpreterError("Interpreter factory not provided for module loading.")
                
                # 创建新的解释器实例以执行被导入模块
                sub_interpreter = self.interpreter_factory()
                sub_interpreter.interpret(ast_module)
                
                # 获取该模块的全局作用域作为 Namespace
                module_instance = ModuleInstanceImpl(module_name, sub_interpreter.context.global_scope)
                self._loaded_modules[module_name] = module_instance
                
                context.define_variable(module_name, module_instance, is_const=True)
                return

        raise InterpreterError(f"Module '{module_name}' not found or not registered.")

    def import_from(self, module_name: str, names: List[str], context: RuntimeContext) -> None:
        """
        处理 from module_name import x, y 或 from module_name import *
        """
        # 1. 优先从 InterOp 注册包中查找
        package = self.interop.get_package(module_name)
        if package:
            if '*' in names:
                # 导入所有非私有属性
                for attr_name in dir(package):
                    if not attr_name.startswith('_'):
                        try:
                            attr_val = getattr(package, attr_name)
                            context.define_variable(attr_name, attr_val)
                        except AttributeError: pass
            else:
                for name in names:
                    try:
                        attr_val = getattr(package, name)
                        context.define_variable(name, attr_val)
                    except AttributeError:
                        raise InterpreterError(f"Cannot import name '{name}' from module '{module_name}'")
            return

        # 2. 处理 IBC 文件模块的 import from 逻辑
        if self.scheduler:
            # 确保模块已加载
            if module_name not in self._loaded_modules:
                self.import_module(module_name, context)
            
            module_instance = self._loaded_modules.get(module_name)
            if module_instance:
                if '*' in names:
                    # 使用接口公开方法获取符号
                    symbols = module_instance.scope.get_all_symbols()
                    for sym_name, sym in symbols.items():
                        if not sym.is_const: # 排除 print, int 等内置符号
                            context.define_variable(sym_name, sym.value, declared_type=sym.declared_type)
                else:
                    for name in names:
                        try:
                            val = module_instance.get_variable(name)
                            symbol = module_instance.scope.get_symbol(name)
                            context.define_variable(name, val, declared_type=symbol.declared_type if symbol else None)
                        except (InterpreterError, KeyError):
                            raise InterpreterError(f"Cannot import name '{name}' from module '{module_name}'")
                return

        raise InterpreterError(f"Module '{module_name}' not found or not registered.")
