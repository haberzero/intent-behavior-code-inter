# calculator.py

def add_numbers(a: int, b: int):
    """一个简单的加法插件函数"""
    return a + b

def multiply_numbers(a: int, b: int):
    """一个简单的乘法插件函数"""
    return a * b

class PluginMetadata:
    def __init__(self):
        self.version = "1.0.0"
        self.author = "IBCI-Inter"

# 钩子函数 (可选)
def setup(engine):
    # 手动注册到不同的名称
    engine.register_plugin("calc", {"add": add_numbers, "mul": multiply_numbers})
    # 同时注册一个静态属性
    engine.register_plugin("plugin_info", PluginMetadata())
    print("Calculator plugin hooked via setup()")
