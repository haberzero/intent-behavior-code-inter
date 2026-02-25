import json
import math
import time
import os
from typing import Any
from utils.host_interface import HostInterface
from utils.semantic.types import FunctionType, ModuleType, STR_TYPE, ANY_TYPE, VOID_TYPE, FLOAT_TYPE, BOOL_TYPE, INT_TYPE
from typedef.scope_types import ScopeNode, ScopeType
from typedef.symbol_types import SymbolType

def get_stdlib_metadata() -> HostInterface:
    """
    创建并返回一个包含所有标准库元数据和实现的 HostInterface。
    """
    host = HostInterface()

    # 1. json 模块
    class JSONLib:
        @staticmethod
        def parse(s: str): return json.loads(s)
        @staticmethod
        def stringify(obj: Any): return json.dumps(obj, ensure_ascii=False)
    
    json_scope = ScopeNode(ScopeType.GLOBAL)
    json_scope.define("parse", SymbolType.FUNCTION).type_info = FunctionType([STR_TYPE], ANY_TYPE)
    json_scope.define("stringify", SymbolType.FUNCTION).type_info = FunctionType([ANY_TYPE], STR_TYPE)
    host.register_module("json", JSONLib, ModuleType(json_scope))

    # 2. math 模块
    math_scope = ScopeNode(ScopeType.GLOBAL)
    math_scope.define("sqrt", SymbolType.FUNCTION).type_info = FunctionType([FLOAT_TYPE], FLOAT_TYPE)
    math_scope.define("pi", SymbolType.VARIABLE).type_info = FLOAT_TYPE
    math_scope.define("pow", SymbolType.FUNCTION).type_info = FunctionType([FLOAT_TYPE, FLOAT_TYPE], FLOAT_TYPE)
    math_scope.define("sin", SymbolType.FUNCTION).type_info = FunctionType([FLOAT_TYPE], FLOAT_TYPE)
    math_scope.define("cos", SymbolType.FUNCTION).type_info = FunctionType([FLOAT_TYPE], FLOAT_TYPE)
    host.register_module("math", math, ModuleType(math_scope))

    # 3. time 模块
    class TimeLib:
        @staticmethod
        def sleep(seconds: float): time.sleep(seconds)
        @staticmethod
        def now() -> float: return time.time()
    
    time_scope = ScopeNode(ScopeType.GLOBAL)
    time_scope.define("now", SymbolType.FUNCTION).type_info = FunctionType([], FLOAT_TYPE)
    time_scope.define("sleep", SymbolType.FUNCTION).type_info = FunctionType([FLOAT_TYPE], VOID_TYPE)
    host.register_module("time", TimeLib, ModuleType(time_scope))

    # 4. file 模块 (实现由 Engine 在运行时通过闭包或注入完成，这里先放元数据)
    # 注意：file 模块需要访问 PermissionManager，所以它的实现通常在 register_stdlib 中处理
    # 为了保持架构整洁，我们可以在这里定义元数据，实现留空，由 Engine 后续覆盖。
    file_scope = ScopeNode(ScopeType.GLOBAL)
    file_scope.define("read", SymbolType.FUNCTION).type_info = FunctionType([STR_TYPE], STR_TYPE)
    file_scope.define("write", SymbolType.FUNCTION).type_info = FunctionType([STR_TYPE, STR_TYPE], VOID_TYPE)
    file_scope.define("exists", SymbolType.FUNCTION).type_info = FunctionType([STR_TYPE], BOOL_TYPE)
    host.register_module("file", None, ModuleType(file_scope))

    # 5. sys 模块
    sys_scope = ScopeNode(ScopeType.GLOBAL)
    sys_scope.define("request_external_access", SymbolType.FUNCTION).type_info = FunctionType([], VOID_TYPE)
    sys_scope.define("is_sandboxed", SymbolType.FUNCTION).type_info = FunctionType([], BOOL_TYPE)
    host.register_module("sys", None, ModuleType(sys_scope))

    # 6. ai 模块
    ai_scope = ScopeNode(ScopeType.GLOBAL)
    ai_scope.define("set_config", SymbolType.FUNCTION).type_info = FunctionType([STR_TYPE, STR_TYPE, STR_TYPE], VOID_TYPE)
    ai_scope.define("set_retry_hint", SymbolType.FUNCTION).type_info = FunctionType([STR_TYPE], VOID_TYPE)
    ai_scope.define("set_retry", SymbolType.FUNCTION).type_info = FunctionType([INT_TYPE], VOID_TYPE)
    ai_scope.define("set_timeout", SymbolType.FUNCTION).type_info = FunctionType([FLOAT_TYPE], VOID_TYPE)
    host.register_module("ai", None, ModuleType(ai_scope))

    return host
