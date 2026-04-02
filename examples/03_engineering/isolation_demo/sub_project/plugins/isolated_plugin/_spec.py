from typing import Dict, Any

def __ibcext_metadata__() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "description": "Test plugin for isolation",
        "author": "Trae",
        "capabilities": []
    }

def __ibcext_vtable__():
    return {
        "functions": {
            "get_secret": {
                "param_types": [],
                "return_type": "str"
            }
        }
    }
