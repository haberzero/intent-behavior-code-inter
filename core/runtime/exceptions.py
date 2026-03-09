from typing import Any

class ReturnException(Exception):
    def __init__(self, value: Any):
        self.value = value

class BreakException(Exception):
    pass

class ContinueException(Exception):
    pass

class RetryException(Exception):
    pass

class ThrownException(Exception):
    """包装用户代码主动抛出的 IbObject 异常"""
    def __init__(self, value: Any):
        self.value = value
