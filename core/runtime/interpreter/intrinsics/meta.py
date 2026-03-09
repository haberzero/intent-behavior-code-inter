from typing import Any, List
from core.runtime.objects.kernel import IbObject
from core.runtime.interfaces import ServiceContext

def register_meta(manager: Any, interpreter: Any):
    """注册元编程相关的内置函数"""
    
    def get_self_source(*args) -> str:
        """获取当前模块的源代码"""
        ctx: ServiceContext = interpreter.service_context
        current_mod = interpreter.current_module_name
        if not current_mod:
            return ""
        
        # 通过 CompilerService 获取源码
        source = ctx.compiler.get_module_source(current_mod)
        return source or ""

    manager.register("get_self_source", get_self_source)
