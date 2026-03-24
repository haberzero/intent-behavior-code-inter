"""
[IES 2.2] JSON 处理插件

纯 Python 实现，零侵入。
"""
import json
from typing import Any, Dict


class JSONLib:
    """
    [IES 2.2] JSON 2.2: JSON 处理插件。
    不继承任何核心类，完全独立。

    注意：parse 方法始终返回 dict 类型。
    - 如果解析成功且结果为 dict，直接返回
    - 如果解析成功但结果不是 dict，尝试转换为 dict 后返回
    - 如果解析失败（JSONDecodeError），报告错误并返回空字典 {}
    """
    def parse(self, s: str) -> Dict[str, Any]:
        try:
            result = json.loads(s)
            if isinstance(result, dict):
                return result
            elif isinstance(result, list):
                return {"_list": result}
            elif isinstance(result, str):
                return {"_str": result}
            elif isinstance(result, (int, float, bool)):
                return {"_value": result}
            else:
                return {}
        except json.JSONDecodeError as e:
            print(f"[IBCI JSON Error] Parse failed: {e}")
            return {}

    def stringify(self, obj: Any) -> str:
        try:
            return json.dumps(obj, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            print(f"[IBCI JSON Error] Stringify failed: {e}")
            return "{}"


def create_implementation():
    return JSONLib()
