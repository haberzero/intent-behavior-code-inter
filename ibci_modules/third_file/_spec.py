"""
Third File Analysis Plugin Specification
Provides enhanced file operations for large-scale codebase analysis.
"""
from typing import Dict, Any

def __ibcext_metadata__() -> Dict[str, Any]:
    """Plugin metadata"""
    return {
        "name": "third_file",
        "version": "1.0.0",
        "description": "Advanced file analysis plugin for large codebase processing",
        "dependencies": [],
    }

def __ibcext_vtable__() -> Dict[str, Any]:
    """
    Method VTable - Native metadata declaration
    """
    return {
        "functions": {
            "search_in_files": {
                "param_types": ["str", "str", "list"], # root_dir, pattern, extensions
                "return_type": "list" # list of dicts: {path, line, content}
            },
            "list_files_recursive": {
                "param_types": ["str", "list"], # root_dir, extensions
                "return_type": "list"
            },
            "get_line_count": {
                "param_types": ["str"],
                "return_type": "int"
            },
            "read_lines_range": {
                "param_types": ["str", "int", "int"], # file_path, start, end
                "return_type": "list"
            },
            "get_file_size": {
                "param_types": ["str"],
                "return_type": "int"
            },
            "find_todos": {
                "param_types": ["str"], # root_dir
                "return_type": "list"
            }
        }
    }
