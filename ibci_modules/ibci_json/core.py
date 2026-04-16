"""
ibci_json/core.py

IBCI JSON 插件实现。非侵入层插件，零内核依赖。
"""
import json
from typing import Any, Dict


class JSONLib:
    """
    JSON 序列化/反序列化工具。

    parse  始终返回 dict：
      - JSON 对象 → dict（直接返回）
      - JSON 数组 → {"_list": [...]}
      - JSON 字符串/数字/bool → {"_str": ...} / {"_value": ...}
      - 解析失败 → {}
    stringify  将任意值序列化为 JSON 字符串。
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


def create_implementation() -> JSONLib:
    return JSONLib()
