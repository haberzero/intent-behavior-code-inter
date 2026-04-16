"""
ibci_schema/core.py

IBCI Schema 插件实现。非侵入层插件，零内核依赖。
"""
from typing import Dict, Any


class SchemaLib:
    """JSON Schema 风格的简单数据校验工具。"""

    def validate(self, data: Dict[str, Any], rules: Dict[str, Any]) -> bool:
        """校验数据是否符合规则，返回 bool。"""
        if not isinstance(data, dict):
            return False

        for field in rules.get("required", []):
            if field not in data:
                return False

        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        for field, rule in rules.get("properties", {}).items():
            if field in data:
                expected = rule.get("type")
                py_type = type_map.get(expected)
                if py_type and not isinstance(data[field], py_type):
                    return False

        return True

    def assert_schema(self, data: Dict[str, Any], rules: Dict[str, Any]) -> None:
        """校验失败则抛出 RuntimeError。"""
        if not self.validate(data, rules):
            raise RuntimeError(f"Schema validation failed. Data: {data}, Rules: {rules}")


def create_implementation() -> SchemaLib:
    return SchemaLib()
