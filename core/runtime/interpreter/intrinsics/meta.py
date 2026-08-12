from typing import Any
from core.runtime.objects.kernel import IbObject

def register_meta(manager: Any, execution_context: Any, service_context: Any):
    """注册元编程/内核信息相关内置函数"""
    
    def get_self_source() -> str:
        """获取当前模块的源代码"""

        # 核心：通过 service_context 和 execution_context 获取信息，严禁穿透持有 interpreter
        ctx = service_context
        
        if ctx.host_service:
            return ctx.host_service.get_source()
        return ""

    def _type(obj: IbObject) -> IbObject:
        """全局 type() 函数：返回值的规范类型名字符串。

        对齐 Python type() 语义的运行时内省：返回对象运行时类型的规范名
        （int/str/list/用户类名等）。fn_callable/behavior 返回含签名的形态
        （如 ``fn_callable[()->int]``、``behavior[(int,str)->bool]``）。供调试、
        泛型分发、类型比较使用。
        """
        if isinstance(obj, IbObject):
            name = obj.ib_class.name
            if name in ("fn_callable", "behavior"):
                return manager.registry.box(obj.signature_name())
            return manager.registry.box(name)
        return manager.registry.box(type(obj).__name__)

    manager.register("get_self_source", get_self_source, unbox=True)
    manager.register("type", _type, unbox=False)
