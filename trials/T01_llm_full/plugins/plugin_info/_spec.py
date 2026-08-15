"""
Plugin Info 插件规范
"""
from typing import Dict, Any

def __ibcext_metadata__() -> Dict[str, Any]:
    return {
        "name": "plugin_info",
        "version": "1.0.0",
        "description": "Plugin info demonstrator",
        "dependencies": []
    }

def __ibcext_vtable__() -> Dict[str, Any]:
    return {
        "variables": {
            "version": "str",
            "author": "str"
        }
    }
