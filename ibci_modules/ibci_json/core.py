"""
ibci_json/core.py

IBCI JSON 序列化/操作插件实现。非侵入层插件，零内核依赖。

功能：
- parse/stringify：基础序列化往返
- merge：合并两个 dict
- get_nested/set_nested：点分路径深层访问（"a.b.c"）
- keys/values：提取 dict 的键/值列表
- pretty：美化输出
- __to_prompt__：模块参与 __prompt__ 协议，描述自身
"""
import json
from typing import Any, Dict, List, Optional


class JSONLib:
    """
    JSON 序列化/反序列化及结构操作工具。

    parse  始终返回 dict：
      - JSON 对象 → dict（直接返回）
      - JSON 数组 → {"_list": [...]}
      - JSON 原始值 → {"_value": ...}
      - 解析失败 → {}
    """

    # ------------------------------------------------------------------
    # 基础序列化
    # ------------------------------------------------------------------

    def parse(self, s: str) -> Dict[str, Any]:
        """将 JSON 字符串解析为 dict。数组/原始值用 _list/_value 包装。"""
        try:
            result = json.loads(s)
            if isinstance(result, dict):
                return result
            elif isinstance(result, list):
                return {"_list": result}
            else:
                return {"_value": result}
        except json.JSONDecodeError as e:
            print(f"[IBCI JSON Error] Parse failed: {e}")
            return {}

    def stringify(self, obj: Any) -> str:
        """将任意值序列化为 JSON 字符串（无缩进）。"""
        try:
            return json.dumps(obj, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as e:
            print(f"[IBCI JSON Error] Stringify failed: {e}")
            return "{}"

    def pretty(self, obj: Any) -> str:
        """将任意值序列化为美化（4 空格缩进）的 JSON 字符串。"""
        try:
            return json.dumps(obj, ensure_ascii=False, indent=4, default=str)
        except (TypeError, ValueError) as e:
            print(f"[IBCI JSON Error] Pretty failed: {e}")
            return "{}"

    # ------------------------------------------------------------------
    # 结构操作
    # ------------------------------------------------------------------

    def merge(self, a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
        """浅层合并两个 dict，b 的键覆盖 a 的同名键。返回新 dict。"""
        result = dict(a)
        result.update(b)
        return result

    def keys(self, obj: Dict[str, Any]) -> List[str]:
        """返回 dict 的所有键列表。"""
        return list(obj.keys())

    def values(self, obj: Dict[str, Any]) -> List[Any]:
        """返回 dict 的所有值列表。"""
        return list(obj.values())

    def get_nested(self, obj: Dict[str, Any], path: str) -> Any:
        """
        按点分路径读取嵌套值（如 'a.b.c'）。
        路径不存在时返回 None（ibci 中对应 null）。
        """
        parts = path.split(".")
        current: Any = obj
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def set_nested(self, obj: Dict[str, Any], path: str, value: Any) -> Dict[str, Any]:
        """
        按点分路径写入嵌套值，返回修改后的新 dict（不修改原 obj）。
        路径中途的节点若不存在则自动创建为 dict。
        """
        import copy
        result = copy.deepcopy(obj)
        parts = path.split(".")
        current = result
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
        return result

    # ------------------------------------------------------------------
    # __prompt__ 协议：使 json 模块本身可以参与 LLM 意图系统
    # ------------------------------------------------------------------

    def __to_prompt__(self) -> str:
        """
        json 模块的 __prompt__ 表示。
        当 json 模块对象作为意图注入内容时，返回此描述字符串。
        """
        return "[JSON module: provides parse/stringify/merge/get_nested/set_nested/keys/values/pretty]"


def create_implementation() -> JSONLib:
    return JSONLib()
