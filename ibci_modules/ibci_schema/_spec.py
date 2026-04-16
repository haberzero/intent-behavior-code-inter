"""
Schema 数据校验插件规范

非侵入式 JSON Schema 风格数据校验插件。
支持类型校验、必填字段、数值范围、字符串长度、枚举、数组元素类型、嵌套 schema。
"""


def __ibcext_metadata__() -> dict:
    return {
        "name": "schema",
        "version": "2.0.0",
        "description": "IBCI 数据校验工具（JSON Schema 子集）",
        "dependencies": [],
    }


def __ibcext_vtable__() -> dict:
    return {
        "functions": {
            "validate":        {"param_types": ["dict", "dict"], "return_type": "bool",  "description": "校验 data 是否符合 schema"},
            "assert_schema":   {"param_types": ["dict", "dict"], "return_type": "void",  "description": "校验失败则抛出 RuntimeError"},
            "required_fields": {"param_types": ["dict"],         "return_type": "list",  "description": "从 schema 提取 required 字段列表"},
            "infer":           {"param_types": ["dict"],         "return_type": "dict",  "description": "从 dict 数据推断简单 schema"},
            "coerce":          {"param_types": ["dict", "dict"], "return_type": "dict",  "description": "按 schema 对 dict 值进行类型强制转换"},
        }
    }
