"""
ibci_schema/core.py

IBCI Schema 数据校验插件实现。非侵入层插件，零内核依赖。

功能：
- validate：校验 dict 是否符合 schema 规则
- assert_schema：校验失败则抛出 RuntimeError
- required_fields：提取 schema 的 required 字段列表
- infer：从 dict 数据推断简单 schema
- coerce：按 schema 对 dict 值进行类型强制转换
"""
from typing import Dict, Any, List, Optional


# Python 类型名到 ibci/schema 类型名的映射
_TYPE_MAP = {
    "string": str,
    "str": str,
    "number": (int, float),
    "float": float,
    "integer": int,
    "int": int,
    "boolean": bool,
    "bool": bool,
    "array": list,
    "list": list,
    "object": dict,
    "dict": dict,
}

# 类型强制转换器
_COERCE_MAP = {
    "string":  str,
    "str":     str,
    "integer": int,
    "int":     int,
    "float":   float,
    "number":  float,
    "boolean": bool,
    "bool":    bool,
}


class SchemaLib:
    """JSON Schema 风格的轻量数据校验与推断工具。"""

    def validate(self, data: Dict[str, Any], rules: Dict[str, Any]) -> bool:
        """
        校验 data 是否符合 rules，返回 bool。

        rules 格式（JSON Schema 子集）：
        {
            "required": ["field1", "field2"],          # 必填字段
            "properties": {
                "field1": {"type": "string"},          # 类型校验
                "field2": {"type": "integer", "min": 0, "max": 100},
                "tags":   {"type": "array",
                           "item_type": "string"},     # 数组元素类型
                "nested": {"type": "object",
                           "properties": {...}}        # 嵌套 schema
            }
        }
        """
        if not isinstance(data, dict):
            return False

        # 必填字段检查
        for field in rules.get("required", []):
            if field not in data:
                return False

        # 属性约束检查
        for field, rule in rules.get("properties", {}).items():
            if field not in data:
                continue
            val = data[field]
            if not self._check_field(val, rule):
                return False

        return True

    def _check_field(self, val: Any, rule: Dict[str, Any]) -> bool:
        """递归检查单个字段。"""
        type_name = rule.get("type")
        if type_name:
            py_type = _TYPE_MAP.get(type_name)
            if py_type and not isinstance(val, py_type):
                return False

        # 数值范围
        if "min" in rule and isinstance(val, (int, float)):
            if val < rule["min"]:
                return False
        if "max" in rule and isinstance(val, (int, float)):
            if val > rule["max"]:
                return False

        # 字符串长度
        if "min_length" in rule and isinstance(val, str):
            if len(val) < rule["min_length"]:
                return False
        if "max_length" in rule and isinstance(val, str):
            if len(val) > rule["max_length"]:
                return False

        # 枚举值
        if "enum" in rule:
            if val not in rule["enum"]:
                return False

        # 数组元素类型
        if type_name in ("array", "list") and "item_type" in rule and isinstance(val, list):
            item_py_type = _TYPE_MAP.get(rule["item_type"])
            if item_py_type:
                for item in val:
                    if not isinstance(item, item_py_type):
                        return False

        # 嵌套 object schema
        if type_name in ("object", "dict") and "properties" in rule and isinstance(val, dict):
            if not self.validate(val, rule):
                return False

        return True

    def assert_schema(self, data: Dict[str, Any], rules: Dict[str, Any]) -> None:
        """校验失败则抛出 RuntimeError，成功则静默返回。"""
        if not self.validate(data, rules):
            raise RuntimeError(f"Schema validation failed. Data keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}")

    def required_fields(self, rules: Dict[str, Any]) -> List[str]:
        """从 schema rules 中提取 required 字段列表。"""
        return list(rules.get("required", []))

    def infer(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        从 dict 数据推断简单 schema（仅支持一层，不递归）。

        返回格式：
        {
            "required": [...],
            "properties": {"field": {"type": "string"}, ...}
        }
        """
        props: Dict[str, Any] = {}
        for key, val in data.items():
            if isinstance(val, bool):
                props[key] = {"type": "boolean"}
            elif isinstance(val, int):
                props[key] = {"type": "integer"}
            elif isinstance(val, float):
                props[key] = {"type": "number"}
            elif isinstance(val, str):
                props[key] = {"type": "string"}
            elif isinstance(val, list):
                props[key] = {"type": "array"}
            elif isinstance(val, dict):
                props[key] = {"type": "object"}
            else:
                props[key] = {"type": "any"}
        return {
            "required": list(data.keys()),
            "properties": props,
        }

    def coerce(self, data: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
        """
        按 schema properties 中声明的 type 对 data 值进行类型强制转换。
        转换失败的字段保留原值。返回新 dict，不修改原 data。
        """
        result = dict(data)
        for field, rule in rules.get("properties", {}).items():
            if field not in result:
                continue
            type_name = rule.get("type")
            converter = _COERCE_MAP.get(type_name)
            if converter:
                try:
                    result[field] = converter(result[field])
                except (ValueError, TypeError):
                    pass  # 转换失败保留原值
        return result


def create_implementation() -> SchemaLib:
    return SchemaLib()
