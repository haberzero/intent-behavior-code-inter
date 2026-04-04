"""
[IES 2.2] Third File Analysis Plugin Entry Point
Minimalist entry point that delegates to core logic.
"""
from .core import create_implementation

__all__ = ["create_implementation"]
