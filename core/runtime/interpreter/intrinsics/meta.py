from typing import Any, List
from core.runtime.objects.kernel import IbObject
from core.runtime.interfaces import ServiceContext

def register_meta(manager: Any, execution_context: Any, service_context: Any):
    """注册元编程/内核信息相关内置函数"""
    
    def get_self_source() -> str:
        """获取当前模块的源代码"""
        # [IES 2.1 Decoupling]
        # 核心：通过 service_context 和 execution_context 获取信息，严禁穿透持有 interpreter
        ctx = service_context
        current_mod = execution_context.current_module_name
        
        if ctx.host_service:
            return ctx.host_service.get_source()
        return ""

    manager.register("get_self_source", get_self_source, unbox=True)
