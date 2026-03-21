"""
[IES 2.2] Schema JSON Schema 校验插件

纯 Python 实现，零侵入。
"""
from typing import Dict, Any


class SchemaLib:
    """
    [IES 2.2] Schema 2.2: JSON Schema 校验插件。
    不继承任何核心类，完全独立。
    """
    def validate(self, data: Dict[str, Any], rules: Dict[str, Any]) -> bool:
        if not isinstance(data, dict):
            return False

        required = rules.get("required", [])
        for field in required:
            if field not in data:
                return False

        properties = rules.get("properties", {})
        for field, rule in properties.items():
            if field in data:
                val = data[field]
                expected_type = rule.get("type")
                if expected_type == "string" and not isinstance(val, str): return False
                if expected_type == "number" and not isinstance(val, (int, float)): return False
                if expected_type == "integer" and not isinstance(val, int): return False
                if expected_type == "boolean" and not isinstance(val, bool): return False
                if expected_type == "array" and not isinstance(val, list): return False
                if expected_type == "object" and not isinstance(val, dict): return False

        return True

    def _assert(self, data: Dict[str, Any], rules: Dict[str, Any]):
        if not self.validate(data, rules):
            raise RuntimeError(f"Schema validation failed. Data: {data}, Rules: {rules}")


def create_implementation():
    return SchemaLib()
