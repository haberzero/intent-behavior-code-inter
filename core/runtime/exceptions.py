from typing import Any

class ReturnException(Exception):
    def __init__(self, value: Any):
        self.value = value

class BreakException(Exception):
    pass

class ContinueException(Exception):
    pass

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
