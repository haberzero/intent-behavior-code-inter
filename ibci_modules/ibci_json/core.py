"""
ibci_json/core.py

JSON 序列化/操作内核实现（模块级函数形态）。零内核依赖。

契约（成员面 + 签名）单一权威源 = 内核契约源（contracts/json.ibci，bind 表达）；
本模块 = 实现面。

功能：
- parse/stringify：基础序列化往返
- merge：合并两个 dict
- get_nested/set_nested：点分路径深层访问（"a.b.c"）
- keys/values：提取 dict 的键/值列表
- pretty：美化输出
- __to_prompt__：模块参与 __prompt__ 协议，描述自身
"""
import copy as _copy
import json as _json
from typing import Any, Dict, List, Optional

from core.base.diagnostics.codes import RUN_JSON_PARSE_ERROR

__all__ = [
    "parse", "parse_or_none", "stringify", "pretty",
    "merge", "keys", "values", "get_nested", "set_nested",
    "__to_prompt__",
]


class JsonParseError(Exception):
    """JSON 解析/序列化失败（fail-fast）。

    ``code`` 属性 = 失败语义单点权威源（VM 边界显式码透传机制——
    经 ``_runtime_error_code_for`` 原码透传，替代裸 RUN_GENERIC_ERROR）。
    """

    code = RUN_JSON_PARSE_ERROR

    def __init__(self, message: str):
        super().__init__(message)


def parse(s: str) -> Any:
    """解析 JSON 字符串，返回实际值（dict / list / 标量）。

    malformed JSON = JsonParseError（fail-fast；经 try/except 捕获）。
    """
    try:
        return _json.loads(s)
    except _json.JSONDecodeError as e:
        raise JsonParseError(f"JSON parse failed: {e}") from e


def parse_or_none(s: str) -> Optional[Any]:
    """显式宽松形态：malformed = None（无副作用——不 print、不抛）。

    与 parse（fail-fast 抛错）互补：调用方按数据形态显式选择失败面
    （None 判定 vs 异常捕获），非默认回退。
    """
    try:
        return _json.loads(s)
    except _json.JSONDecodeError:
        return None


def stringify(obj: Any) -> str:
    """将任意值序列化为 JSON 字符串（无缩进）。

    不可序列化值（如循环引用）= JsonParseError（fail-fast）。
    """
    try:
        return _json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError) as e:
        raise JsonParseError(f"JSON stringify failed: {e}") from e


def pretty(obj: Any) -> str:
    """将任意值序列化为美化（4 空格缩进）的 JSON 字符串。

    不可序列化值 = JsonParseError（fail-fast）。
    """
    try:
        return _json.dumps(obj, ensure_ascii=False, indent=4, default=str)
    except (TypeError, ValueError) as e:
        raise JsonParseError(f"JSON pretty failed: {e}") from e


def merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """浅层合并两个 dict，b 的键覆盖 a 的同名键。返回新 dict。"""
    result = dict(a)
    result.update(b)
    return result


def keys(obj: Dict[str, Any]) -> List[str]:
    """返回 dict 的所有键列表。"""
    return list(obj.keys())


def values(obj: Dict[str, Any]) -> List[Any]:
    """返回 dict 的所有值列表。"""
    return list(obj.values())


def get_nested(obj: Dict[str, Any], path: str) -> Any:
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


def set_nested(obj: Dict[str, Any], path: str, value: Any) -> Dict[str, Any]:
    """
    按点分路径写入嵌套值，返回修改后的新 dict（不修改原 obj）。
    路径中途的节点若不存在则自动创建为 dict。
    """
    result = _copy.deepcopy(obj)
    parts = path.split(".")
    current = result
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value
    return result


def __to_prompt__() -> str:
    """
    json 模块的 __prompt__ 表示。
    当 json 模块对象作为意图注入内容时，返回此描述字符串。
    """
    return "[JSON module: provides parse/parse_or_none/stringify/merge/get_nested/set_nested/keys/values/pretty]"
