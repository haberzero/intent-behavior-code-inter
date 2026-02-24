import json
import math
import time
import os
from typing import Any
from ..interfaces import InterOp

def register_stdlib(interop: InterOp):
    """
    注册 ibc-inter 的第一方标准库组件。
    这些组件是利用 Python 原生能力实现的。
    """
    
    # 1. json 组件
    class JSONLib:
        @staticmethod
        def parse(s: str):
            return json.loads(s)
        
        @staticmethod
        def stringify(obj: Any):
            return json.dumps(obj, ensure_ascii=False)
            
    interop.register_package("json", JSONLib)

    # 2. math 组件
    # 直接注册 math 模块即可，InterOp 会处理映射
    interop.register_package("math", math)

    # 3. time 组件
    class TimeLib:
        @staticmethod
        def sleep(seconds: float):
            time.sleep(seconds)
            
        @staticmethod
        def now() -> float:
            return time.time()
            
    interop.register_package("time", TimeLib)

    # 4. file 组件 (基本的文件交互)
    class FileLib:
        @staticmethod
        def read(path: str) -> str:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
                
        @staticmethod
        def write(path: str, content: str):
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
                
        @staticmethod
        def exists(path: str) -> bool:
            return os.path.exists(path)

    interop.register_package("file", FileLib)
