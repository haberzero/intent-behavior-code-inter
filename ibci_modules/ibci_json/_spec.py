"""
JSON 序列化/操作插件规范

非侵入式 JSON 工具插件。包含解析、序列化、合并、嵌套访问等。
同时实现 __to_prompt__ 协议，使 json 模块参与 IBCI LLM 意图系统。
"""


def __ibcext_metadata__() -> dict:
    return {
        "name": "json",
        "kind": "method_module",
        "version": "2.0.0",
        "description": "IBCI JSON 工具（parse/stringify/merge/嵌套操作/prompt协议）",
        "dependencies": [],
    }


def __ibcext_vtable__() -> dict:
    return {
        "functions": {
            # --- 基础序列化 ---
            "parse":      {"params": [{"name": "s", "type": "str"}], "return_type": "dict",  "description": "JSON 字符串 → dict"},
            "stringify":  {"params": [{"name": "obj", "type": "any"}], "return_type": "str",   "description": "值 → JSON 字符串"},
            "pretty":     {"params": [{"name": "obj", "type": "any"}], "return_type": "str",   "description": "值 → 美化 JSON 字符串"},
            # --- 结构操作 ---
            "merge":      {"params": [{"name": "a", "type": "dict"}, {"name": "b", "type": "dict"}], "return_type": "dict",  "description": "浅层合并两个 dict（b 覆盖 a）"},
            "keys":       {"params": [{"name": "obj", "type": "dict"}], "return_type": "list",  "description": "返回 dict 的键列表"},
            "values":     {"params": [{"name": "obj", "type": "dict"}], "return_type": "list",  "description": "返回 dict 的值列表"},
            "get_nested": {"params": [{"name": "obj", "type": "dict"}, {"name": "path", "type": "str"}], "return_type": "any",   "description": "按点分路径读取嵌套值"},
            "set_nested": {"params": [{"name": "obj", "type": "dict"}, {"name": "path", "type": "str"}, {"name": "value", "type": "any"}], "return_type": "dict", "description": "按点分路径写入嵌套值（返回新 dict）"},
            # --- __prompt__ 协议 ---
            "__to_prompt__": {"params": [], "return_type": "str", "description": "LLM 意图系统的模块描述"},
        }
    }
