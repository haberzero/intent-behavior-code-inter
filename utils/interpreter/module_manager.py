import os
from typing import List, Dict, Any, Optional
from .interfaces import ModuleManager, RuntimeContext, InterOp
from typedef.exception_types import InterpreterError

class ModuleManagerImpl:
    def __init__(self, interop: InterOp, scheduler: Optional[Any] = None, root_dir: str = "."):
        self.interop = interop
        self.scheduler = scheduler
        self.root_dir = root_dir
        self._loaded_modules: Dict[str, Any] = {}

    def import_module(self, module_name: str, context: RuntimeContext) -> None:
        """
        处理 import module_name
        优先从 InterOp 注册包中加载（命名空间隔离的第三方/第一方库）。
        其次尝试从已编译的 IBC 模块中加载。
        """
        # 1. 优先从 InterOp 注册包中查找 (Python 扩展/标准库)
        package = self.interop.get_package(module_name)
        if package:
            context.define_variable(module_name, package, is_const=True)
            return

        # 2. 联动 Scheduler 处理文件系统中的 IBC 模块导入
        if self.scheduler:
            ast_module = self.scheduler.get_module_ast(module_name)
            if ast_module:
                # 在 IBC 模块导入中，我们需要执行该模块并将它的顶级作用域作为一个 Namespace 对象暴露
                # 暂时简化处理：直接执行模块内容（由于 Scheduler 已经编译并做了语义分析，这里通常只需执行）
                # 这里我们假设模块已经被执行过，或者我们需要在这里创建一个临时的 Namespace
                
                # 为了原型机稳定性，我们暂时将模块的所有顶级定义导入到一个 Namespace 对象中
                # 这个 Namespace 对象可以用一个 Dict 或者一个简单的类实例来模拟
                namespace = type('Namespace', (), {})()
                
                # 从 Scheduler 的 scope_cache 中获取该模块的符号
                module_scope = self.scheduler.scope_cache.get(module_name)
                if module_scope:
                    # 遍历作用域中的所有符号，并将其绑定到 namespace 对象上
                    # 注意：这里需要获取符号的值，可能需要通过一个临时的 Interpreter 来运行该模块
                    # 或者从全局符号表中获取（如果 IBC 模块是全局单例的）
                    pass
                
                # 为简单起见，目前 IBC 跨文件导入仅支持符号声明的可见性，不涉及复杂的运行时状态隔离
                context.define_variable(module_name, ast_module, is_const=True)
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

        # 2. TODO: 处理 IBC 文件模块的 import from 逻辑
        raise InterpreterError(f"Module '{module_name}' not found or not registered.")
