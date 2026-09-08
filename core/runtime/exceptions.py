from typing import Any


class StageTransitionError(Exception):
    """违反注册生命周期顺序或访问未就绪阶段"""
    pass

class RegistryIsolationError(Exception):
    """检测到跨引擎的非法插件对象渗透"""
    pass

class ThrownException(Exception):
    """包装用户代码主动抛出的 IbObject 异常"""
    def __init__(self, value: Any):
        self.value = value

    def __str__(self) -> str:
        # 抛出错误值的显示面 = ``TypeName: message``（Python 异常显示对等；
        # 类型名 + message 字段双保真）——避免裸对象 repr 跨 VM 边界
        # （子线程透传/嵌套包装场景错误文本保真）。
        from core.runtime.objects.kernel.base import IbObject
        value = self.value
        if isinstance(value, IbObject):
            type_name = value.ib_class.name
            raw = value.fields.get("message")
            if raw is not None:
                # 装箱值经 to_native 解箱（IbObject 标准协议面）
                if isinstance(raw, IbObject):
                    raw = raw.to_native()
                if isinstance(raw, str) and raw:
                    return f"{type_name}: {raw}" if type_name else raw
        return Exception.__str__(self) or repr(value)
