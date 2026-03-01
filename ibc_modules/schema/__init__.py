from typing import Dict, Any, List

class SchemaLib:
    def validate(self, data: Dict[str, Any], rules: Dict[str, Any]) -> bool:
        """
        简单实现 JSON Schema 校验逻辑。
        支持: required, type
        """
        if not isinstance(data, dict):
            return False
            
        # 1. 校验必填项
        required = rules.get("required", [])
        for field in required:
            if field not in data:
                return False
                
        # 2. 校验类型 (简单映射)
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
            from core.types.exception_types import InterpreterError
            raise InterpreterError(f"Schema validation failed. Data: {data}, Rules: {rules}")

    def setup(self, capabilities):
        # schema 模块目前不需要特殊能力
        pass

def create_implementation():
    lib = SchemaLib()
    # 映射 'assert' 关键字 (Python 中是关键字，所以我们内部叫 _assert)
    setattr(lib, 'assert', lib._assert)
    return lib
