from .core import AIPlugin

# [IES 2.0] 强制使用工厂模式以支持多引擎隔离
def create_implementation():
    return AIPlugin()
